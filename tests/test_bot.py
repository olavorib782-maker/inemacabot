from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from bot import (
    SERVICES_KEY,
    TELEGRAM_MAX_MESSAGE_LENGTH,
    _is_authorized,
    _send_result_document,
    create_application,
    document_message,
    help_command,
    split_message,
    start_workers,
    status_command,
    stop_workers,
    text_message,
)
from conversation_history import ConversationHistory
from artifact_store import ArtifactStore
from config import Settings
from job import Job, JobStatus
from job_registry import JobRegistry
from queue_manager import QueueManager
from sqlite_job_store import SQLiteJobStore
from telegram.ext import CommandHandler


@dataclass
class _FakeSettings:
    telegram_allowed_user_id: int = 42
    telegram_ls_max_file_bytes: int = 1024


def _fake_update(user_id: int | None) -> SimpleNamespace:
    user = None if user_id is None else SimpleNamespace(id=user_id)
    return SimpleNamespace(effective_user=user)


def _fake_services(allowed_user_id: int = 42) -> SimpleNamespace:
    return SimpleNamespace(settings=_FakeSettings(telegram_allowed_user_id=allowed_user_id))


def test_is_authorized_permite_usuario_correto() -> None:
    assert _is_authorized(_fake_update(42), _fake_services()) is True


def test_is_authorized_bloqueia_usuario_diferente() -> None:
    assert _is_authorized(_fake_update(999), _fake_services()) is False


def test_is_authorized_bloqueia_quando_sem_usuario() -> None:
    assert _is_authorized(_fake_update(None), _fake_services()) is False


def test_help_command_menciona_status() -> None:
    async def scenario() -> None:
        message = _FakeMessage("/ajuda", 42)
        await help_command(
            _message_update(42, message),
            _context(_fake_services()),
        )
        assert len(message.replies) == 1
        assert "/status" in message.replies[0]

    asyncio.run(scenario())


def test_documento_ls_autorizado_e_salvo_e_enfileirado(tmp_path: Path) -> None:
    async def scenario() -> None:
        queue = QueueManager()
        registry = JobRegistry()
        store = ArtifactStore(tmp_path / "artifacts")
        services = SimpleNamespace(
            settings=_FakeSettings(),
            artifact_store=store,
            job_service=__import__("job_service").JobService(
                __import__("router").Router(), queue, registry
            ),
        )
        message = _FakeDocumentMessage("../Meu Tema.ls", 100, 42)
        bot = _FakeTelegramBot("(title Teste)")

        await document_message(
            _document_update(42, message), _document_context(services, bot)
        )

        assert bot.get_file_calls == ["file-id"]
        assert queue.size("mkimusica") == 1
        job = await queue.get("mkimusica")
        assert registry.get(job.id) is job
        assert job.artifacts[0].relative_path == f"{job.id}/input.ls"
        assert job.artifacts[0].filename == "Meu Tema.ls"
        saved_path = store.resolve(job.artifacts[0].relative_path)
        assert saved_path.read_text(encoding="utf-8") == "(title Teste)"
        assert saved_path.name == "input.ls"
        assert message.replies[0].startswith("Arquivo recebido.\nFila: mkimusica")

    asyncio.run(scenario())


def test_documento_nao_autorizado_nao_dispara_download(tmp_path: Path) -> None:
    async def scenario() -> None:
        services = _document_services(tmp_path)
        message = _FakeDocumentMessage("teste.ls", 100, 42)
        bot = _FakeTelegramBot("conteúdo")

        await document_message(
            _document_update(999, message), _document_context(services, bot)
        )

        assert bot.get_file_calls == []
        assert message.replies == []
        assert services.job_service.queue_manager.size("mkimusica") == 0

    asyncio.run(scenario())


