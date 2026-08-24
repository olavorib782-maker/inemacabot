"""Roteamento determinístico de mensagens para futuras filas."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RouteDecision:
    """Resultado da classificação de uma mensagem do usuário."""

    is_job: bool
    fila: str | None = None
    tipo: str | None = None
    skill: str | None = None


def _normalize(message: str) -> str:
    """Normaliza maiúsculas, acentos e separadores para comparar palavras-chave."""
    decomposed = unicodedata.normalize("NFKD", message.casefold())
    without_accents = "".join(char for char in decomposed if not unicodedata.combining(char))
    return without_accents.replace("_", " ").replace("-", " ")


class Router:
    """Identifica trabalhos conhecidos sem usar serviços externos."""

    _MUSIC_SKILLS = {
        "ls para musicxml": "leadsheet_para_musicxml",
        "converter leadsheet": "leadsheet_para_musicxml",
        "converter para musicxml": "leadsheet_para_musicxml",
    }
    _SERVICE_SKILLS = {
        "pesquisa": "pesquisa",
        "pesquise": "pesquisa",
        "documento": "documento",
        "automacao": "automacao",
        "processamento arquivo": "processamento_arquivo",
    }
    _TEXT_SKILLS = {
        "roteiro": "roteiro",
        "transcricao": "transcricao",
        "traducao": "traducao",
        "texto avatar": "texto_avatar",
    }
    _VIDEO_SKILLS = {
        "video explicativo": "video_explicativo",
        "video curso": "video_curso",
        "reels": "reels",
        "edicao video": "edicao_video",
    }

    def route(self, message: str) -> RouteDecision:
        """Retorna a fila correspondente ou informa que a mensagem não é um trabalho."""
        normalized_message = _normalize(message)

        decision = self._match(normalized_message, self._MUSIC_SKILLS, "mkimusica", "musica")
        if decision is not None:
            return decision

        decision = self._match(normalized_message, self._SERVICE_SKILLS, "mkiservicos", "servico")
        if decision is not None:
            return decision

        decision = self._match(normalized_message, self._TEXT_SKILLS, "mkitextos", "texto")
        if decision is not None:
            return decision

        decision = self._match(normalized_message, self._VIDEO_SKILLS, "mkivideos", "video")
        if decision is not None:
            return decision

        return RouteDecision(is_job=False)

    @staticmethod
    def _match(
        message: str,
        skills: dict[str, str],
        fila: str,
        tipo: str,
    ) -> RouteDecision | None:
        for keyword, skill in skills.items():
            if keyword in message:
                return RouteDecision(is_job=True, fila=fila, tipo=tipo, skill=skill)
        return None
