"""Worker especializado para a fila de serviços."""

from __future__ import annotations

from job import Job
from queue_manager import QueueManager
from workers.base_worker import BaseWorker
from job_event_bus import JobEventBus
from job_registry import JobRegistry

class ServiceWorker(BaseWorker):
    """Processa exclusivamente trabalhos da fila ``mkiservicos``."""

    _FILA = "mkiservicos"

    def __init__(
        self,
        queue_manager: QueueManager,
        fila: str = _FILA,
        event_bus: JobEventBus | None = None,
        job_registry: JobRegistry | None = None,
    ) -> None:
        if fila != self._FILA:
            raise ValueError("ServiceWorker aceita apenas a fila mkiservicos.")
        super().__init__(
            queue_manager, fila, event_bus=event_bus, job_registry=job_registry
        )

    async def process_job(self, job: Job) -> str:
        """Produz o resultado de laboratório para um trabalho de serviço."""
        return f"Job {job.id} processado pelo ServiceWorker."
