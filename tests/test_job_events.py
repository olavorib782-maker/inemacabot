from job import Job, JobStatus
from job_events import JobCompletedEvent


def test_job_completed_event_carrega_job():
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

    assert event.job is job
    assert event.job.status == JobStatus.CONCLUIDO