"""Testes da preparação inteligente de narrações."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from artifact_store import ArtifactStore
from job import Job
from narration_service import (
    NarrationService,
    NarrationError,
)


def criar_job():
    return Job(
        chat_id=1,
        fila="mkitextos",
        tipo="texto",
        skill="texto_avatar",
        titulo="Teste de narração",
        descricao="Texto avatar de 15 segundos",
    )


def resposta(texto):
    return (
        "Título: Teste\n"
        "Narração pronta:\n"
        f"{texto}\n"
        "Palavras da narração: 5\n"
        "Duração estimada: 15 segundos\n"
    )


@pytest.fixture
def ambiente(monkeypatch, tmp_path):
    runner = AsyncMock()
    store = ArtifactStore(tmp_path)

    async def fake_gerar_voz(
        texto, output_path, voz
    ):
        output_path.write_bytes(b"audio simulado")
        return output_path

    gerar = AsyncMock(side_effect=fake_gerar_voz)
    medir = AsyncMock()

    monkeypatch.setattr(
        "narration_service.gerar_voz", gerar
    )

    monkeypatch.setattr(
        "narration_service.medir_duracao", medir
    )

    service = NarrationService(runner, store)

    return service, runner, gerar, medir


def test_aprovado_primeira_tentativa(ambiente):
    service, runner, gerar, medir = ambiente
    medir.return_value = 11.304

    job = criar_job()

    resultado = asyncio.run(
        service.preparar(
            job,
            resposta("Venha apreciar nossa apresentação musical."),
        )
    )

    assert resultado.tentativas == 1
    assert resultado.duracao_real == 11.304
    assert resultado.audio_path.is_file()
    assert resultado.audio_path.name == "narracao.mp3"
    assert gerar.await_count == 1
    runner.run.assert_not_awaited()


@pytest.mark.parametrize(
    "duracao, acao",
    [
        (18.2, "reduzir"),
        (7.0, "ampliar"),
    ],
)
def test_revisao_automatica(ambiente, duracao, acao):
    service, runner, gerar, medir = ambiente

    medir.side_effect = [duracao, 13.7]

    runner.run.return_value = resposta(
        "Venha viver uma experiência musical especial."
    )

    job = criar_job()
    descricao_original = job.descricao

    resultado = asyncio.run(
        service.preparar(
            job,
            resposta("Venha apreciar nossa música."),
        )
    )

    assert resultado.tentativas == 2
    assert resultado.duracao_real == 13.7
    assert gerar.await_count == 2
    assert runner.run.await_count == 1

    revisao = runner.run.await_args.args[0]

    assert acao in revisao.descricao
    assert job.descricao == descricao_original
    assert resultado.audio_path.is_file()


def test_limite_de_tentativas(ambiente):
    service, runner, gerar, medir = ambiente

    medir.return_value = 20

    runner.run.return_value = resposta(
        "Venha apreciar nossa música."
    )

    job = criar_job()

    with pytest.raises(NarrationError):
        asyncio.run(
            service.preparar(
                job,
                resposta("Venha apreciar nossa música."),
            )
        )

    assert gerar.await_count == 3
    assert runner.run.await_count == 2

    pasta = service.artifact_store.root / job.id

    assert not (pasta / "narracao.mp3").exists()
    assert not (
        pasta / "narracao-temporaria.mp3"
    ).exists()


def test_falha_tts_interrompe(ambiente):
    service, runner, gerar, medir = ambiente

    gerar.side_effect = RuntimeError(
        "Falha simulada no Edge TTS"
    )

    with pytest.raises(RuntimeError):
        asyncio.run(
            service.preparar(
                criar_job(),
                resposta("Venha apreciar nossa música."),
            )
        )

    medir.assert_not_awaited()
    runner.run.assert_not_awaited()


def test_texto_longo_revisado_antes_do_audio(ambiente):
    service, runner, gerar, medir = ambiente

    medir.return_value = 12

    runner.run.return_value = resposta(
        "Venha apreciar nossa apresentação musical."
    )

    resultado = asyncio.run(
        service.preparar(
            criar_job(),
            resposta("musica " * 50),
        )
    )

    assert resultado.tentativas == 2
    assert gerar.await_count == 1
    assert runner.run.await_count == 1


def test_duracao_nao_informada(ambiente):
    service, runner, gerar, medir = ambiente

    job = criar_job()
    job.descricao = "Crie um texto avatar"

    with pytest.raises(NarrationError):
        asyncio.run(
            service.preparar(
                job,
                resposta("Venha apreciar nossa música."),
            )
        )

    gerar.assert_not_awaited()
    medir.assert_not_awaited()


@pytest.mark.parametrize(
    "duracao, quantidade, meta",
    [
        (9.456, 20, 27),
        (18.2, 28, 20),
        (7.0, 25, 28),
    ],
)
def test_meta_adaptativa(
    ambiente, duracao, quantidade, meta
):
    service, runner, gerar, medir = ambiente

    medir.side_effect = [duracao, 12.75]

    runner.run.return_value = resposta(
        "musica " * meta
    )

    resultado = asyncio.run(
        service.preparar(
            criar_job(),
            resposta("musica " * quantidade),
        )
    )

    revisao = runner.run.await_args.args[0]

    assert f"Nova meta: {meta} palavras." in revisao.descricao

    assert (
        f"{quantidade} palavras."
        in revisao.descricao
    )

    assert "Velocidade real observada:" in revisao.descricao
    assert resultado.tentativas == 2
    assert resultado.duracao_real == 12.75
    assert gerar.await_count == 2
    assert runner.run.await_count == 1


def test_audio_aprovado_sem_revisao_adaptativa(ambiente):
    service, runner, gerar, medir = ambiente

    medir.return_value = 12.75

    resultado = asyncio.run(
        service.preparar(
            criar_job(),
            resposta("musica " * 25),
        )
    )

    assert resultado.tentativas == 1
    assert resultado.duracao_real == 12.75
    assert gerar.await_count == 1

    runner.run.assert_not_awaited()


def test_log_das_tentativas(ambiente, caplog):
    service, runner, gerar, medir = ambiente

    caplog.set_level(
        "INFO", logger="narration_service"
    )

    medir.side_effect = [9.456, 12.75]

    runner.run.return_value = resposta(
        "musica " * 27
    )

    job = criar_job()

    asyncio.run(
        service.preparar(
            job,
            resposta("musica " * 20),
        )
    )

    assert job.id in caplog.text
    assert "Narracao 1/3" in caplog.text
    assert "Narracao 2/3" in caplog.text
    assert "Palavras=20" in caplog.text
    assert "Palavras=27" in caplog.text
    assert "Audio=9.456s" in caplog.text
    assert "Audio=12.750s" in caplog.text
    assert "Resultado=ampliar" in caplog.text
    assert "Resultado=aprovado" in caplog.text
