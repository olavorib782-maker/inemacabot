"""Worker genérico para processamento assíncrono de trabalhos em fila."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from job import Job, JobStatus
from job_event_bus import JobEventBus
from job_events import JobCompletedEvent
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
    ) -> None:
        self.queue_manager = queue_manager
        self.fila = fila
        self.event_bus = event_bus
        self.queue_manager.size(fila)

    async def run(self) -> None:
        """Aguarda e processa trabalhos da fila até ser cancelado."""
        while True:
            job = await self.queue_manager.get(self.fila)
            job.status = JobStatus.PROCESSANDO
            job.atualizada_em = _now()

            try:
                job.resultado = await self.process_job(job)
            except Exception:
                job.status = JobStatus.ERRO
                job.atualizada_em = _now()
                logger.exception(
                    "Falha ao processar job %s na fila %s.",
                    job.id,
                    self.fila,
                )
            else:
                job.status = JobStatus.CONCLUIDO
                job.atualizada_em = _now()

                if self.event_bus is not None:
                    await self.event_bus.publish(JobCompletedEvent(job))

    async def process_job(self, job: Job) -> str:
        """Produz um resultado simples, podendo ser sobrescrito."""
        return f"Job {job.id} processado pelo worker."