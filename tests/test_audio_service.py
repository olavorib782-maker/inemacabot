"""Testes do serviço compartilhado de áudio."""

import asyncio
from pathlib import Path

import pytest

from audio_service import (
    gerar_voz,
    medir_duracao,
    validar_duracao,
)


@pytest.mark.parametrize(
    "real, alvo, esperado, motivo",
    [
        (11.304, 15, True, "aprovado"),
        (15, 15, True, "aprovado"),
        (10.5, 15, True, "aprovado"),
        (10.49, 15, False, "ampliar"),
        (8, 15, False, "ampliar"),
        (15.01, 15, False, "reduzir"),
        (20, 15, False, "reduzir"),
        (30, 30, True, "aprovado"),
    ],
)
def test_validar_duracao(real, alvo, esperado, motivo):
    assert validar_duracao(real, alvo) == (
        esperado, motivo
    )


@pytest.mark.parametrize(
    "real, alvo",
    [
        (0, 15),
        (-1, 15),
        (10, 0),
        (10, -1),
        (float("nan"), 15),
        (float("inf"), 15),
        (10, float("nan")),
        (10, float("inf")),
    ],
)
def test_duracao_invalida(real, alvo):
    with pytest.raises(ValueError):
        validar_duracao(real, alvo)


@pytest.mark.parametrize(
    "proporcao",
    [0, -0.5, 1.1, float("nan")],
)
def test_proporcao_invalida(proporcao):
    with pytest.raises(ValueError):
        validar_duracao(11, 15, proporcao)


def test_proporcao_personalizada():
    assert validar_duracao(9, 15, 0.60) == (
        True, "aprovado"
    )


def test_gerar_voz_texto_vazio(tmp_path):
    with pytest.raises(ValueError):
        asyncio.run(
            gerar_voz("   ", tmp_path / "voz.mp3")
        )


def test_medir_arquivo_inexistente(tmp_path):
    with pytest.raises(FileNotFoundError):
        asyncio.run(
            medir_duracao(tmp_path / "inexistente.mp3")
        )


def test_gerar_voz_simulada(monkeypatch, tmp_path):
    class FakeCommunicate:
        def __init__(self, text, voice, rate):
            assert text == "Teste de voz"
            assert voice == "pt-BR-AntonioNeural"
            assert rate == "-8%"

        async def save(self, path):
            Path(path).write_bytes(b"audio simulado")

    monkeypatch.setattr(
        "audio_service.edge_tts.Communicate",
        FakeCommunicate,
    )

    saida = tmp_path / "voz.mp3"

    resultado = asyncio.run(
        gerar_voz("Teste de voz", saida)
    )

    assert resultado == saida
    assert saida.stat().st_size > 0


def test_medir_duracao_simulada(monkeypatch, tmp_path):
    class FakeProcess:
        returncode = 0

        async def communicate(self):
            return b"11.304000", b""

    async def fake_subprocess(*args, **kwargs):
        assert args[0] == "ffprobe"
        return FakeProcess()

    monkeypatch.setattr(
        "audio_service.asyncio.create_subprocess_exec",
        fake_subprocess,
    )

    arquivo = tmp_path / "voz.mp3"
    arquivo.write_bytes(b"audio simulado")

    assert asyncio.run(
        medir_duracao(arquivo)
    ) == pytest.approx(11.304)