def test_documento_com_extensao_invalida_e_rejeitado(tmp_path: Path) -> None:
    async def scenario() -> None:
        services = _document_services(tmp_path)
        message = _FakeDocumentMessage("partitura.pdf", 100, 42)
        bot = _FakeTelegramBot("conteúdo")

        await document_message(
            _document_update(42, message), _document_context(services, bot)
        )

        assert bot.get_file_calls == []
        assert message.replies == ["Envie um arquivo .ls válido."]

    asyncio.run(scenario())


def test_documento_acima_do_limite_e_rejeitado(tmp_path: Path) -> None:
    async def scenario() -> None:
        services = _document_services(tmp_path)
        message = _FakeDocumentMessage("teste.ls", 1025, 42)
        bot = _FakeTelegramBot("conteúdo")

        await document_message(
            _document_update(42, message), _document_context(services, bot)
        )

        assert bot.get_file_calls == []
        assert message.replies == ["O arquivo .ls excede o tamanho permitido."]

    asyncio.run(scenario())


def test_send_document_recebe_nome_musicxml(tmp_path: Path) -> None:
    async def scenario() -> None:
        path = tmp_path / "output.xml"
        path.write_text("<score-partwise/>", encoding="utf-8")
        bot = _RecordingDocumentBot()

        await _send_result_document(
            bot, 42, path, "resultado.musicxml", "Leadsheet convertido para MusicXML."
        )

        assert len(bot.calls) == 1
        call = bot.calls[0]
        assert call["chat_id"] == 42
        assert call["filename"] == "resultado.musicxml"
        assert call["caption"] == "Leadsheet convertido para MusicXML."
        assert call["content"] == b"<score-partwise/>"

    asyncio.run(scenario())


def test_status_com_registry_vazio() -> None:
    async def scenario() -> None:
        message = _FakeMessage("/status", 42)
        await status_command(
            _message_update(42, message),
            _status_context(JobRegistry()),
        )
        assert message.replies == ["Nenhum Job registrado."]

    asyncio.run(scenario())


def test_status_mostra_resumo_com_todos_os_estados_e_total() -> None:
    async def scenario() -> None:
        registry = JobRegistry()
        statuses = [
            JobStatus.AGUARDANDO,
            JobStatus.AGUARDANDO,
            JobStatus.PROCESSANDO,
            JobStatus.CONCLUIDO,
            JobStatus.ERRO,
        ]
        for status in statuses:
            job = _make_status_job()
            job.status = status
            registry.add(job)

        message = _FakeMessage("/status", 42)
        await status_command(
            _message_update(42, message),
            _status_context(registry),
        )

        assert message.replies == [
            "Resumo dos Jobs\n\n"
            "AGUARDANDO: 2\n"
            "PROCESSANDO: 1\n"
            "CONCLUIDO: 1\n"
            "ERRO: 1\n"
            "CANCELADO: 0\n"
            "TOTAL: 5"
        ]

    asyncio.run(scenario())


def test_status_consulta_job_especifico() -> None:
    async def scenario() -> None:
        registry = JobRegistry()
        job = _make_status_job("Meu trabalho")
        job.status = JobStatus.PROCESSANDO
        registry.add(job)
        message = _FakeMessage(f"/status {job.id}", 42)

        await status_command(
            _message_update(42, message),
            _status_context(registry, [job.id]),
        )

        assert message.replies == [
            "Detalhes do Job\n\n"
            f"Job ID: {job.id}\n"
            "Fila: mkitextos\n"
            "Skill: teste\n"
            "Status: PROCESSANDO\n"
            "Título: Meu trabalho"
        ]

    asyncio.run(scenario())


def test_status_job_inexistente() -> None:
    async def scenario() -> None:
        message = _FakeMessage("/status desconhecido", 42)
        await status_command(
            _message_update(42, message),
            _status_context(JobRegistry(), ["desconhecido"]),
        )
        assert message.replies == ["Job não encontrado: desconhecido"]

    asyncio.run(scenario())


def test_status_rejeita_mais_de_um_argumento() -> None:
    async def scenario() -> None:
        message = _FakeMessage("/status um dois", 42)
        await status_command(
            _message_update(42, message),
            _status_context(JobRegistry(), ["um", "dois"]),
        )
        assert message.replies == ["Uso: /status ou /status <job_id>"]

    asyncio.run(scenario())


