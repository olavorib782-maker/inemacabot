from __future__ import annotations

import asyncio
from collections.abc import Callable

import pytest

from job import Job, JobStatus
from queue_manager import QueueManager
from workers.base_worker import BaseWorker
from workers.service_worker import ServiceWorker
from workers.video_worker import VideoWorker


def test_service_worker_herda_base_worker_e_usa_fila_correta() -> None:
    worker = ServiceWorker(QueueManager())

    assert isinstance(worker, BaseWorker)
    assert worker.fila == "mkiservicos"


def test_service_worker_processa_job_com_sucesso() -> None:
    async def scenario() -> None:
        worker = ServiceWorker(QueueManager())
        job = _make_job("mkiservicos")

        result = await worker.process_job(job)

        assert result == f"Job {job.id} processado pelo ServiceWorker."

    asyncio.run(scenario())


def test_service_worker_conclui_job_enfileirado() -> None:
    async def scenario() -> None:
        manager = QueueManager()
        worker = ServiceWorker(manager)
        job = _make_job("mkiservicos")
        task = asyncio.create_task(worker.run())

        await manager.put(job)
        await _wait_until(lambda: job.status is JobStatus.CONCLUIDO)

        assert job.resultado == f"Job {job.id} processado pelo ServiceWorker."
        await _cancel(task)

    asyncio.run(scenario())


def test_service_worker_rejeita_fila_incorreta() -> None:
    with pytest.raises(ValueError, match="ServiceWorker aceita apenas a fila mkiservicos"):
        ServiceWorker(QueueManager(), "mkivideos")


def test_workers_especializados_sao_independentes() -> None:
    async def scenario() -> None:
        manager = QueueManager()
        video_worker = VideoWorker(manager)
        service_worker = ServiceWorker(manager)
        video_job = _make_job("mkivideos")
        service_job = _make_job("mkiservicos")
        video_task = asyncio.create_task(video_worker.run())
        service_task = asyncio.create_task(service_worker.run())

        await manager.put(video_job)
        await manager.put(service_job)
        await _wait_until(
            lambda: video_job.status is JobStatus.CONCLUIDO
            and service_job.status is JobStatus.CONCLUIDO
        )

        assert video_job.resultado.endswith("VideoWorker.")
        assert service_job.resultado.endswith("ServiceWorker.")
        await _cancel(video_task)
        await _cancel(service_task)

    asyncio.run(scenario())


def _make_job(fila: str) -> Job:
    return Job(42, fila, "servico", "teste", "Serviço", "Descrição de teste.")


async def _wait_until(predicate: Callable[[], bool]) -> None:
    async def wait() -> None:
        while not predicate():
            await asyncio.sleep(0)

    await asyncio.wait_for(wait(), timeout=1)


async def _cancel(task: asyncio.Task[None]) -> None:
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
