"""Registro em memória dos trabalhos criados."""

from __future__ import annotations

from job import Job


class JobRegistry:
    """Mantém as referências dos trabalhos registradas por ID."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}

    def add(self, job: Job) -> None:
        """Registra um trabalho, substituindo outro com o mesmo ID."""
        self._jobs[job.id] = job

    def get(self, job_id: str) -> Job | None:
        """Retorna o trabalho registrado ou ``None`` quando inexistente."""
        return self._jobs.get(job_id)

    def list_all(self) -> list[Job]:
        """Retorna todos os trabalhos registrados."""
        return list(self._jobs.values())