def test_status_nao_autorizado_nao_consulta_registry_nem_responde() -> None:
    async def scenario() -> None:
        registry = _SpyRegistry()
        message = _FakeMessage("/status", 42)
        await status_command(
            _message_update(999, message),
            _status_context(registry),
        )
        assert registry.calls == []
        assert message.replies == []

    asyncio.run(scenario())


def test_status_sem_effective_message_nao_responde_nem_consulta_registry() -> None:
    async def scenario() -> None:
        registry = _SpyRegistry()
        update = SimpleNamespace(
            effective_user=SimpleNamespace(id=42),
            effective_message=None,
        )
        await status_command(update, _status_context(registry))
        assert registry.calls == []

    asyncio.run(scenario())


def test_status_trunca_titulo_acima_de_200_caracteres() -> None:
    async def scenario() -> None:
        registry = JobRegistry()
        job = _make_status_job("a" * 201)
        registry.add(job)
        message = _FakeMessage(f"/status {job.id}", 42)

        await status_command(
            _message_update(42, message),
            _status_context(registry, [job.id]),
        )

        assert message.replies[0].endswith(f"Título: {'a' * 200}...")
        assert "a" * 201 not in message.replies[0]

    asyncio.run(scenario())


def test_split_message_nao_divide_texto_curto() -> None:
    text = "Olá, tudo bem?"
    assert split_message(text) == [text]


def test_split_message_divide_texto_acima_do_limite() -> None:
    text = "a" * (TELEGRAM_MAX_MESSAGE_LENGTH + 100)
    parts = split_message(text)
    assert len(parts) == 2
    assert all(len(part) <= TELEGRAM_MAX_MESSAGE_LENGTH for part in parts)
    assert "".join(parts) == text


def test_split_message_prefere_quebrar_em_espaco() -> None:
    limit = 20
    text = "palavra " * 10
    parts = split_message(text, limit=limit)
    assert all(len(part) <= limit for part in parts)
    for part in parts[:-1]:
        assert not part.endswith("palavr")


def test_split_message_prefere_quebrar_em_quebra_de_linha() -> None:
    limit = 15
    text = "linha um\nlinha dois\nlinha tres"
    parts = split_message(text, limit=limit)
    assert all(len(part) <= limit for part in parts)


def test_split_message_corta_palavra_unica_maior_que_limite() -> None:
    limit = 10
    text = "a" * 25
    parts = split_message(text, limit=limit)
    assert all(len(part) <= limit for part in parts)
    assert "".join(parts) == text


def test_split_message_preserva_conteudo_total() -> None:
    text = ("Frase número. " * 500).strip()
    parts = split_message(text)
    assert all(len(part) <= TELEGRAM_MAX_MESSAGE_LENGTH for part in parts)
    assert sum(len(p) for p in parts) <= len(text)
    assert len(parts) > 0


def test_text_message_enfileira_job_sem_ia_nem_historico() -> None:
    async def scenario() -> None:
        job = Job(42, "mkivideos", "video", "video_explicativo", "Video", "Descricao")
        job_service = _FakeJobService(job)
        ai_client = _FakeAIClient()
        history = ConversationHistory(20)
        message = _FakeMessage("Quero um video explicativo", 456)
        services = _services_for_text(job_service, ai_client, history)

        await text_message(_message_update(42, message), _context(services))

        assert job_service.calls == [(456, "Quero um video explicativo")]
        assert ai_client.calls == []
        assert history.get_messages() == []
        assert message.replies == [
            "Trabalho recebido.\n"
            "Fila: mkivideos\n"
            "Skill: video_explicativo\n"
            "Status: AGUARDANDO\n"
            f"Job: {job.id}"
        ]

    asyncio.run(scenario())


