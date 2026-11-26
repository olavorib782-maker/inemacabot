import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from artifact_store import ArtifactStore
from job import Job
from narration_service import NarrationResult
from queue_manager import QueueManager
from workers.text_worker import TextWorker


def criar_job(premium=True, autorizado=True):
    dados = {"gerar_audio": True}
    if premium:
        dados["motor_voz"] = "elevenlabs"
        dados["premium_autorizado"] = autorizado

    return Job(
        42, "mkitextos", "texto", "texto_avatar",
        "Apresentacao", "Texto avatar de 15 segundos",
        dados=dados,
    )


def criar_resultado(tmp_path, premium=True, aprovado=True):
    nome = "narracao-premium.mp3" if premium else "narracao.mp3"
    audio = tmp_path / nome
    audio.write_bytes(b"audio simulado")

    return NarrationResult(
        resposta="Narração pronta: A música transforma vidas.",
        texto="A música transforma vidas.",
        relative_path=nome,
        audio_path=audio,
        duracao_real=12.5 if aprovado else 18.2,
        duracao_alvo=15,
        tentativas=1,
        motor="elevenlabs" if premium else "edge_tts",
        aprovado=aprovado,
        observacao="" if aprovado else "Duracao fora do intervalo.",
        task_id="kie-teste-123" if premium else None,
    )


@pytest.mark.parametrize(
    "premium, aprovado",
    [(True, True), (True, False), (False, True)],
)
def test_worker_entrega_audio(tmp_path, monkeypatch, premium, aprovado):
    async def scenario():
        resultado = criar_resultado(tmp_path, premium, aprovado)
        runner = Mock()
        runner.run = AsyncMock(return_value=resultado.resposta)

        service = Mock()
        service.preparar = AsyncMock(return_value=resultado)
        service.preparar_premium = AsyncMock(return_value=resultado)

        monkeypatch.setattr(
            "workers.text_worker.NarrationService",
            Mock(return_value=service),
        )
        cliente = Mock()
        monkeypatch.setattr("workers.text_worker.KieClient", cliente)

        worker = TextWorker(
            QueueManager(),
            agent_runner=runner,
            artifact_store=ArtifactStore(tmp_path),
            paid_tasks_db_path=tmp_path / "paid_tasks.db",
        )

        job = criar_job(premium=premium)
        mensagem = await worker.process_job(job)

        assert job.artifacts[0].filename == resultado.audio_path.name
        assert job.dados["motor_voz"] == resultado.motor
        assert job.dados["narracao_aprovada"] is aprovado
        assert ("Locução aprovada!" in mensagem) is aprovado

        if premium:
            service.preparar_premium.assert_awaited_once()
            service.preparar.assert_not_awaited()
            assert job.dados["kie_task_id"] == resultado.task_id
        else:
            service.preparar.assert_awaited_once()
            service.preparar_premium.assert_not_awaited()
            cliente.assert_not_called()

        if not aprovado:
            assert resultado.observacao in mensagem
            assert resultado.audio_path.exists()

    asyncio.run(scenario())


def test_worker_bloqueia_premium_sem_autorizacao(tmp_path, monkeypatch):
    async def scenario():
        runner = Mock()
        runner.run = AsyncMock(return_value="Narracao de teste.")

        cliente = Mock()
        guard = Mock()

        monkeypatch.setattr("workers.text_worker.KieClient", cliente)
        monkeypatch.setattr("workers.text_worker.PaidTaskGuard", guard)

        worker = TextWorker(
            QueueManager(),
            agent_runner=runner,
            artifact_store=ArtifactStore(tmp_path),
            paid_tasks_db_path=tmp_path / "paid_tasks.db",
        )

        job = criar_job(premium=True, autorizado=False)

        with pytest.raises(PermissionError, match="nao autorizada"):
            await worker.process_job(job)

        cliente.assert_not_called()
        guard.assert_not_called()
        assert not job.artifacts
        assert not (tmp_path / "paid_tasks.db").exists()

    asyncio.run(scenario())
