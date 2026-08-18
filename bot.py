"""Ponto de entrada e handlers do bot do Telegram."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import cast
from job_event_bus import JobEventBus

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from ai_client import AIClient, AIClientError
from agent_runner import AgentRunner
from config import Settings, load_config
from conversation_history import ConversationHistory
from job import JobStatus
from job_registry import JobRegistry
from job_service import JobService
from queue_manager import QueueManager
from router import Router
from skill_loader import SkillLoader
from worker_manager import WorkerManager
from result_notifier import ResultNotifier
from result_supervisor import ResultSupervisor

logger = logging.getLogger(__name__)
SERVICES_KEY = "services"
TELEGRAM_MAX_MESSAGE_LENGTH = 4000


def split_message(
    text: str,
    limit: int = TELEGRAM_MAX_MESSAGE_LENGTH,
) -> list[str]:
    """Divide uma mensagem longa em blocos compatíveis com o Telegram."""

    if not text:
        return []

    if len(text) <= limit:
        return [text]

    parts: list[str] = []
    remaining = text

    while len(remaining) > limit:
        chunk = remaining[:limit]

        split_at = chunk.rfind("\n")
        if split_at <= 0:
            split_at = chunk.rfind(" ")

        if split_at <= 0:
            split_at = limit

        part = remaining[:split_at]

        if part:
            parts.append(part)

        remaining = remaining[split_at:]

        if remaining.startswith("\n") or remaining.startswith(" "):
            remaining = remaining[1:]

    if remaining:
        parts.append(remaining)

    return parts



@dataclass(slots=True)
class BotServices:
    """Dependências compartilhadas pelos handlers do bot."""

    settings: Settings
    ai_client: AIClient
    history: ConversationHistory
    queue_manager: QueueManager
    job_registry: JobRegistry
    job_service: JobService
    worker_manager: WorkerManager
    skill_loader: SkillLoader
    agent_runner: AgentRunner
    result_notifier: ResultNotifier | None = None
    result_supervisor: ResultSupervisor | None = None
    result_supervisor_task: asyncio.Task[None] | None = None

def _services(context: ContextTypes.DEFAULT_TYPE) -> BotServices:
    return cast(BotServices, context.application.bot_data[SERVICES_KEY])


def _is_authorized(update: Update, services: BotServices) -> bool:
    """Retorna se o remetente da atualização é o usuário permitido."""
    user = update.effective_user
    return user is not None and user.id == services.settings.telegram_allowed_user_id


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Responde ao comando /start para o usuário autorizado."""
    services = _services(context)
    if not _is_authorized(update, services):
        return

    message = update.effective_message
    if message is not None:
        await message.reply_text("Olá! Envie uma mensagem para conversar com o assistente.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Explica os comandos disponíveis para o usuário autorizado."""
    services = _services(context)
    if not _is_authorized(update, services):
        return

    message = update.effective_message
    if message is not None:
        await message.reply_text(
            "Envie uma mensagem para falar com o assistente. "
            "Use /limpar para apagar o contexto da conversa e /status para "
            "consultar os trabalhos."
        )


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Apaga o histórico em memória para o usuário autorizado."""
    services = _services(context)
    if not _is_authorized(update, services):
        return

    async with services.history.lock:
        services.history.clear()

    message = update.effective_message
    if message is not None:
        await message.reply_text("O contexto da conversa foi apagado.")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mostra um resumo dos trabalhos ou os detalhes de um Job."""
    services = _services(context)
    if not _is_authorized(update, services):
        return

    message = update.effective_message
    if message is None:
        return

    if len(context.args) > 1:
        await message.reply_text("Uso: /status ou /status <job_id>")
        return

    if context.args:
        job_id = context.args[0]
        job = services.job_registry.get(job_id)
        if job is None:
            await message.reply_text(f"Job não encontrado: {job_id}")
            return

        titulo = job.titulo
        if len(titulo) > 200:
            titulo = f"{titulo[:200]}..."

        await message.reply_text(
            "Detalhes do Job\n\n"
            f"Job ID: {job.id}\n"
            f"Fila: {job.fila}\n"
            f"Skill: {job.skill}\n"
            f"Status: {job.status.value}\n"
            f"Título: {titulo}"
        )
        return

    jobs = services.job_registry.list_all()
    if not jobs:
        await message.reply_text("Nenhum Job registrado.")
        return

    counts = {status: 0 for status in JobStatus}
    for job in jobs:
        counts[job.status] += 1

    await message.reply_text(
        "Resumo dos Jobs\n\n"
        f"AGUARDANDO: {counts[JobStatus.AGUARDANDO]}\n"
        f"PROCESSANDO: {counts[JobStatus.PROCESSANDO]}\n"
        f"CONCLUIDO: {counts[JobStatus.CONCLUIDO]}\n"
        f"ERRO: {counts[JobStatus.ERRO]}\n"
        f"CANCELADO: {counts[JobStatus.CANCELADO]}\n"
        f"TOTAL: {len(jobs)}"
    )


async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Envia uma mensagem de texto autorizada à IA e registra o par resultante."""
    services = _services(context)
    if not _is_authorized(update, services):
        return

    message = update.effective_message
    if message is None or not message.text:
        return

    job = await services.job_service.submit(message.chat_id, message.text)
    if job is not None:
        await message.reply_text(
            "Trabalho recebido.\n"
            f"Fila: {job.fila}\n"
            f"Skill: {job.skill}\n"
            f"Status: {job.status.value}\n"
            f"Job: {job.id}"
        )
        return

    async with services.history.lock:
        try:
            answer = await services.ai_client.get_response(
                services.history.get_messages(), message.text
            )
        except AIClientError as error:
            await message.reply_text(str(error))
            return
        except Exception as error:
            logger.error("Falha inesperada no processamento da mensagem (%s).", type(error).__name__)
            await message.reply_text("Não foi possível processar sua mensagem no momento.")
            return

        services.history.add_pair(message.text, answer)

        for part in split_message(answer):
            await message.reply_text(part)



async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Registra falhas não tratadas sem incluir dados sensíveis."""
    logger.error("Erro não tratado pelo bot do Telegram (%s).", type(context.error).__name__)


async def start_workers(application: Application) -> None:
    """Inicia os workers quando a aplicação do Telegram estiver pronta."""
    services = cast(BotServices, application.bot_data[SERVICES_KEY])
    await services.worker_manager.start()
    if services.result_supervisor is not None and services.result_supervisor_task is None:
        services.result_supervisor_task = asyncio.create_task(
            services.result_supervisor.run(),
            name="result-supervisor",
        )


async def stop_workers(application: Application) -> None:
    """Encerra os workers durante o desligamento da aplicação."""
    services = cast(BotServices, application.bot_data[SERVICES_KEY])
    supervisor_task = services.result_supervisor_task
    if supervisor_task is not None:
        supervisor_task.cancel()
        await asyncio.gather(supervisor_task, return_exceptions=True)
        services.result_supervisor_task = None
    await services.worker_manager.stop()


def create_application(settings: Settings) -> Application:
    """Monta a aplicação do Telegram e registra seus handlers."""
    queue_manager = QueueManager()
    job_registry = JobRegistry()
    ai_client = AIClient(settings)
    skill_loader = SkillLoader("skills")
    agent_runner = AgentRunner(ai_client, skill_loader)
    event_bus = JobEventBus()
    application = (
        ApplicationBuilder()
        .token(settings.telegram_bot_token)
        .post_init(start_workers)
        .post_shutdown(stop_workers)
        .build()
    )
    async def send_result(chat_id: int, text: str) -> None:
        for part in split_message(text):
            await application.bot.send_message(chat_id=chat_id, text=part)

    result_notifier = ResultNotifier(send_result)
    result_supervisor = ResultSupervisor(event_bus, result_notifier)
    application.bot_data[SERVICES_KEY] = BotServices(
        settings=settings,
        ai_client=ai_client,
        history=ConversationHistory(settings.history_max_messages),
        queue_manager=queue_manager,
        job_registry=job_registry,
        job_service=JobService(Router(), queue_manager, job_registry),
        worker_manager=WorkerManager(
            queue_manager,
            agent_runner,
            event_bus=event_bus,
        ),
        skill_loader=skill_loader,
        agent_runner=agent_runner,
        result_notifier=result_notifier,
        result_supervisor=result_supervisor,
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("ajuda", help_command))
    application.add_handler(CommandHandler("limpar", clear_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message))
    application.add_error_handler(error_handler)
    return application


def main() -> None:
    """Carrega a configuração e inicia o recebimento de mensagens por polling."""
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO
    )
    settings = load_config()
    create_application(settings).run_polling()


if __name__ == "__main__":
    main()
