"""Serviço para transformar mensagens reconhecidas em trabalhos enfileirados."""

from __future__ import annotations

from job import Job
from job_artifact import JobArtifact
from job_registry import JobRegistry
from queue_manager import QueueManager
from router import Router


class JobService:
    """Cria e enfileira trabalhos a partir das decisões do roteador."""

    def __init__(
        self, router: Router, queue_manager: QueueManager, job_registry: JobRegistry
    ) -> None:
        self.router = router
        self.queue_manager = queue_manager
        self.job_registry = job_registry

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
        self.job_registry.add(job)
        await self.queue_manager.put(job)
        return job

    async def submit_music_document(
        self,
        chat_id: int,
        job_id: str,
        friendly_filename: str,
        relative_path: str,
    ) -> Job:
        """Persiste e enfileira um `.ls` já salvo na raiz controlada."""
        job = Job(
            id=job_id,
            chat_id=chat_id,
            fila="mkimusica",
            tipo="musica",
            skill="leadsheet_para_musicxml",
            titulo=f"Converter {friendly_filename} para MusicXML",
            descricao="Conversão de leadsheet para MusicXML.",
            artifacts=[
                JobArtifact(
                    role="input",
                    relative_path=relative_path,
                    filename=friendly_filename,
                    media_type="application/x-improvisor-leadsheet",
                )
            ],
        )
        self.job_registry.add(job)
        await self.queue_manager.put(job)
        return job