@pytest.mark.parametrize(
    "falhas, intervalos_esperados",
    [
        (1, [2]),
        (2, [2, 5]),
    ],
)
def test_recuperacao_edge_tts(
    monkeypatch, tmp_path, falhas, intervalos_esperados
):
    from edge_tts.exceptions import NoAudioReceived

    chamadas = []
    intervalos = []

    class FakeCommunicate:
        def __init__(self, text, voice, rate):
            chamadas.append((text, voice, rate))

        async def save(self, path):
            if len(chamadas) <= falhas:
                Path(path).write_bytes(b"audio incompleto")
                raise NoAudioReceived("Falha simulada")

            assert not Path(path).exists()
            Path(path).write_bytes(b"audio completo")

    async def fake_sleep(segundos):
        intervalos.append(segundos)

    monkeypatch.setattr(
        "audio_service.edge_tts.Communicate",
        FakeCommunicate,
    )
    monkeypatch.setattr(
        "audio_service.asyncio.sleep",
        fake_sleep,
    )

    saida = tmp_path / "voz.mp3"

    resultado = asyncio.run(
        gerar_voz("Teste de recuperacao", saida)
    )

    assert resultado == saida
    assert len(chamadas) == falhas + 1
    assert len(set(chamadas)) == 1
    assert intervalos == intervalos_esperados
    assert saida.read_bytes() == b"audio completo"
    assert not (tmp_path / "voz.mp3.part").exists()


@pytest.mark.parametrize(
    "tipo_falha",
    ["sem_audio", "timeout", "conexao", "arquivo_vazio"],
)
def test_recuperacao_por_tipo_de_falha(
    monkeypatch, tmp_path, tipo_falha
):
    import aiohttp
    from edge_tts.exceptions import NoAudioReceived

    chamadas = []

    class FakeCommunicate:
        def __init__(self, text, voice, rate):
            chamadas.append(text)

        async def save(self, path):
            if len(chamadas) == 1:
                if tipo_falha == "sem_audio":
                    raise NoAudioReceived("Sem audio")

                if tipo_falha == "timeout":
                    raise asyncio.TimeoutError()

                if tipo_falha == "conexao":
                    raise aiohttp.ClientConnectionError()

                Path(path).write_bytes(b"")
                return

            Path(path).write_bytes(b"audio recuperado")

    async def fake_sleep(segundos):
        pass

    monkeypatch.setattr(
        "audio_service.edge_tts.Communicate",
        FakeCommunicate,
    )
    monkeypatch.setattr(
        "audio_service.asyncio.sleep",
        fake_sleep,
    )

    saida = tmp_path / "voz.mp3"

    asyncio.run(gerar_voz("Teste", saida))

    assert len(chamadas) == 2
    assert saida.read_bytes() == b"audio recuperado"
    assert not (tmp_path / "voz.mp3.part").exists()


def test_edge_tts_esgota_tentativas(
    monkeypatch, tmp_path
):
    from edge_tts.exceptions import NoAudioReceived

    chamadas = []
    intervalos = []

    class FakeCommunicate:
        def __init__(self, text, voice, rate):
            chamadas.append(text)

        async def save(self, path):
            Path(path).write_bytes(b"incompleto")
            raise NoAudioReceived("Falha persistente")

    async def fake_sleep(segundos):
        intervalos.append(segundos)

    monkeypatch.setattr(
        "audio_service.edge_tts.Communicate",
        FakeCommunicate,
    )
    monkeypatch.setattr(
        "audio_service.asyncio.sleep",
        fake_sleep,
    )

    saida = tmp_path / "voz.mp3"

    with pytest.raises(
        RuntimeError,
        match="falhou apos 3 tentativas",
    ):
        asyncio.run(gerar_voz("Teste", saida))

    assert len(chamadas) == 3
    assert intervalos == [2, 5]
    assert not saida.exists()
    assert not (tmp_path / "voz.mp3.part").exists()


def test_edge_tts_erro_permanente_sem_retry(
    monkeypatch, tmp_path
):
    chamadas = []

    class FakeCommunicate:
        def __init__(self, text, voice, rate):
            chamadas.append(text)
            raise ValueError("Parametro invalido")

    monkeypatch.setattr(
        "audio_service.edge_tts.Communicate",
        FakeCommunicate,
    )

    saida = tmp_path / "voz.mp3"

    with pytest.raises(ValueError):
        asyncio.run(gerar_voz("Teste", saida))

    assert len(chamadas) == 1
    assert not saida.exists()
    assert not (tmp_path / "voz.mp3.part").exists()
