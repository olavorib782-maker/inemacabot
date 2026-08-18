"""Controle do ciclo de vida dos workers especializados."""

from __future__ import annotations

import asyncio

from agent_runner import AgentRunner
from job_event_bus import JobEventBus
from job_registry import JobRegistry
from queue_manager import QueueManager
from workers.base_worker import BaseWorker
from workers.service_worker import ServiceWorker
from workers.text_worker import TextWorker
from workers.video_worker import VideoWorker


class WorkerManager:
    """Inicia e interrompe os workers associados às filas do sistema."""

    def __init__(
        self,
        queue_manager: QueueManager,
        agent_runner: AgentRunner | None = None,
        event_bus: JobEventBus | None = None,
        job_registry: JobRegistry | None = None,
    ) -> None:
        self.queue_manager = queue_manager
        self.agent_runner = agent_runner
        self.event_bus = event_bus or JobEventBus()
        self.job_registry = job_registry
        self.workers: dict[str, BaseWorker] = {}
        self.tasks: dict[str, asyncio.Task[None]] = {}

    async def start(self) -> None:
        """Cria e inicia um worker por fila, sem duplicar workers ativos."""
        if self.tasks:
            return

        self.workers = {
            "mkivideos": VideoWorker(
                self.queue_manager,
                agent_runner=self.agent_runner,
                event_bus=self.event_bus,
                job_registry=self.job_registry,
            ),
            "mkitextos": TextWorker(
                self.queue_manager,
                event_bus=self.event_bus,
                job_registry=self.job_registry,
            ),
            "mkiservicos": ServiceWorker(
                self.queue_manager,
                event_bus=self.event_bus,
                job_registry=self.job_registry,
            ),
        }

        self.tasks = {
            fila: asyncio.create_task(
                worker.run(),
                name=f"worker-{fila}",
            )
            for fila, worker in self.workers.items()
        }

    async def stop(self) -> None:
        """Cancela os workers ativos e aguarda o encerramento."""
        tasks = tuple(self.tasks.values())

        if not tasks:
            return

        for task in tasks:
            task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)

        self.tasks = {}
        self.workers = {}
