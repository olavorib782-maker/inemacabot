"""Serviço para transformar mensagens reconhecidas em trabalhos enfileirados."""

from __future__ import annotations

from job import Job
from queue_manager import QueueManager
from router import Router


class JobService:
    """Cria e enfileira trabalhos a partir das decisões do roteador."""

    def __init__(self, router: Router, queue_manager: QueueManager) -> None:
        self.router = router
        self.queue_manager = queue_manager

    async def submit(self, chat_id: int, message: str) -> Job | None:
        """Enfileira um trabalho reconhecido ou retorna ``None`` para conversa normal."""
        decision = self.router.route(message)
        if not decision.is_job:
            return None

        job = Job(
            chat_id=chat_id,
            fila=decision.fila,
            tipo=decision.tipo,
            skill=decision.skill,
            titulo=message,
            descricao=message,
        )
        await self.queue_manager.put(job)
        return job
