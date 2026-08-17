"""Worker especializado para a fila de vídeos."""

from __future__ import annotations

from agent_runner import AgentRunner
from job import Job
from queue_manager import QueueManager
from workers.base_worker import BaseWorker
from job_event_bus import JobEventBus

class VideoWorker(BaseWorker):
    """Processa exclusivamente trabalhos da fila ``mkivideos``."""

    _FILA = "mkivideos"

    def __init__(
        self,
        queue_manager: QueueManager,
        fila: str = _FILA,
        agent_runner: AgentRunner | None = None,
        event_bus: JobEventBus | None = None,
    ) -> None:
        if fila != self._FILA:
            raise ValueError("VideoWorker aceita apenas a fila mkivideos.")
        super().__init__(queue_manager, fila, event_bus=event_bus)
        self.agent_runner = agent_runner

    async def process_job(self, job: Job) -> str:
        """Produz o resultado de laboratório para um trabalho de vídeo."""
        if self.agent_runner is not None:
            return await self.agent_runner.run(job)
        return f"Job {job.id} processado pelo VideoWorker."
