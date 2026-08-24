from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

import pytest

from artifact_store import ArtifactStore
from job import Job, JobStatus
from queue_manager import QueueManager
from worker_manager import WorkerManager
from workers.service_worker import ServiceWorker
from workers.text_worker import TextWorker
from workers.video_worker import VideoWorker
from workers.music_worker import MusicWorker


_IMPROVISOR_CLIENT = object()


def _manager(
    queue_manager: QueueManager,
    **kwargs: object,
) -> WorkerManager:
    return WorkerManager(
        queue_manager,
        improvisor_client=_IMPROVISOR_CLIENT,  # type: ignore[arg-type]
        **kwargs,  # type: ignore[arg-type]
    )


def test_worker_manager_cria_os_quatro_workers() -> None:
    async def scenario() -> None:
        manager = _manager(QueueManager())

        await manager.start()

        assert isinstance(manager.workers["mkivideos"], VideoWorker)
        assert isinstance(manager.workers["mkitextos"], TextWorker)
        assert isinstance(manager.workers["mkiservicos"], ServiceWorker)
        assert isinstance(manager.workers["mkimusica"], MusicWorker)
        await manager.stop()

    asyncio.run(scenario())


def test_worker_manager_sem_agent_runner_preserva_worker_de_laboratorio() -> None:
    async def scenario() -> None:
        manager = _manager(QueueManager())

        await manager.start()

        assert manager.workers["mkivideos"].agent_runner is None
        await manager.stop()

    asyncio.run(scenario())


def test_worker_manager_injeta_mesma_instancia_no_video_worker() -> None:
    async def scenario() -> None:
        agent_runner = _FakeAgentRunner("Resposta do agente")
        manager = _manager(QueueManager(), agent_runner=agent_runner)

        await manager.start()

        video_worker = manager.workers["mkivideos"]
        assert isinstance(video_worker, VideoWorker)
        assert video_worker.agent_runner is agent_runner
        assert not hasattr(manager.workers["mkitextos"], "agent_runner")
        assert not hasattr(manager.workers["mkiservicos"], "agent_runner")
        await manager.stop()

    asyncio.run(scenario())


def test_worker_manager_injeta_cliente_no_music_worker(tmp_path: Path) -> None:
    async def scenario() -> None:
        client = object()
        manager = WorkerManager(
            QueueManager(),
            improvisor_client=client,  # type: ignore[arg-type]
            artifact_store=ArtifactStore(tmp_path),
        )
        await manager.start()
        assert manager.workers["mkimusica"].improvisor_client is client
        await manager.stop()

    asyncio.run(scenario())


def test_worker_manager_rejeita_cliente_ausente() -> None:
    with pytest.raises(ValueError, match="ImproVisorClient"):
        WorkerManager(QueueManager())


def test_start_inicia_tres_tasks_ativas_com_filas_vazias() -> None:
    async def scenario() -> None:
        manager = _manager(QueueManager())

        await manager.start()
        await asyncio.sleep(0)

        assert len(manager.tasks) == 4
        assert all(not task.done() for task in manager.tasks.values())
        await manager.stop()

    asyncio.run(scenario())


def test_video_worker_processa_job_da_fila_de_videos() -> None:
    async def scenario() -> None:
        queue_manager = QueueManager()
        manager = _manager(queue_manager)
        job = _make_job("mkivideos")

        await manager.start()
        await queue_manager.put(job)
        await _wait_until(lambda: job.status is JobStatus.CONCLUIDO)

        assert job.resultado == f"Job {job.id} processado pelo VideoWorker."
        await manager.stop()

    asyncio.run(scenario())


def test_video_worker_usa_agent_runner_quando_fornecido_ao_manager() -> None:
    async def scenario() -> None:
        queue_manager = QueueManager()
        agent_runner = _FakeAgentRunner("Resultado do AgentRunner")
        manager = _manager(queue_manager, agent_runner=agent_runner)
        job = _make_job("mkivideos")

        await manager.start()
        await queue_manager.put(job)
        await _wait_until(lambda: job.status is JobStatus.CONCLUIDO)

        assert agent_runner.calls == [job]
        assert job.resultado == "Resultado do AgentRunner"
        await manager.stop()

    asyncio.run(scenario())


def test_text_worker_processa_job_da_fila_de_textos() -> None:
    async def scenario() -> None:
        queue_manager = QueueManager()
        manager = _manager(queue_manager)
        job = _make_job("mkitextos")

        await manager.start()
        await queue_manager.put(job)
        await _wait_until(lambda: job.status is JobStatus.CONCLUIDO)

        assert job.resultado == f"Job {job.id} processado pelo TextWorker."
        await manager.stop()

    asyncio.run(scenario())


def test_service_worker_processa_job_da_fila_de_servicos() -> None:
    async def scenario() -> None:
        queue_manager = QueueManager()
        manager = _manager(queue_manager)
        job = _make_job("mkiservicos")

        await manager.start()
        await queue_manager.put(job)
        await _wait_until(lambda: job.status is JobStatus.CONCLUIDO)

        assert job.resultado == f"Job {job.id} processado pelo ServiceWorker."
        await manager.stop()

    asyncio.run(scenario())


def test_stop_encerra_workers_e_limpa_referencias() -> None:
    async def scenario() -> None:
        manager = _manager(QueueManager())

        await manager.start()
        tasks = tuple(manager.tasks.values())
        await manager.stop()

        assert all(task.done() and task.cancelled() for task in tasks)
        assert manager.tasks == {}
        assert manager.workers == {}

    asyncio.run(scenario())


def test_start_nao_duplica_workers_sem_stop() -> None:
    async def scenario() -> None:
        manager = _manager(QueueManager())

        await manager.start()
        initial_workers = manager.workers
        initial_tasks = manager.tasks
        await manager.start()

        assert manager.workers is initial_workers
        assert manager.tasks is initial_tasks
        assert len(manager.tasks) == 4
        await manager.stop()

    asyncio.run(scenario())


def test_stop_e_seguro_sem_workers_ativos() -> None:
    async def scenario() -> None:
        manager = _manager(QueueManager())

        await manager.stop()

        assert manager.tasks == {}
        assert manager.workers == {}

    asyncio.run(scenario())


class _FakeAgentRunner:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[Job] = []

    async def run(self, job: Job) -> str:
        self.calls.append(job)
        return self.response


async def _wait_until(predicate: Callable[[], bool]) -> None:
    async def wait() -> None:
        while not predicate():
            await asyncio.sleep(0)

    await asyncio.wait_for(wait(), timeout=1)


def _make_job(fila: str) -> Job:
    return Job(42, fila, "teste", "teste", "Trabalho", "Descrição de teste.")
