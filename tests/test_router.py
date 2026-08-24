from __future__ import annotations

import pytest

from router import Router


def test_conversa_normal_nao_vira_job() -> None:
    decision = Router().route("Bom dia, Inemaca!")
    assert decision.is_job is False


def test_video_vai_para_mkivideos() -> None:
    decision = Router().route("Quero criar um vídeo explicativo sobre agentes de IA")
    assert decision.is_job is True
    assert decision.fila == "mkivideos"
    assert decision.tipo == "video"
    assert decision.skill == "video_explicativo"


def test_roteiro_vai_para_mkitextos() -> None:
    decision = Router().route("Preciso de um roteiro para um vídeo")
    assert decision.is_job is True
    assert decision.fila == "mkitextos"
    assert decision.tipo == "texto"
    assert decision.skill == "roteiro"


def test_pesquisa_vai_para_mkiservicos() -> None:
    decision = Router().route("Pesquise ferramentas gratuitas para edição de vídeo")
    assert decision.is_job is True
    assert decision.fila == "mkiservicos"
    assert decision.tipo == "servico"
    assert decision.skill == "pesquisa"


@pytest.mark.parametrize(
    "message",
    ["ls para musicxml", "converter leadsheet", "converter para musicxml"],
)
def test_intencao_musical_especifica_vai_para_mkimusica(message: str) -> None:
    decision = Router().route(message)
    assert decision.is_job is True
    assert decision.fila == "mkimusica"
    assert decision.tipo == "musica"
    assert decision.skill == "leadsheet_para_musicxml"


@pytest.mark.parametrize(
    "message",
    [
        "guide tones para Dm7 | G7",
        "Crie guide tones para Dm7 | G7 | Cmaj7 | Cmaj7",
        "Gere guide tones para D/F# | G7/B",
    ],
)
def test_intencao_guide_tones_explicita_vai_para_mkimusica(message: str) -> None:
    decision = Router().route(message)

    assert decision.is_job is True
    assert decision.fila == "mkimusica"
    assert decision.tipo == "musica"
    assert decision.skill == "guide_tones"


@pytest.mark.parametrize("message", ["quero ouvir música", "mostre uma partitura"])
def test_termos_musicais_genericos_nao_sao_roteados(message: str) -> None:
    assert Router().route(message).is_job is False


def test_router_ignora_maiusculas_e_minusculas() -> None:
    decision = Router().route("QUERO UM VÍDEO EXPLICATIVO")
    assert decision.is_job is True
    assert decision.skill == "video_explicativo"


def test_pedido_nao_reconhecido_nao_e_forcado_para_fila() -> None:
    decision = Router().route("asdfgh")
    assert decision.is_job is False
    assert decision.fila is None
