"""Worker da conversão headless de leadsheets para MusicXML."""

from __future__ import annotations

from artifact_store import ArtifactStore
from improvisor_client import ImproVisorClient
from job import Job
from job_artifact import JobArtifact
from job_event_bus import JobEventBus
from job_registry import JobRegistry
from queue_manager import QueueManager
from workers.base_worker import BaseWorker


class MusicWorker(BaseWorker):
    """Processa exclusivamente a fila ``mkimusica``."""

    _FILA = "mkimusica"
    _OUTPUT_MEDIA_TYPE = "application/vnd.recordare.musicxml+xml"

    def __init__(
        self,
        queue_manager: QueueManager,
        improvisor_client: ImproVisorClient,
        artifact_store: ArtifactStore,
        fila: str = _FILA,
        event_bus: JobEventBus | None = None,
        job_registry: JobRegistry | None = None,
    ) -> None:
        if fila != self._FILA:
            raise ValueError("MusicWorker aceita apenas a fila mkimusica.")
        super().__init__(
            queue_manager, fila, event_bus=event_bus, job_registry=job_registry
        )
        self.improvisor_client = improvisor_client
        self.artifact_store = artifact_store

    async def process_job(self, job: Job) -> str:
        if job.skill == "leadsheet_para_musicxml":
            operation = self.improvisor_client.convert
            output_filename = "resultado.musicxml"
            success_message = "Leadsheet convertido para MusicXML."
        elif job.skill == "guide_tones":
            operation = self.improvisor_client.generate_guidetones
            output_filename = "guide_tones.musicxml"
            success_message = "Guide tones gerados com sucesso."
        else:
            raise ValueError("Skill musical não suportada.")

        input_artifact = next(
            (
                artifact
                for artifact in job.artifacts
                if artifact.role == "input"
                and artifact.relative_path.lower().endswith(".ls")
            ),
            None,
        )
        if input_artifact is None:
            raise ValueError("Job musical sem artefato .ls de entrada.")

        input_path = self.artifact_store.resolve(input_artifact.relative_path)
        output_relative, output_path = self.artifact_store.job_path(
            job.id, "output.xml"
        )

        await operation(input_path, output_path)

        job.artifacts.append(
            JobArtifact(
                role="output",
                relative_path=output_relative,
                filename=output_filename,
                media_type=self._OUTPUT_MEDIA_TYPE,
            )
        )
        return success_message
