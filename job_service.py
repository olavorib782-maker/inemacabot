"""Serviço para transformar mensagens reconhecidas em trabalhos enfileirados."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

from artifact_store import ArtifactStore
from job import Job
from job import JobStatus
from job_artifact import JobArtifact
from job_registry import JobRegistry
from leadsheet_builder import LeadsheetBuilder
from queue_manager import QueueManager
from router import Router


logger = logging.getLogger(__name__)
_GUIDE_TONES_MARKER = "guide tones para"
_MAX_GUIDE_TONES_MESSAGE_LENGTH = 2000
_MAX_GUIDE_TONES_PROGRESSION_LENGTH = 1024


class GuideTonesRequestError(ValueError):
    """Indica uma solicitação textual de guide tones malformada."""


def extract_guide_tones_chords(message: str) -> list[str]:
    """Extrai barras separadas por ``|`` sem interpretar harmonia."""
    if len(message) > _MAX_GUIDE_TONES_MESSAGE_LENGTH:
        raise GuideTonesRequestError("A solicitação de guide tones é muito longa.")

    marker_index = message.casefold().find(_GUIDE_TONES_MARKER)
    if marker_index < 0:
        raise GuideTonesRequestError("Marcador de guide tones ausente.")

    progression = message[marker_index + len(_GUIDE_TONES_MARKER) :].strip()
    if not progression:
        raise GuideTonesRequestError("A progressão harmônica está ausente.")
    if len(progression) > _MAX_GUIDE_TONES_PROGRESSION_LENGTH:
        raise GuideTonesRequestError("A progressão harmônica é muito longa.")

    bars = progression.split("|")
    if bars[-1].strip() == "":
        bars.pop()
    if not bars or any(not bar.strip() for bar in bars):
        raise GuideTonesRequestError("A progressão contém um compasso vazio.")

    return [bar.strip() for bar in bars]


class JobService:
    """Cria e enfileira trabalhos a partir das decisões do roteador."""

    def __init__(
        self,
        router: Router,
        queue_manager: QueueManager,
        job_registry: JobRegistry,
        leadsheet_builder: LeadsheetBuilder | None = None,
        artifact_store: ArtifactStore | None = None,
    ) -> None:
        self.router = router
        self.queue_manager = queue_manager
        self.job_registry = job_registry
        self.leadsheet_builder = leadsheet_builder
        self.artifact_store = artifact_store

    async def submit(self, chat_id: int, message: str) -> Job | None:
        """Enfileira um trabalho reconhecido ou retorna ``None`` para conversa normal."""
        decision = self.router.route(message)
        if not decision.is_job:
            return None
        if decision.skill == "guide_tones":
            chords = extract_guide_tones_chords(message)
            return await self.submit_guide_tones(chat_id, chords)

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

    async def submit_guide_tones(
        self, chat_id: int, chords: Sequence[str]
    ) -> Job:
        """Cria, persiste e enfileira um Job a partir de acordes estruturados."""
        if self.leadsheet_builder is None or self.artifact_store is None:
            raise RuntimeError("Dependências de guide tones não configuradas.")

        content = self.leadsheet_builder.render_guidetones(chords)
        job = Job(
            chat_id=chat_id,
            fila="mkimusica",
            tipo="musica",
            skill="guide_tones",
            titulo="Gerar guide tones",
            descricao="Geração de guide tones a partir de uma progressão harmônica.",
        )
        relative_path, input_path = self.artifact_store.job_path(job.id, "input.ls")

        try:
            input_path.write_text(content, encoding="utf-8")
        except OSError:
            self._remove_artifact(input_path)
            raise

        job.artifacts.append(
            JobArtifact(
                role="input",
                relative_path=relative_path,
                filename="guide_tones.ls",
                media_type="application/x-improvisor-leadsheet",
            )
        )

        try:
            self.job_registry.add(job)
        except BaseException:
            self._remove_artifact(input_path)
            raise

        try:
            await self.queue_manager.put(job)
        except BaseException:
            job.status = JobStatus.ERRO
            job.atualizada_em = datetime.now(timezone.utc)
            try:
                self.job_registry.update(job)
            except Exception:
                logger.exception(
                    "Falha ao persistir erro de enqueue do Job de guide tones %s.",
                    job.id,
                )
            raise

        return job

    @staticmethod
    def _remove_artifact(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.exception("Falha ao remover artifact incompleto de guide tones.")
