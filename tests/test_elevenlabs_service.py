"""Testes da integracao ElevenLabs sem consumo de creditos."""

from unittest.mock import AsyncMock

import pytest

import elevenlabs_service as service

from paid_task_guard import PaidTaskGuard, PaidTaskError


@pytest.fixture
def guard(tmp_path):
    return PaidTaskGuard(tmp_path / "paid_tasks.db")


@pytest.fixture
def cliente():
    mock = AsyncMock()
    mock.criar_tarefa.return_value = "kie-teste-123"
    mock.aguardar_resultado.return_value = (
        "https://example.com/audio.mp3"
    )
    return mock


def test_parametros_brian():
    dados = service.preparar_parametros("Ola!")

    assert dados["dialogue"][0]["text"] == "Ola!"
    assert dados["dialogue"][0]["voice"] == service.VOZ_BRIAN
    assert dados["stability"] == 0.5
    assert dados["language_code"] == "pt"


@pytest.mark.parametrize("texto", ["", "   ", "a" * 5001])
def test_texto_invalido(texto):
    with pytest.raises(ValueError):
        service.preparar_parametros(texto)


@pytest.mark.asyncio
async def test_sem_autorizacao(guard, cliente, tmp_path):
    with pytest.raises(PermissionError):
        await service.gerar_narracao_premium(
            "job-1",
            "Teste de voz",
            tmp_path / "audio.mp3",
            guard,
            cliente,
        )

    cliente.criar_tarefa.assert_not_called()
    assert guard.consultar("job-1") is None


@pytest.mark.asyncio
async def test_geracao_premium(
    guard, cliente, tmp_path, monkeypatch
):
    audio = tmp_path / "audio.mp3"
    cliente.baixar_resultado.return_value = audio

    monkeypatch.setattr(
        service,
        "validar_audio_mp3",
        AsyncMock(return_value=12.5),
    )

    resultado = await service.gerar_narracao_premium(
        "job-2",
        "Teste de voz",
        audio,
        guard,
        cliente,
        autorizado=True,
    )

    assert resultado["task_id"] == "kie-teste-123"
    assert resultado["duracao_real"] == 12.5
    assert resultado["arquivo"] == audio

    cliente.criar_tarefa.assert_awaited_once()
    cliente.aguardar_resultado.assert_awaited_once_with(
        "kie-teste-123"
    )

    assert guard.consultar("job-2")["state"] == "submitted"


@pytest.mark.asyncio
async def test_duplicidade(guard, cliente, tmp_path):
    guard.reservar("job-3", service.MODELO_ELEVENLABS)

    with pytest.raises(PaidTaskError):
        await service.gerar_narracao_premium(
            "job-3",
            "Teste de voz",
            tmp_path / "audio.mp3",
            guard,
            cliente,
            autorizado=True,
        )

    cliente.criar_tarefa.assert_not_called()


@pytest.mark.asyncio
async def test_falha_envio_sem_repeticao(
    guard, cliente, tmp_path
):
    cliente.criar_tarefa.side_effect = TimeoutError(
        "Falha simulada"
    )

    argumentos = (
        "job-4",
        "Teste de voz",
        tmp_path / "audio.mp3",
        guard,
        cliente,
    )

    with pytest.raises(TimeoutError):
        await service.gerar_narracao_premium(
            *argumentos, autorizado=True
        )

    assert guard.consultar("job-4")["state"] == "reserved"

    with pytest.raises(PaidTaskError):
        await service.gerar_narracao_premium(
            *argumentos, autorizado=True
        )

    cliente.criar_tarefa.assert_awaited_once()
