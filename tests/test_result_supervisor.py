import asyncio

import pytest

from job import Job, JobStatus
from job_event_bus import JobEventBus
from job_events import JobCompletedEvent, JobFailedEvent
from result_notifier import ResultNotifier
from result_supervisor import ResultSupervisor


@pytest.mark.asyncio
async def test_supervisor_encaminha_evento_para_notifier():
    bus = JobEventBus()
    recebidos = []

    async def sender(chat_id: int, message: str) -> None:
        recebidos.append((chat_id, message))

    notifier = ResultNotifier(sender)
    supervisor = ResultSupervisor(bus, notifier)

    job = Job(
        chat_id=123,
        fila="mkivideos",
        tipo="video",
        skill="video_explicativo",
        titulo="Teste",
        descricao="Teste",
        status=JobStatus.CONCLUIDO,
        resultado="Resultado do teste.",
    )

    task = asyncio.create_task(supervisor.run())

    await bus.publish(JobCompletedEvent(job))
    await asyncio.sleep(0.01)

    task.cancel()
    await asyncio.gather(task, return_exceptions=True)

    assert len(recebidos) == 1
    assert recebidos[0][0] == 123
    assert "Resultado do teste." in recebidos[0][1]


@pytest.mark.asyncio
async def test_supervisor_encaminha_falha_ao_metodo_correto():
    class RecordingNotifier:
        def __init__(self) -> None:
            self.completed = []
            self.failed = []

        async def notify(self, job: Job) -> None:
            self.completed.append(job)

        async def notify_failure(self, job: Job) -> None:
            self.failed.append(job)

    notifier = RecordingNotifier()
    supervisor = ResultSupervisor(JobEventBus(), notifier)
    job = Job(
        chat_id=123,
        fila="mkivideos",
        tipo="video",
        skill="video_explicativo",
        titulo="Teste",
        descricao="Teste",
        status=JobStatus.ERRO,
    )

    await supervisor.handle(JobFailedEvent(job))

    assert notifier.failed == [job]
    assert notifier.completed == []


@pytest.mark.asyncio
async def test_falha_de_envio_nao_encerra_supervisor() -> None:
    class FlakyNotifier:
        def __init__(self) -> None:
            self.calls = 0
            self.received = []

        async def notify(self, job: Job) -> None:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("falha de envio")
            self.received.append(job)

        async def notify_failure(self, job: Job) -> None:
            self.received.append(job)

    bus = JobEventBus()
    notifier = FlakyNotifier()
    supervisor = ResultSupervisor(bus, notifier)  # type: ignore[arg-type]
    first = Job(1, "mkitextos", "texto", "teste", "A", "A")
    second = Job(1, "mkitextos", "texto", "teste", "B", "B")
    task = asyncio.create_task(supervisor.run())

    await bus.publish(JobCompletedEvent(first))
    await bus.publish(JobCompletedEvent(second))
    for _ in range(20):
        if notifier.received:
            break
        await asyncio.sleep(0)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)

    assert notifier.received == [second]
