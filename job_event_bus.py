"""Barramento assíncrono de eventos dos Jobs."""

from __future__ import annotations

import asyncio
from job_events import JobEvent


class JobEventBus:
    """Publica e distribui eventos de conclusão de Jobs."""

    def __init__(self) -> None:
        self._events: asyncio.Queue[JobEvent] = asyncio.Queue()

    async def publish(self, event: JobEvent) -> None:
        """Publica um evento para processamento posterior."""
        await self._events.put(event)

    async def get(self) -> JobEvent:
        """Aguarda e retorna o próximo evento."""
        return await self._events.get()
