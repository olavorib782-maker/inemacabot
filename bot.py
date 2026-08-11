"""Ponto de entrada e handlers do bot do Telegram."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import cast

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
from config import Settings, load_config
from conversation_history import ConversationHistory


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
            "Use /limpar para apagar o contexto da conversa."
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


async def text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Envia uma mensagem de texto autorizada à IA e registra o par resultante."""
    services = _services(context)
    if not _is_authorized(update, services):
        return

    message = update.effective_message
    if message is None or not message.text:
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


def create_application(settings: Settings) -> Application:
    """Monta a aplicação do Telegram e registra seus handlers."""
    application = ApplicationBuilder().token(settings.telegram_bot_token).build()
    application.bot_data[SERVICES_KEY] = BotServices(
        settings=settings,
        ai_client=AIClient(settings),
        history=ConversationHistory(settings.history_max_messages),
    )
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("ajuda", help_command))
    application.add_handler(CommandHandler("limpar", clear_command))
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