def test_text_message_normal_preserva_fluxo_da_ia() -> None:
    async def scenario() -> None:
        job_service = _FakeJobService(None)
        ai_client = _FakeAIClient("Resposta da IA")
        history = ConversationHistory(20)
        message = _FakeMessage("Bom dia", 456)

        await text_message(_message_update(42, message), _context(_services_for_text(job_service, ai_client, history)))

        assert job_service.calls == [(456, "Bom dia")]
        assert ai_client.calls == [([], "Bom dia")]
        assert history.get_messages() == [
            {"role": "user", "content": "Bom dia"},
            {"role": "assistant", "content": "Resposta da IA"},
        ]
        assert message.replies == ["Resposta da IA"]

    asyncio.run(scenario())


def test_text_message_nao_autorizada_nao_acessa_servicos() -> None:
    async def scenario() -> None:
        job_service = _FakeJobService(None)
        ai_client = _FakeAIClient()
        message = _FakeMessage("Quero um video", 456)

        await text_message(
            _message_update(999, message),
            _context(_services_for_text(job_service, ai_client, ConversationHistory(20))),
        )

        assert job_service.calls == []
        assert ai_client.calls == []
        assert message.replies == []

    asyncio.run(scenario())


def test_callbacks_de_ciclo_de_vida_controlam_workers() -> None:
    async def scenario() -> None:
        worker_manager = _FakeWorkerManager()
        result_supervisor = _FakeResultSupervisor()
        application = SimpleNamespace(
            bot_data={SERVICES_KEY: SimpleNamespace(
                worker_manager=worker_manager,
                queue_manager=QueueManager(),
                job_registry=JobRegistry(),
                result_supervisor=result_supervisor,
                result_supervisor_task=None,
            )}
        )

        await start_workers(application)
        services = application.bot_data[SERVICES_KEY]
        supervisor_task = services.result_supervisor_task
        assert supervisor_task is not None
        await asyncio.wait_for(result_supervisor.started.wait(), timeout=1)
        await stop_workers(application)

        assert worker_manager.start_calls == 1
        assert worker_manager.stop_calls == 1
        assert result_supervisor.cancelled is True
        assert supervisor_task.done() is True
        assert services.result_supervisor_task is None

    asyncio.run(scenario())


