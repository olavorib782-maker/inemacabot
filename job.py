"""Modelo de trabalho para as futuras filas do InemacaBot."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


VALID_QUEUES = frozenset({"mkivideos", "mkitextos", "mkiservicos"})


class JobStatus(str, Enum):
    """Estados possíveis de um trabalho."""

    AGUARDANDO = "AGUARDANDO"
    PROCESSANDO = "PROCESSANDO"
    CONCLUIDO = "CONCLUIDO"
    ERRO = "ERRO"
    CANCELADO = "CANCELADO"


class JobPriority(str, Enum):
    """Prioridades possíveis de um trabalho."""

    BAIXA = "BAIXA"
    NORMAL = "NORMAL"
    ALTA = "ALTA"
    URGENTE = "URGENTE"


def _now() -> datetime:
    """Retorna o instante atual em UTC."""
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class Job:
    """Representa uma solicitação que será processada futuramente em uma fila."""

    chat_id: int
    fila: str
    tipo: str
    skill: str
    titulo: str
    descricao: str
    id: str = field(default_factory=lambda: str(uuid4()))
    status: JobStatus = JobStatus.AGUARDANDO
    prioridade: JobPriority = JobPriority.NORMAL
    dados: dict[str, Any] = field(default_factory=dict)
    criada_em: datetime = field(default_factory=_now)
    atualizada_em: datetime = field(default_factory=_now)
    resultado: str = ""

    def __post_init__(self) -> None:
        if self.fila not in VALID_QUEUES:
            raise ValueError(f"Fila inválida: {self.fila}.")
