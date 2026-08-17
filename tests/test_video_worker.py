from __future__ import annotations

import asyncio
from collections.abc import Callable

import pytest

from ai_client import AIClientError

from job import Job, JobStatus
from queue_manager import QueueManager
from workers.base_worker import BaseWorker
from workers.video_worker import VideoWorker


def test_video_worker_herda_base_worker_e_usa_fila_correta() -> None:
    worker = VideoWorker(QueueManager())

    assert isinstance(worker, BaseWorker)
    assert worker.fila == "mkivideos"


def test_video_worker_processa_job_com_sucesso() -> None:
    async def scenario() -> None:
        agent_runner = _FakeAgentRunner("Resultado do agente")
        worker = VideoWorker(QueueManager(), agent_runner=agent_runner)
        job = _make_job("mkivideos")

        result = await worker.process_job(job)

        assert agent_runner.calls == [job]
        assert result == "Resultado do agente"

    asyncio.run(scenario())


def test_video_worker_conclui_job_enfileirado() -> None:
    async def scenario() -> None:
        manager = QueueManager()
        worker = VideoWorker(manager, agent_runner=_FakeAgentRunner("Resultado do agente"))
        job = _make_job("mkivideos")
        task = asyncio.create_task(worker.run())

        await manager.put(job)
        await _wait_until(lambda: job.status is JobStatus.CONCLUIDO)

        assert job.resultado == "Resultado do agente"
        await _cancel(task)

    asyncio.run(scenario())


def test_video_worker_rejeita_fila_incorreta() -> None:
    with pytest.raises(ValueError, match="VideoWorker aceita apenas a fila mkivideos"):
        VideoWorker(QueueManager(), "mkitextos")


def test_erro_do_agent_runner_coloca_job_em_erro_pelo_ciclo_base() -> None:
    async def scenario() -> None:
        manager = QueueManager()
        worker = VideoWorker(manager, agent_runner=_FailingAgentRunner(AIClientError("Falha da IA")))
        job = _make_job("mkivideos")
        task = asyncio.create_task(worker.run())

        await manager.put(job)
        await _wait_until(lambda: job.status is JobStatus.ERRO)

        assert job.resultado == ""
        await _cancel(task)

    asyncio.run(scenario())


def test_video_worker_nao_altera_job_fora_do_ciclo_base() -> None:
    async def scenario() -> None:
        worker = VideoWorker(QueueManager(), agent_runner=_FakeAgentRunner("Resultado do agente"))
        job = _make_job("mkivideos")

        await worker.process_job(job)

        assert job.status is JobStatus.AGUARDANDO
        assert job.resultado == ""

    asyncio.run(scenario())


def _make_job(fila: str) -> Job:
    return Job(42, fila, "video", "teste", "Vídeo", "Descrição de teste.")


class _FakeAgentRunner:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[Job] = []

    async def run(self, job: Job) -> str:
        self.calls.append(job)
        return self.response


class _FailingAgentRunner:
    def __init__(self, error: AIClientError) -> None:
        self.error = error

    async def run(self, job: Job) -> str:
        raise self.error


async def _wait_until(predicate: Callable[[], bool]) -> None:
    async def wait() -> None:
        while not predicate():
            await asyncio.sleep(0)

    await asyncio.wait_for(wait(), timeout=1)


async def _cancel(task: asyncio.Task[None]) -> None:
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
