from __future__ import annotations

import asyncio
from collections.abc import Callable

import pytest

from job import Job, JobStatus
from queue_manager import QueueManager
from workers.base_worker import BaseWorker
from job_event_bus import JobEventBus

def test_worker_pega_um_job_da_fila_correta() -> None:
    async def scenario() -> None:
        manager = QueueManager()
        worker = BaseWorker(manager, "mkitextos")
        job = _make_job("mkitextos")
        task = asyncio.create_task(worker.run())

        await manager.put(job)
        await _wait_until(lambda: job.status is JobStatus.CONCLUIDO)

        assert manager.size("mkitextos") == 0
        await _cancel(task)

    asyncio.run(scenario())


def test_job_termina_concluido_apos_processamento_com_sucesso() -> None:
    async def scenario() -> None:
        manager = QueueManager()
        worker = BaseWorker(manager, "mkivideos")
        job = _make_job("mkivideos")
        task = asyncio.create_task(worker.run())

        assert job.status is JobStatus.AGUARDANDO
        await manager.put(job)
        await _wait_until(lambda: job.status is JobStatus.CONCLUIDO)

        assert job.status is JobStatus.CONCLUIDO
        await _cancel(task)

    asyncio.run(scenario())


def test_resultado_e_armazenado_no_job() -> None:
    async def scenario() -> None:
        manager = QueueManager()
        worker = BaseWorker(manager, "mkiservicos")
        job = _make_job("mkiservicos")
        task = asyncio.create_task(worker.run())

        await manager.put(job)
        await _wait_until(lambda: job.status is JobStatus.CONCLUIDO)

        assert job.resultado == f"Job {job.id} processado pelo worker."
        await _cancel(task)

    asyncio.run(scenario())


def test_atualizada_em_e_alterada_durante_processamento() -> None:
    async def scenario() -> None:
        manager = QueueManager()
        worker = BaseWorker(manager, "mkitextos")
        job = _make_job("mkitextos")
        created_at = job.atualizada_em
        task = asyncio.create_task(worker.run())

        await manager.put(job)
        await _wait_until(lambda: job.status is JobStatus.CONCLUIDO)

        assert job.atualizada_em > created_at
        await _cancel(task)

    asyncio.run(scenario())


def test_excecao_durante_processamento_coloca_job_em_erro() -> None:
    class FailingWorker(BaseWorker):
        async def process_job(self, job: Job) -> str:
            raise RuntimeError("falha de laboratório")

    async def scenario() -> None:
        manager = QueueManager()
        worker = FailingWorker(manager, "mkivideos")
        job = _make_job("mkivideos")
        task = asyncio.create_task(worker.run())

        await manager.put(job)
        await _wait_until(lambda: job.status is JobStatus.ERRO)

        assert job.status is JobStatus.ERRO
        await _cancel(task)

    asyncio.run(scenario())


def test_fila_vazia_faz_worker_aguardar() -> None:
    async def scenario() -> None:
        worker = BaseWorker(QueueManager(), "mkivideos")
        task = asyncio.create_task(worker.run())

        await asyncio.sleep(0)

        assert not task.done()
        await _cancel(task)

    asyncio.run(scenario())


def test_jobs_sao_processados_em_ordem_fifo() -> None:
    processed_ids: list[str] = []

    class RecordingWorker(BaseWorker):
        async def process_job(self, job: Job) -> str:
            processed_ids.append(job.id)
            return job.titulo

    async def scenario() -> None:
        manager = QueueManager()
        worker = RecordingWorker(manager, "mkivideos")
        jobs = [_make_job("mkivideos", f"Job {number}") for number in range(3)]
        task = asyncio.create_task(worker.run())

        for job in jobs:
            await manager.put(job)
        await _wait_until(lambda: all(job.status is JobStatus.CONCLUIDO for job in jobs))

        assert processed_ids == [job.id for job in jobs]
        await _cancel(task)

    asyncio.run(scenario())


def test_worker_nao_consume_job_de_outra_fila() -> None:
    async def scenario() -> None:
        manager = QueueManager()
        worker = BaseWorker(manager, "mkivideos")
        text_job = _make_job("mkitextos")
        task = asyncio.create_task(worker.run())

        await manager.put(text_job)
        await asyncio.sleep(0)

        assert text_job.status is JobStatus.AGUARDANDO
        assert manager.size("mkitextos") == 1
        await _cancel(task)

    asyncio.run(scenario())


async def _wait_until(predicate: Callable[[], bool]) -> None:
    async def wait() -> None:
        while not predicate():
            await asyncio.sleep(0)

    await asyncio.wait_for(wait(), timeout=1)


async def _cancel(task: asyncio.Task[None]) -> None:
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


def _make_job(fila: str, titulo: str = "Trabalho") -> Job:
    return Job(
        chat_id=42,
        fila=fila,
        tipo="teste",
        skill="teste",
        titulo=titulo,
        descricao="Descrição de teste.",
    )
@pytest.mark.asyncio
async def test_worker_publica_evento_ao_concluir_job():
    queue_manager = QueueManager()
    event_bus = JobEventBus()

    worker = BaseWorker(
        queue_manager,
        "mkivideos",
        event_bus=event_bus,
    )

    job = Job(
        chat_id=123,
        fila="mkivideos",
        tipo="video",
        skill="video_explicativo",
        titulo="Teste",
        descricao="Teste",
    )

    await queue_manager.put(job)

    task = asyncio.create_task(worker.run())

    evento = await asyncio.wait_for(event_bus.get(), timeout=1)

    task.cancel()
    await asyncio.gather(task, return_exceptions=True)

    assert evento.job is job
    assert job.status == JobStatus.CONCLUIDO