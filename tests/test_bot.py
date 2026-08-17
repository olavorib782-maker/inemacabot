from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace

from bot import (
    SERVICES_KEY,
    TELEGRAM_MAX_MESSAGE_LENGTH,
    _is_authorized,
    create_application,
    split_message,
    start_workers,
    stop_workers,
    text_message,
)
from conversation_history import ConversationHistory
from config import Settings
from job import Job


@dataclass
class _FakeSettings:
    telegram_allowed_user_id: int = 42


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


def test_create_application_compartilha_dependencias_do_agent_runner() -> None:
    application = create_application(
        Settings(
            telegram_bot_token="123:test-token",
            telegram_allowed_user_id=42,
            ai_api_key="test-key",
            ai_base_url="https://example.test/v1",
            ai_model="test-model",
            ai_system_prompt="Teste",
            history_max_messages=20,
        )
    )
    services = application.bot_data[SERVICES_KEY]

    assert services.agent_runner.ai_client is services.ai_client
    assert services.agent_runner.skill_loader is services.skill_loader
    assert services.job_service.queue_manager is services.queue_manager
    assert services.worker_manager.queue_manager is services.queue_manager
    assert services.worker_manager.agent_runner is services.agent_runner
    assert services.worker_manager.event_bus is services.result_supervisor.event_bus


class _FakeMessage:
    def __init__(self, text: str, chat_id: int) -> None:
        self.text = text
        self.chat_id = chat_id
        self.replies: list[str] = []

    async def reply_text(self, text: str) -> None:
        self.replies.append(text)


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


def _context(services: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(application=SimpleNamespace(bot_data={SERVICES_KEY: services}))
