"""Testes de recuperacao ElevenLabs."""

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
    mock.aguardar_resultado.return_value = (
        "https://example.com/audio.mp3"
    )
    return mock


@pytest.mark.asyncio
async def test_recuperacao(
    guard, cliente, tmp_path, monkeypatch
):
    guard.reservar("job-1", service.MODELO_ELEVENLABS)
    guard.registrar_task_id("job-1", "kie-existente")

    audio = tmp_path / "audio.mp3"
    cliente.baixar_resultado.return_value = audio

    monkeypatch.setattr(
        service,
        "validar_audio_mp3",
        AsyncMock(return_value=13.2),
    )

    resultado = await service.recuperar_narracao_premium(
        "job-1", audio, guard, cliente
    )

    assert resultado["recuperado"] is True
    assert resultado["task_id"] == "kie-existente"
    assert resultado["duracao_real"] == 13.2
    assert resultado["arquivo"] == audio

    cliente.criar_tarefa.assert_not_called()
    cliente.aguardar_resultado.assert_awaited_once_with(
        "kie-existente"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cenario", ["inexistente", "sem_id", "outro_modelo"]
)
async def test_bloqueio(
    guard, cliente, tmp_path, cenario
):
    if cenario == "sem_id":
        guard.reservar("job-2", service.MODELO_ELEVENLABS)

    elif cenario == "outro_modelo":
        guard.reservar("job-2", "outro-modelo")
        guard.registrar_task_id("job-2", "kie-outro")

    with pytest.raises(PaidTaskError):
        await service.recuperar_narracao_premium(
            "job-2",
            tmp_path / "audio.mp3",
            guard,
            cliente,
        )

    cliente.criar_tarefa.assert_not_called()
    cliente.aguardar_resultado.assert_not_called()
    cliente.baixar_resultado.assert_not_called()


@pytest.mark.asyncio
async def test_falha_download(
    guard, cliente, tmp_path
):
    guard.reservar("job-3", service.MODELO_ELEVENLABS)
    guard.registrar_task_id("job-3", "kie-preservado")

    cliente.baixar_resultado.side_effect = TimeoutError(
        "Falha simulada"
    )

    with pytest.raises(TimeoutError):
        await service.recuperar_narracao_premium(
            "job-3",
            tmp_path / "audio.mp3",
            guard,
            cliente,
        )

    registro = guard.consultar("job-3")

    assert registro["task_id"] == "kie-preservado"
    assert registro["state"] == "submitted"

    cliente.criar_tarefa.assert_not_called()
