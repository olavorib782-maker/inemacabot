from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from artifact_store import ArtifactStore
from improvisor_client import ImproVisorClientError
from job import Job, JobStatus
from job_artifact import JobArtifact
from queue_manager import QueueManager
from workers.music_worker import MusicWorker


class _FakeImproVisorClient:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[tuple[Path, Path]] = []

    async def convert(self, input_path: Path, output_path: Path) -> object:
        self.calls.append((input_path, output_path))
        if self.fail:
            raise ImproVisorClientError("detalhe técnico")
        output_path.write_text("<score-partwise/>", encoding="utf-8")
        return object()


def _job_with_input(store: ArtifactStore) -> Job:
    job = Job(42, "mkimusica", "musica", "leadsheet_para_musicxml", "T", "D")
    relative, path = store.job_path(job.id, "input.ls")
    path.write_text("(title Teste)", encoding="utf-8")
    job.artifacts.append(
        JobArtifact("input", relative, "input.ls", "application/x-improvisor")
    )
    return job


@pytest.mark.asyncio
async def test_music_worker_chama_cliente_e_adiciona_output(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    client = _FakeImproVisorClient()
    worker = MusicWorker(QueueManager(), client, store)  # type: ignore[arg-type]
    job = _job_with_input(store)

    result = await worker.process_job(job)

    assert result == "Leadsheet convertido para MusicXML."
    assert client.calls == [
        (store.resolve(job.artifacts[0].relative_path), store.resolve(f"{job.id}/output.xml"))
    ]
    output = job.artifacts[-1]
    assert output.role == "output"
    assert output.filename == "resultado.musicxml"
    assert output.media_type == "application/vnd.recordare.musicxml+xml"


@pytest.mark.asyncio
async def test_artefato_so_e_adicionado_apos_sucesso(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    worker = MusicWorker(
        QueueManager(), _FakeImproVisorClient(fail=True), store  # type: ignore[arg-type]
    )
    job = _job_with_input(store)

    with pytest.raises(ImproVisorClientError):
        await worker.process_job(job)

    assert [artifact.role for artifact in job.artifacts] == ["input"]


@pytest.mark.asyncio
async def test_falha_do_cliente_marca_job_como_erro(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    queue = QueueManager()
    worker = MusicWorker(
        queue, _FakeImproVisorClient(fail=True), store  # type: ignore[arg-type]
    )
    job = _job_with_input(store)
    task = asyncio.create_task(worker.run())

    await queue.put(job)
    await _wait_for_status(job, JobStatus.ERRO)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)

    assert [artifact.role for artifact in job.artifacts] == ["input"]


def test_music_worker_rejeita_outra_fila(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="mkimusica"):
        MusicWorker(QueueManager(), None, ArtifactStore(tmp_path), fila="mkitextos")


async def _wait_for_status(job: Job, expected: JobStatus) -> None:
    async def wait() -> None:
        while job.status is not expected:
            await asyncio.sleep(0)

    await asyncio.wait_for(wait(), timeout=1)

