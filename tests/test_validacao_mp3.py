"""Testes locais de validacao MP3."""

import subprocess

import pytest

from audio_service import validar_audio_mp3


@pytest.fixture
def mp3_valido(tmp_path):
    arquivo = tmp_path / "valido.mp3"

    subprocess.run(
        [
            "ffmpeg", "-v", "error",
            "-f", "lavfi",
            "-i", "sine=frequency=440:duration=2",
            "-c:a", "libmp3lame",
            str(arquivo),
        ],
        check=True,
    )

    return arquivo


@pytest.mark.asyncio
async def test_mp3_valido(mp3_valido):
    duracao = await validar_audio_mp3(mp3_valido)

    assert 1.9 <= duracao <= 2.2


@pytest.mark.asyncio
async def test_arquivo_inexistente(tmp_path):
    with pytest.raises(FileNotFoundError):
        await validar_audio_mp3(
            tmp_path / "inexistente.mp3"
        )


@pytest.mark.asyncio
async def test_arquivo_vazio(tmp_path):
    arquivo = tmp_path / "vazio.mp3"
    arquivo.touch()

    with pytest.raises(RuntimeError):
        await validar_audio_mp3(arquivo)


@pytest.mark.asyncio
async def test_arquivo_invalido(tmp_path):
    arquivo = tmp_path / "invalido.mp3"
    arquivo.write_text("Isto nao e um audio.")

    with pytest.raises(RuntimeError):
        await validar_audio_mp3(arquivo)


@pytest.mark.asyncio
async def test_wav_disfarcado(tmp_path):
    arquivo = tmp_path / "falso.mp3"

    subprocess.run(
        [
            "ffmpeg", "-v", "error",
            "-f", "lavfi",
            "-i", "sine=frequency=440:duration=2",
            "-c:a", "pcm_s16le",
            "-f", "wav",
            str(arquivo),
        ],
        check=True,
    )

    with pytest.raises(
        RuntimeError, match="Formato recebido"
    ):
        await validar_audio_mp3(arquivo)
