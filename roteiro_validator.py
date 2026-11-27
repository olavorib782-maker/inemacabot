
"""Validação de duração de roteiros para locução."""

from __future__ import annotations

import re


LIMITES = {
    10: 18,
    15: 28,
    20: 38,
    30: 55,
    45: 85,
    60: 110,
}


def extrair_duracao(descricao: str) -> int | None:
    """Identifica a duração solicitada em segundos."""
    match = re.search(
        r"\b(\d+)\s*(segundos?|segs?|s)\b",
        descricao,
        flags=re.IGNORECASE,
    )
    if match:
        return int(match.group(1))

    match = re.search(
        r"\b(\d+)\s*(minutos?|mins?)\b",
        descricao,
        flags=re.IGNORECASE,
    )
    if match:
        return int(match.group(1)) * 60

    return None


def limite_palavras(segundos: int) -> int:
    """Calcula o limite de palavras da narração."""
    if segundos <= 0:
        raise ValueError("A duração deve ser positiva.")

    if segundos in LIMITES:
        return LIMITES[segundos]

    return max(1, int(segundos * 110 / 60))


def extrair_narracao(resposta: str) -> str | None:
    """Extrai a narracao com suporte a variacoes Markdown."""
    prefixo = r"^[ \t]*(?:#{1,6}[ \t]+)?\*{0,2}"
    sufixo = r"\*{0,2}[ \t]*:\*{0,2}[ \t]*"

    padrao = (
        prefixo
        + r"Narração(?:[ \t]+pronta)?"
        + sufixo
        + r"(.*?)"
        + r"(?="
        + prefixo
        + r"(?:Palavras da narração|Duração estimada|"
          r"Sugestões visuais|Trilha sonora|"
          r"Título|Duração solicitada|Narração(?: pronta)?)"
        + sufixo
        + r"|\Z)"
    )

    match = re.search(
        padrao,
        resposta,
        flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )

    if not match:
        return None

    return match.group(1).strip() or None


def contar_palavras(texto: str) -> int:
    """Conta palavras, incluindo nomes e marcadores."""
    return len(re.findall(r"\b[\wÀ-ÿ]+(?:[-'][\wÀ-ÿ]+)*\b", texto))


def validar_roteiro(
    descricao: str,
    resposta: str,
) -> tuple[bool, str]:
    """Verifica se a narração respeita a duração solicitada."""
    segundos = extrair_duracao(descricao)

    if segundos is None:
        return True, "Nenhuma duração foi especificada."

    if segundos <= 0:
        return False, "A duração solicitada deve ser positiva."

    narracao = extrair_narracao(resposta)

    if not narracao:
        return False, "Não foi possível identificar a narração."

    palavras = contar_palavras(narracao)
    limite = limite_palavras(segundos)

    if palavras > limite:
        return (
            False,
            f"Narração com {palavras} palavras. "
            f"Limite para {segundos} segundos: {limite}.",
        )

    return (
        True,
        f"Narração validada: {palavras}/{limite} palavras "
        f"para {segundos} segundos.",
    )
