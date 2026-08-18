"""Worker especializado para a fila de textos."""

from __future__ import annotations

from job import Job
from queue_manager import QueueManager
from workers.base_worker import BaseWorker
from job_event_bus import JobEventBus
from job_registry import JobRegistry

class TextWorker(BaseWorker):
    """Processa exclusivamente trabalhos da fila ``mkitextos``."""

    _FILA = "mkitextos"

    def __init__(
        self,
        queue_manager: QueueManager,
        fila: str = _FILA,
        event_bus: JobEventBus | None = None,
        job_registry: JobRegistry | None = None,
    ) -> None:
        if fila != self._FILA:
            raise ValueError("TextWorker aceita apenas a fila mkitextos.")
        super().__init__(
            queue_manager, fila, event_bus=event_bus, job_registry=job_registry
        )

    async def process_job(self, job: Job) -> str:
        """Produz o resultado de laboratório para um trabalho de texto."""
        return f"Job {job.id} processado pelo TextWorker."