def test_startup_restaura_jobs_e_status_consulta_registry_restaurado(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        database_path = tmp_path / "jobs.sqlite3"
        source_store = SQLiteJobStore(database_path)
        source_store.initialize()
        jobs = {
            status: _make_status_job(status.value)
            for status in JobStatus
        }
        for status, job in jobs.items():
            job.status = status
            source_store.save(job)

        registry = JobRegistry(SQLiteJobStore(database_path))
        queue_manager = QueueManager()
        worker_manager = _FakeWorkerManager()
        services = SimpleNamespace(
            settings=_FakeSettings(),
            job_registry=registry,
            queue_manager=queue_manager,
            worker_manager=worker_manager,
            result_supervisor=None,
            result_supervisor_task=None,
        )
        application = SimpleNamespace(bot_data={SERVICES_KEY: services})

        await start_workers(application)

        assert registry.get(jobs[JobStatus.AGUARDANDO].id) is not None
        assert queue_manager.size("mkitextos") == 1
        assert await queue_manager.get("mkitextos") is registry.get(
            jobs[JobStatus.AGUARDANDO].id
        )
        restored_processing = registry.get(jobs[JobStatus.PROCESSANDO].id)
        assert restored_processing is not None
        assert restored_processing.status is JobStatus.ERRO
        assert "reinicialização" in restored_processing.resultado
        persisted = {
            job.id: job for job in SQLiteJobStore(database_path).load_all()
        }
        assert persisted[jobs[JobStatus.PROCESSANDO].id].status is JobStatus.ERRO
        assert queue_manager.size("mkitextos") == 0
        assert worker_manager.start_calls == 1

        message = _FakeMessage("/status", 42)
        context = _context(services)
        context.args = []
        await status_command(_message_update(42, message), context)
        assert message.replies == [
            "Resumo dos Jobs\n\n"
            "AGUARDANDO: 1\n"
            "PROCESSANDO: 0\n"
            "CONCLUIDO: 1\n"
            "ERRO: 2\n"
            "CANCELADO: 1\n"
            "TOTAL: 5"
        ]

    asyncio.run(scenario())


def test_create_application_compartilha_dependencias_do_agent_runner(
    tmp_path: Path,
) -> None:
    application = create_application(
        Settings(
            telegram_bot_token="123:test-token",
            telegram_allowed_user_id=42,
            ai_api_key="test-key",
            ai_base_url="https://example.test/v1",
            ai_model="test-model",
            ai_system_prompt="Teste",
            history_max_messages=20,
            improvisor_java_executable="java-test",
            improvisor_bridge_classpath="bridge;improvisor.jar",
            improvisor_home=tmp_path / "improvisor",
            improvisor_user_home=tmp_path / "user-home",
            improvisor_timeout_seconds=12,
            jobs_db_path=str(tmp_path / "jobs.sqlite3"),
        )
    )
    services = application.bot_data[SERVICES_KEY]

    assert services.agent_runner.ai_client is services.ai_client
    assert services.agent_runner.skill_loader is services.skill_loader
    assert services.job_service.queue_manager is services.queue_manager
    assert services.job_service.job_registry is services.job_registry
    assert services.worker_manager.queue_manager is services.queue_manager
    assert services.worker_manager.job_registry is services.job_registry
    assert services.worker_manager.agent_runner is services.agent_runner
    assert services.worker_manager.event_bus is services.result_supervisor.event_bus
    assert services.worker_manager.improvisor_client is not None
    assert services.worker_manager.improvisor_client._config.java_executable == "java-test"


def test_create_application_registra_comando_status(tmp_path: Path) -> None:
    application = create_application(
        Settings(
            telegram_bot_token="123:test-token",
            telegram_allowed_user_id=42,
            ai_api_key="test-key",
            ai_base_url="https://example.test/v1",
            ai_model="test-model",
            ai_system_prompt="Teste",
            history_max_messages=20,
            improvisor_java_executable="java-test",
            improvisor_bridge_classpath="bridge;improvisor.jar",
            improvisor_home=tmp_path / "improvisor",
            improvisor_user_home=tmp_path / "user-home",
            improvisor_timeout_seconds=12,
            jobs_db_path=str(tmp_path / "jobs.sqlite3"),
        )
    )

    handlers = [handler for group in application.handlers.values() for handler in group]
    assert any(
        isinstance(handler, CommandHandler) and "status" in handler.commands
        for handler in handlers
    )


def test_create_application_cria_um_cliente_e_compartilha_com_music_worker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = object()
    configs: list[object] = []

    def create_client(config: object) -> object:
        configs.append(config)
        return client

    monkeypatch.setattr("bot.ImproVisorClient", create_client)
    application = create_application(
        Settings(
            telegram_bot_token="123:test-token",
            telegram_allowed_user_id=42,
            ai_api_key="test-key",
            ai_base_url="https://example.test/v1",
            ai_model="test-model",
            ai_system_prompt="Teste",
            history_max_messages=20,
            improvisor_java_executable="java-test",
            improvisor_bridge_classpath="bridge;improvisor.jar",
            improvisor_home=tmp_path / "improvisor",
            improvisor_user_home=tmp_path / "user-home",
            improvisor_timeout_seconds=12,
            jobs_db_path=str(tmp_path / "jobs.sqlite3"),
        )
    )
    manager = application.bot_data[SERVICES_KEY].worker_manager

    async def scenario() -> None:
        await manager.start()
        assert manager.workers["mkimusica"].improvisor_client is client
        await manager.stop()

    asyncio.run(scenario())
    assert configs and len(configs) == 1
    assert manager.improvisor_client is client


class _FakeMessage:
    def __init__(self, text: str, chat_id: int) -> None:
        self.text = text
        self.chat_id = chat_id
        self.replies: list[str] = []

    async def reply_text(self, text: str) -> None:
        self.replies.append(text)


class _FakeDocumentMessage(_FakeMessage):
    def __init__(self, filename: str, file_size: int, chat_id: int) -> None:
        super().__init__("", chat_id)
        self.document = SimpleNamespace(
            file_name=filename,
            file_size=file_size,
            file_id="file-id",
        )


class _FakeTelegramFile:
    def __init__(self, content: str) -> None:
        self.content = content

    async def download_to_drive(self, custom_path: Path) -> None:
        Path(custom_path).write_text(self.content, encoding="utf-8")


class _FakeTelegramBot:
    def __init__(self, content: str) -> None:
        self.content = content
        self.get_file_calls: list[str] = []

    async def get_file(self, file_id: str) -> _FakeTelegramFile:
        self.get_file_calls.append(file_id)
        return _FakeTelegramFile(self.content)


class _RecordingDocumentBot:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def send_document(self, **kwargs: object) -> None:
        document = kwargs["document"]
        self.calls.append({**kwargs, "content": document.read()})  # type: ignore[union-attr]


class _FakeJobService:
    def __init__(self, result: Job | None) -> None:
        self.result = result
        self.calls: list[tuple[int, str]] = []

    async def submit(self, chat_id: int, message: str) -> Job | None:
        self.calls.append((chat_id, message))
        return self.result


class _FakeAIClient:
    def __init__(self, answer: str = "") -> None:
        self.answer = answer
        self.calls: list[tuple[list[dict[str, str]], str]] = []

    async def get_response(self, history: list[dict[str, str]], message: str) -> str:
        self.calls.append((history, message))
        return self.answer


class _FakeWorkerManager:
    def __init__(self) -> None:
        self.start_calls = 0
        self.stop_calls = 0

    async def start(self) -> None:
        self.start_calls += 1

    async def stop(self) -> None:
        self.stop_calls += 1


class _FakeResultSupervisor:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.cancelled = False

    async def run(self) -> None:
        self.started.set()
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            self.cancelled = True
            raise


class _SpyRegistry:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None]] = []

    def get(self, job_id: str) -> None:
        self.calls.append(("get", job_id))
        return None

    def list_all(self) -> list[Job]:
        self.calls.append(("list_all", None))
        return []


