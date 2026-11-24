
from roteiro_validator import (
    extrair_duracao,
    extrair_narracao,
    contar_palavras,
    validar_roteiro,
)


def test_extrair_duracao():
    assert extrair_duracao("Roteiro de 20 segundos") == 20
    assert extrair_duracao("Vídeo de 2 minutos") == 120
    assert extrair_duracao("Roteiro sem tempo definido") is None


def test_extrair_narracao():
    resposta = """Título: Apresentação

Narração pronta:
Bem-vindos a esta noite especial.

Palavras da narração: 6

Sugestões visuais:
- Palco iluminado.
"""
    assert extrair_narracao(resposta) == (
        "Bem-vindos a esta noite especial."
    )


def test_contar_palavras():
    assert contar_palavras("Boa noite, [Nome do Artista]!") == 5


def test_roteiro_dentro_do_limite():
    resposta = """Título: Apresentação

Narração pronta:
Boa noite! Recebam com carinho nosso saxofonista.

Palavras da narração: 7
"""
    aprovado, mensagem = validar_roteiro(
        "Crie um roteiro de 20 segundos",
        resposta,
    )

    assert aprovado is True
    assert "validada" in mensagem


def test_roteiro_acima_do_limite():
    narracao = " ".join(["música"] * 45)

    resposta = f"""Título: Apresentação

Narração pronta:
{narracao}

Palavras da narração: 45
"""
    aprovado, mensagem = validar_roteiro(
        "Crie um roteiro de 20 segundos",
        resposta,
    )

    assert aprovado is False
    assert "45 palavras" in mensagem
    assert "38" in mensagem


def test_roteiro_sem_narracao():
    aprovado, mensagem = validar_roteiro(
        "Crie um roteiro de 20 segundos",
        "Título: Apresentação",
    )

    assert aprovado is False
    assert "Não foi possível identificar" in mensagem
