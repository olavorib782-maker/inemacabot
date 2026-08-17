"""Eventos relacionados ao ciclo de vida dos Jobs."""

from __future__ import annotations

from dataclasses import dataclass

from job import Job


@dataclass(frozen=True, slots=True)
class JobCompletedEvent:
    """Evento emitido quando um Job termina o processamento."""

    job: Job