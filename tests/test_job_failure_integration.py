from __future__ import annotations

import asyncio

import pytest

from job import Job, JobStatus
from job_event_bus import JobEventBus
from queue_manager import QueueManager
from result_notifier import ResultNotifier
from result_supervisor import ResultSupervisor
from workers.base_worker import BaseWorker


@pytest.mark.asyncio
async def test_falha_do_worker_chega_ao_sender_com_mensagem_segura():
    class FailingWorker(BaseWorker):
        async def process_job(self, job: Job) -> str:
            raise RuntimeError("detalhe secreto da exceção")

    class RecordingNotifier(ResultNotifier):
        def __init__(self, sender):
            super().__init__(sender)
            self.failed_jobs: list[Job] = []

        async def notify_failure(self, job: Job) -> None:
            self.failed_jobs.append(job)
            await super().notify_failure(job)

    queue_manager = QueueManager()
    event_bus = JobEventBus()
    sent = asyncio.Event()
    messages: list[tuple[int, str]] = []

    async def sender(chat_id: int, message: str) -> None:
        messages.append((chat_id, message))
        sent.set()

    notifier = RecordingNotifier(sender)
    supervisor = ResultSupervisor(event_bus, notifier)
    worker = FailingWorker(queue_manager, "mkivideos", event_bus=event_bus)
    job = Job(
        chat_id=123,
        fila="mkivideos",
        tipo="video",
        skill="video_explicativo",
        titulo="Teste",
        descricao="Teste",
        resultado="resultado parcial confidencial",
    )
    worker_task = asyncio.create_task(worker.run())
    supervisor_task = asyncio.create_task(supervisor.run())

    try:
        await queue_manager.put(job)
        await asyncio.wait_for(sent.wait(), timeout=1)

        assert job.status is JobStatus.ERRO
        assert notifier.failed_jobs == [job]
        assert len(messages) == 1
        chat_id, message = messages[0]
        assert chat_id == job.chat_id
        assert job.id in message
        assert job.skill in message
        assert "Traceback" not in message
        assert "RuntimeError" not in message
        assert "detalhe secreto da exceção" not in message
        assert job.resultado not in message
    finally:
        worker_task.cancel()
        supervisor_task.cancel()
        await asyncio.gather(worker_task, supervisor_task, return_exceptions=True)
