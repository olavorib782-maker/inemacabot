from __future__ import annotations

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


def test_router_ignora_maiusculas_e_minusculas() -> None:
    decision = Router().route("QUERO UM VÍDEO EXPLICATIVO")
    assert decision.is_job is True
    assert decision.skill == "video_explicativo"


def test_pedido_nao_reconhecido_nao_e_forcado_para_fila() -> None:
    decision = Router().route("asdfgh")
    assert decision.is_job is False
    assert decision.fila is None
