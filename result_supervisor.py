"""Supervisor responsável por observar eventos de conclusão de Jobs."""

from __future__ import annotations

import logging

from job_event_bus import JobEventBus
from job_events import JobCompletedEvent, JobEvent, JobFailedEvent
from result_notifier import ResultNotifier


logger = logging.getLogger(__name__)


class ResultSupervisor:
    """Consome eventos e encaminha resultados para o notifier."""

    def __init__(
        self,
        event_bus: JobEventBus,
        notifier: ResultNotifier,
    ) -> None:
        self.event_bus = event_bus
        self.notifier = notifier

    async def run(self) -> None:
        """Aguarda continuamente os eventos de conclusão."""
        while True:
            event = await self.event_bus.get()
            try:
                await self.handle(event)
            except Exception:
                logger.exception("Falha ao notificar resultado de Job.")

    async def handle(self, event: JobEvent) -> None:
        """Encaminha o resultado do Job para o notifier."""
        if isinstance(event, JobCompletedEvent):
            await self.notifier.notify(event.job)
        elif isinstance(event, JobFailedEvent):
            await self.notifier.notify_failure(event.job)