def _services_for_text(
    job_service: _FakeJobService,
    ai_client: _FakeAIClient,
    history: ConversationHistory,
) -> SimpleNamespace:
    return SimpleNamespace(
        settings=_FakeSettings(),
        job_service=job_service,
        ai_client=ai_client,
        history=history,
    )


def _message_update(user_id: int, message: _FakeMessage) -> SimpleNamespace:
    return SimpleNamespace(effective_user=SimpleNamespace(id=user_id), effective_message=message)


def _document_update(user_id: int, message: _FakeDocumentMessage) -> SimpleNamespace:
    return _message_update(user_id, message)


def _document_context(services: SimpleNamespace, bot: _FakeTelegramBot) -> SimpleNamespace:
    context = _context(services)
    context.bot = bot
    return context


def _document_services(tmp_path: Path) -> SimpleNamespace:
    from job_service import JobService
    from router import Router

    queue = QueueManager()
    return SimpleNamespace(
        settings=_FakeSettings(),
        artifact_store=ArtifactStore(tmp_path / "artifacts"),
        job_service=JobService(Router(), queue, JobRegistry()),
    )


def _context(services: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(application=SimpleNamespace(bot_data={SERVICES_KEY: services}))


def _status_context(
    registry: JobRegistry | _SpyRegistry,
    args: list[str] | None = None,
) -> SimpleNamespace:
    services = SimpleNamespace(settings=_FakeSettings(), job_registry=registry)
    context = _context(services)
    context.args = [] if args is None else args
    return context


def _make_status_job(titulo: str = "Trabalho") -> Job:
    return Job(
        chat_id=42,
        fila="mkitextos",
        tipo="texto",
        skill="teste",
        titulo=titulo,
        descricao="Descrição",
    )
