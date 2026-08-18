"""Registro em memória dos trabalhos criados."""

from __future__ import annotations

from job import Job
from sqlite_job_store import SQLiteJobStore


class JobRegistry:
    """Mantém as referências dos trabalhos registradas por ID."""

    def __init__(self, store: SQLiteJobStore | None = None) -> None:
        self._jobs: dict[str, Job] = {}
        self.store = store

    def add(self, job: Job) -> None:
        """Registra um trabalho, substituindo outro com o mesmo ID."""
        if self.store is not None:
            self.store.save(job)
        self._jobs[job.id] = job

    def update(self, job: Job) -> None:
        """Persiste mudanças explícitas mantendo a mesma referência em memória."""
        if self.store is not None:
            self.store.save(job)
        self._jobs[job.id] = job

    def restore(self) -> list[Job]:
        """Restaura no mapa em memória todos os Jobs persistidos."""
        if self.store is None:
            return []

        self.store.initialize()
        jobs = self.store.load_all()
        self._jobs = {job.id: job for job in jobs}
        return jobs

    def get(self, job_id: str) -> Job | None:
        """Retorna o trabalho registrado ou ``None`` quando inexistente."""
        return self._jobs.get(job_id)

    def list_all(self) -> list[Job]:
        """Retorna todos os trabalhos registrados."""
        return list(self._jobs.values())
