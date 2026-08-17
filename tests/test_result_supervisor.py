import asyncio

import pytest

from job import Job, JobStatus
from job_event_bus import JobEventBus
from job_events import JobCompletedEvent
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