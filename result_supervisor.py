"""Supervisor responsável por observar eventos de conclusão de Jobs."""

from __future__ import annotations

from job_event_bus import JobEventBus
from job_events import JobCompletedEvent
from result_notifier import ResultNotifier


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
            event: JobCompletedEvent = await self.event_bus.get()
            await self.handle(event)

    async def handle(self, event: JobCompletedEvent) -> None:
        """Encaminha o resultado do Job para o notifier."""
        await self.notifier.notify(event.job)