"""Testes do NarrationService premium."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from artifact_store import ArtifactStore
from job import Job
from narration_service import NarrationService, NarrationError
from paid_task_guard import PaidTaskGuard


def criar_job():
    return Job(
        chat_id=1,
        fila="mkitextos",
        tipo="texto",
        skill="texto_avatar",
        titulo="Teste premium",
        descricao="Texto avatar de 15 segundos",
    )


def resposta(texto):
    return (
        "Titulo: Teste\n"
        "Narração pronta:\n"
        f"{texto}\n"
        "Palavras da narração: 5\n"
        "Duração estimada: 15 segundos\n"
    )


@pytest.fixture
def ambiente(monkeypatch, tmp_path):
    runner = AsyncMock()
    cliente = AsyncMock()
    store = ArtifactStore(tmp_path / "artifacts")
    guard = PaidTaskGuard(tmp_path / "paid_tasks.db")

    async def fake_premium(**kwargs):
        arquivo = kwargs["output_path"]
        arquivo.write_bytes(b"audio premium simulado")

        return {
            "task_id": "kie-teste-premium",
            "arquivo": arquivo,
            "duracao_real": 12.5,
        }

    gerar = AsyncMock(side_effect=fake_premium)

    monkeypatch.setattr(
        "narration_service.gerar_narracao_premium",
        gerar,
    )

    service = NarrationService(runner, store)

    return service, runner, gerar, guard, cliente


def test_sem_autorizacao(ambiente):
    service, runner, gerar, guard, cliente = ambiente

    with pytest.raises(PermissionError):
        asyncio.run(
            service.preparar_premium(
                criar_job(),
                resposta("Venha apreciar nossa musica."),
                guard,
                cliente,
            )
        )

    gerar.assert_not_awaited()
    runner.run.assert_not_awaited()


def test_premium_aprovado(ambiente):
    service, runner, gerar, guard, cliente = ambiente

    resultado = asyncio.run(
        service.preparar_premium(
            criar_job(),
            resposta("Venha apreciar nossa musica."),
            guard,
            cliente,
            autorizado=True,
        )
    )

    assert resultado.motor == "elevenlabs"
    assert resultado.aprovado is True
    assert resultado.duracao_real == 12.5
    assert resultado.task_id == "kie-teste-premium"
    assert resultado.audio_path.is_file()
    assert resultado.audio_path.name == "narracao-premium.mp3"
    assert resultado.tentativas == 1

    gerar.assert_awaited_once()
    runner.run.assert_not_awaited()


def test_revisao_antes_da_geracao(ambiente):
    service, runner, gerar, guard, cliente = ambiente

    runner.run.return_value = resposta(
        "Venha apreciar nossa musica."
    )

    resultado = asyncio.run(
        service.preparar_premium(
            criar_job(),
            resposta("musica " * 50),
            guard,
            cliente,
            autorizado=True,
        )
    )

    assert resultado.tentativas == 2
    assert resultado.aprovado is True

    runner.run.assert_awaited_once()
    gerar.assert_awaited_once()

    assert gerar.await_args.kwargs["texto"] == (
        "Venha apreciar nossa musica."
    )


@pytest.mark.parametrize("duracao", [7.0, 18.2])
def test_duracao_fora_do_limite(ambiente, duracao):
    service, runner, gerar, guard, cliente = ambiente

    async def fake_audio(**kwargs):
        arquivo = kwargs["output_path"]
        arquivo.write_bytes(b"audio preservado")
        return {
            "task_id": "kie-preservado",
            "arquivo": arquivo,
            "duracao_real": duracao,
        }

    gerar.side_effect = fake_audio

    resultado = asyncio.run(
        service.preparar_premium(
            criar_job(),
            resposta("Venha apreciar nossa musica."),
            guard,
            cliente,
            autorizado=True,
        )
    )

    assert resultado.aprovado is False
    assert resultado.audio_path.is_file()
    assert resultado.duracao_real == duracao
    assert resultado.observacao
    assert resultado.task_id == "kie-preservado"
    gerar.assert_awaited_once()
    runner.run.assert_not_awaited()


def test_texto_invalido(ambiente):
    service, runner, gerar, guard, cliente = ambiente
    runner.run.return_value = resposta("musica " * 50)

    with pytest.raises(NarrationError):
        asyncio.run(
            service.preparar_premium(
                criar_job(),
                resposta("musica " * 50),
                guard,
                cliente,
                autorizado=True,
            )
        )

    gerar.assert_not_awaited()
    assert runner.run.await_count == 2


def test_falha_kie_sem_repeticao(ambiente):
    service, runner, gerar, guard, cliente = ambiente
    gerar.side_effect = TimeoutError("Falha simulada KIE")

    with pytest.raises(TimeoutError):
        asyncio.run(
            service.preparar_premium(
                criar_job(),
                resposta("Venha apreciar nossa musica."),
                guard,
                cliente,
                autorizado=True,
            )
        )

    gerar.assert_awaited_once()
    runner.run.assert_not_awaited()


def test_duracao_nao_informada(ambiente):
    service, runner, gerar, guard, cliente = ambiente
    job = criar_job()
    job.descricao = "Texto avatar premium"

    with pytest.raises(NarrationError):
        asyncio.run(
            service.preparar_premium(
                job,
                resposta("Venha apreciar nossa musica."),
                guard,
                cliente,
                autorizado=True,
            )
        )

    gerar.assert_not_awaited()
    runner.run.assert_not_awaited()
