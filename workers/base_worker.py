"""Worker genérico para processamento assíncrono de trabalhos em fila."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from job import Job, JobStatus
from job_event_bus import JobEventBus
from job_events import JobCompletedEvent, JobFailedEvent
from job_registry import JobRegistry
from queue_manager import QueueManager


logger = logging.getLogger(__name__)


def _now() -> datetime:
    """Retorna o instante atual em UTC."""
    return datetime.now(timezone.utc)


class BaseWorker:
    """Processa continuamente os trabalhos de uma fila específica."""

    def __init__(
        self,
        queue_manager: QueueManager,
        fila: str,
        event_bus: JobEventBus | None = None,
        job_registry: JobRegistry | None = None,
    ) -> None:
        self.queue_manager = queue_manager
        self.fila = fila
        self.event_bus = event_bus
        self.job_registry = job_registry
        self.queue_manager.size(fila)

    async def run(self) -> None:
        """Aguarda e processa trabalhos da fila até ser cancelado."""
        while True:
            job = await self.queue_manager.get(self.fila)
            job.status = JobStatus.PROCESSANDO
            job.atualizada_em = _now()
            if self.job_registry is not None:
                self.job_registry.update(job)

            try:
                job.resultado = await self.process_job(job)
            except Exception:
                job.status = JobStatus.ERRO
                job.atualizada_em = _now()
                if self.job_registry is not None:
                    self.job_registry.update(job)
                logger.exception(
                    "Falha ao processar job %s na fila %s.",
                    job.id,
                    self.fila,
                )

                if self.event_bus is not None:
                    await self.event_bus.publish(JobFailedEvent(job))
            else:
                job.status = JobStatus.CONCLUIDO
                job.atualizada_em = _now()
                if self.job_registry is not None:
                    self.job_registry.update(job)

                if self.event_bus is not None:
                    await self.event_bus.publish(JobCompletedEvent(job))

    async def process_job(self, job: Job) -> str:
        """Produz um resultado simples, podendo ser sobrescrito."""
        return f"Job {job.id} processado pelo worker."
