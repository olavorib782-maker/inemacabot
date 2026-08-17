from __future__ import annotations

import asyncio
from collections.abc import Callable

import pytest

from job import Job, JobStatus
from queue_manager import QueueManager
from workers.base_worker import BaseWorker
from workers.text_worker import TextWorker


def test_text_worker_herda_base_worker_e_usa_fila_correta() -> None:
    worker = TextWorker(QueueManager())

    assert isinstance(worker, BaseWorker)
    assert worker.fila == "mkitextos"


def test_text_worker_processa_job_com_sucesso() -> None:
    async def scenario() -> None:
        worker = TextWorker(QueueManager())
        job = _make_job("mkitextos")

        result = await worker.process_job(job)

        assert result == f"Job {job.id} processado pelo TextWorker."

    asyncio.run(scenario())


def test_text_worker_conclui_job_enfileirado() -> None:
    async def scenario() -> None:
        manager = QueueManager()
        worker = TextWorker(manager)
        job = _make_job("mkitextos")
        task = asyncio.create_task(worker.run())

        await manager.put(job)
        await _wait_until(lambda: job.status is JobStatus.CONCLUIDO)

        assert job.resultado == f"Job {job.id} processado pelo TextWorker."
        await _cancel(task)

    asyncio.run(scenario())


def test_text_worker_rejeita_fila_incorreta() -> None:
    with pytest.raises(ValueError, match="TextWorker aceita apenas a fila mkitextos"):
        TextWorker(QueueManager(), "mkivideos")


def _make_job(fila: str) -> Job:
    return Job(42, fila, "texto", "teste", "Texto", "Descrição de teste.")


async def _wait_until(predicate: Callable[[], bool]) -> None:
    async def wait() -> None:
        while not predicate():
            await asyncio.sleep(0)

    await asyncio.wait_for(wait(), timeout=1)


async def _cancel(task: asyncio.Task[None]) -> None:
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
