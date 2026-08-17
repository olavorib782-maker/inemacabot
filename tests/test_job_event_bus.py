import pytest

from job import Job, JobStatus
from job_event_bus import JobEventBus
from job_events import JobCompletedEvent


@pytest.mark.asyncio
async def test_publica_e_recebe_evento():
    job = Job(
        chat_id=123,
        fila="mkivideos",
        tipo="video",
        skill="video_explicativo",
        titulo="Teste",
        descricao="Teste",
        status=JobStatus.CONCLUIDO,
    )

    event = JobCompletedEvent(job)
    bus = JobEventBus()

    await bus.publish(event)
    recebido = await bus.get()

    assert recebido is event
    assert recebido.job is job