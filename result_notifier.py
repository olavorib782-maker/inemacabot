"""Notificação de resultados de Jobs."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

from artifact_store import ArtifactPathError, ArtifactStore
from job import Job


Sender = Callable[[int, str], Awaitable[None]]
DocumentSender = Callable[[int, Path, str, str], Awaitable[None]]


class ResultNotifier:
    """Entrega resultados de Jobs ao usuário através de um sender."""

    def __init__(
        self,
        sender: Sender,
        document_sender: DocumentSender | None = None,
        artifact_store: ArtifactStore | None = None,
    ) -> None:
        self.sender = sender
        self.document_sender = document_sender
        self.artifact_store = artifact_store

    async def notify(self, job: Job) -> None:
        """Envia o resultado do Job para o chat correspondente."""
        output_artifact = next(
            (artifact for artifact in job.artifacts if artifact.role == "output"),
            None,
        )
        if (
            output_artifact is None
            or self.document_sender is None
            or self.artifact_store is None
        ):
            message = self._build_message(job)
            await self.sender(job.chat_id, message)
            return

        try:
            path = self.artifact_store.resolve(output_artifact.relative_path)
        except ArtifactPathError:
            await self.sender(job.chat_id, self._build_missing_artifact_message(job))
            return
        if not path.is_file():
            await self.sender(job.chat_id, self._build_missing_artifact_message(job))
            return

        await self.document_sender(
            job.chat_id,
            path,
            output_artifact.filename,
            self._build_document_caption(job),
        )

    async def notify_failure(self, job: Job) -> None:
        """Informa com segurança que o processamento do Job falhou."""
        message = self._build_failure_message(job)
        await self.sender(job.chat_id, message)

    @staticmethod
    def _build_message(job: Job) -> str:
        """Monta a mensagem de resultado."""
        return (
            "✅ Trabalho concluído!\n\n"
            f"Job: {job.id}\n"
            f"Skill: {job.skill}\n\n"
            f"{job.resultado}"
        )

    @staticmethod
    def _build_failure_message(job: Job) -> str:
        """Monta uma mensagem de falha sem detalhes técnicos."""
        return (
            "❌ Não foi possível concluir o trabalho.\n\n"
            f"Job: {job.id}\n"
            f"Skill: {job.skill}\n\n"
            "Tente novamente mais tarde."
        )

    @staticmethod
    def _build_document_caption(job: Job) -> str:
        return "Leadsheet convertido para MusicXML."

    @staticmethod
    def _build_missing_artifact_message(job: Job) -> str:
        return (
            "❌ O arquivo gerado não está disponível.\n\n"
            f"Job: {job.id}\n"
            "Tente novamente mais tarde."
        )
