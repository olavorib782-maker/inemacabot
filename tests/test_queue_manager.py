from __future__ import annotations

import asyncio

import pytest

from job import Job
from queue_manager import QueueManager


def test_as_tres_filas_existem() -> None:
    manager = QueueManager()
    assert set(manager.queues) == {"mkivideos", "mkitextos", "mkiservicos"}


def test_job_de_mkivideos_e_recuperado_da_mesma_fila() -> None:
    async def scenario() -> None:
        manager = QueueManager()
        job = _make_job("mkivideos")

        await manager.put(job)

        assert await manager.get("mkivideos") is job

    asyncio.run(scenario())


def test_job_de_mkitextos_nao_aparece_em_mkivideos() -> None:
    async def scenario() -> None:
        manager = QueueManager()
        job = _make_job("mkitextos")

        await manager.put(job)

        assert manager.size("mkivideos") == 0
        assert manager.size("mkitextos") == 1

    asyncio.run(scenario())


def test_job_de_mkiservicos_vai_para_a_fila_correta() -> None:
    async def scenario() -> None:
        manager = QueueManager()
        job = _make_job("mkiservicos")

        await manager.put(job)

        assert await manager.get("mkiservicos") is job

    asyncio.run(scenario())


def test_ordem_fifo_e_preservada() -> None:
    async def scenario() -> None:
        manager = QueueManager()
        first = _make_job("mkivideos", "Primeiro")
        second = _make_job("mkivideos", "Segundo")
        third = _make_job("mkivideos", "Terceiro")

        await manager.put(first)
        await manager.put(second)
        await manager.put(third)

        assert await manager.get("mkivideos") is first
        assert await manager.get("mkivideos") is second
        assert await manager.get("mkivideos") is third

    asyncio.run(scenario())


def test_size_informa_a_quantidade_de_jobs() -> None:
    async def scenario() -> None:
        manager = QueueManager()
        await manager.put(_make_job("mkivideos"))
        await manager.put(_make_job("mkivideos"))

        assert manager.size("mkivideos") == 2
        await manager.get("mkivideos")
        assert manager.size("mkivideos") == 1

    asyncio.run(scenario())


def test_fila_invalida_gera_erro_claro() -> None:
    manager = QueueManager()

    with pytest.raises(ValueError, match="Fila inválida: inexistente"):
        manager.size("inexistente")


def test_filas_sao_independentes() -> None:
    async def scenario() -> None:
        manager = QueueManager()
        video_job = _make_job("mkivideos")
        text_job = _make_job("mkitextos")

        await manager.put(video_job)
        await manager.put(text_job)

        assert await manager.get("mkitextos") is text_job
        assert manager.size("mkivideos") == 1
        assert await manager.get("mkivideos") is video_job

    asyncio.run(scenario())


def _make_job(fila: str, titulo: str = "Trabalho") -> Job:
    return Job(
        chat_id=42,
        fila=fila,
        tipo="teste",
        skill="teste",
        titulo=titulo,
        descricao="Descrição de teste.",
    )
