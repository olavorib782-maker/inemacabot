"""Testes de integração da produção de narrações."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from artifact_store import ArtifactStore
from job import Job
from narration_service import NarrationResult, NarrationError
from queue_manager import QueueManager
from workers.text_worker import TextWorker


def criar_job(gerar_audio=True):
    return Job(
        chat_id=1,
        fila="mkitextos",
        tipo="texto",
        skill="texto_avatar",
        titulo="Teste avatar",
        descricao="Texto avatar de 15 segundos",
        dados={"gerar_audio": gerar_audio},
    )


def resposta():
    return (
        "Título: Teste\n"
        "Narração pronta:\n"
        "Venha apreciar nossa música.\n"
        "Palavras da narração: 4\n"
        "Duração estimada: 15 segundos"
    )


@pytest.fixture
def ambiente(tmp_path):
    runner = AsyncMock()
    runner.run.return_value = resposta()

    store = ArtifactStore(tmp_path)

    worker = TextWorker(
        QueueManager(),
        agent_runner=runner,
        artifact_store=store,
    )

    return worker, runner, store


def test_avatar_com_audio(ambiente, monkeypatch):
    worker, runner, store = ambiente
    job = criar_job()

    relativo, caminho = store.job_path(
        job.id, "narracao.mp3"
    )

    caminho.write_bytes(b"audio simulado")

    preparar = AsyncMock(
        return_value=NarrationResult(
            resposta=resposta(),
            texto="Venha apreciar nossa música.",
            relative_path=relativo,
            audio_path=caminho,
            duracao_real=12.5,
            duracao_alvo=15,
            tentativas=2,
        )
    )

    monkeypatch.setattr(
        "narration_service.NarrationService.preparar",
        preparar,
    )

    resultado = asyncio.run(worker.process_job(job))

    assert len(job.artifacts) == 1

    artifact = job.artifacts[0]

    assert artifact.role == "output"
    assert artifact.filename == "narracao.mp3"
    assert artifact.media_type == "audio/mpeg"
    assert artifact.relative_path == relativo

    assert job.dados["duracao_real"] == 12.5
    assert job.dados["duracao_alvo"] == 15
    assert job.dados["tentativas_narracao"] == 2
    assert job.dados["narracao"] == (
        "Venha apreciar nossa música."
    )

    assert "Locução aprovada!" in resultado
    assert "12.50" in resultado
    preparar.assert_awaited_once()


def test_avatar_sem_audio(ambiente, monkeypatch):
    worker, runner, store = ambiente

    preparar = AsyncMock()

    monkeypatch.setattr(
        "narration_service.NarrationService.preparar",
        preparar,
    )

    job = criar_job(False)

    resultado = asyncio.run(worker.process_job(job))

    assert "Narração pronta:" in resultado
    assert not job.artifacts
    preparar.assert_not_awaited()


def test_narracao_reprovada(ambiente, monkeypatch):
    worker, runner, store = ambiente

    preparar = AsyncMock(
        side_effect=NarrationError(
            "Narração não aprovada."
        )
    )

    monkeypatch.setattr(
        "narration_service.NarrationService.preparar",
        preparar,
    )

    job = criar_job()

    with pytest.raises(NarrationError):
        asyncio.run(worker.process_job(job))

    assert not job.artifacts
    assert "duracao_real" not in job.dados


def test_audio_sem_duracao(ambiente):
    worker, runner, store = ambiente

    job = criar_job()
    job.descricao = "Texto avatar com áudio"

    with pytest.raises(ValueError):
        asyncio.run(worker.process_job(job))

    runner.run.assert_not_awaited()
    assert not job.artifacts
