"""Gerenciamento assíncrono das filas de trabalhos do InemacaBot."""

from __future__ import annotations

import asyncio

from job import Job, VALID_QUEUES


class QueueManager:
    """Mantém filas FIFO independentes para os tipos de trabalho suportados."""

    def __init__(self) -> None:
        self.queues: dict[str, asyncio.Queue[Job]] = {
            fila: asyncio.Queue() for fila in VALID_QUEUES
        }

    async def put(self, job: Job) -> None:
        """Adiciona um trabalho à fila indicada pelo próprio trabalho."""
        if not isinstance(job, Job):
            raise TypeError("A fila aceita apenas objetos Job.")

        queue = self._get_queue(job.fila)
        await queue.put(job)

    async def get(self, fila: str) -> Job:
        """Aguarda e remove o próximo trabalho da fila solicitada."""
        return await self._get_queue(fila).get()

    def size(self, fila: str) -> int:
        """Retorna a quantidade atual de trabalhos na fila solicitada."""
        return self._get_queue(fila).qsize()

    def _get_queue(self, fila: str) -> asyncio.Queue[Job]:
        try:
            return self.queues[fila]
        except KeyError as error:
            raise ValueError(f"Fila inválida: {fila}.") from error
