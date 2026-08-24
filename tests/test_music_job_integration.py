from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from artifact_store import ArtifactStore
from job import Job, JobStatus
from job_artifact import JobArtifact
from job_event_bus import JobEventBus
from queue_manager import QueueManager
from result_notifier import ResultNotifier
from result_supervisor import ResultSupervisor
from workers.music_worker import MusicWorker


class _FakeImproVisorClient:
    def __init__(self) -> None:
        self.convert_calls: list[tuple[Path, Path]] = []
        self.guidetone_calls: list[tuple[Path, Path]] = []

    async def convert(self, input_path: Path, output_path: Path) -> object:
        self.convert_calls.append((input_path, output_path))
        output_path.write_text("<score-partwise/>", encoding="utf-8")
        return object()

    async def generate_guidetones(
        self, input_path: Path, output_path: Path
    ) -> object:
        self.guidetone_calls.append((input_path, output_path))
        output_path.write_text("<score-partwise/>", encoding="utf-8")
        return object()


@pytest.mark.asyncio
async def test_fluxo_interno_musical_ate_document_sender(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "artifacts")
    queue = QueueManager()
    bus = JobEventBus()
    client = _FakeImproVisorClient()
    worker = MusicWorker(
        queue, client, store, event_bus=bus  # type: ignore[arg-type]
    )
    documents = []

    async def text_sender(chat_id: int, message: str) -> None:
        raise AssertionError("O fluxo com output não deve usar sender textual.")

    async def document_sender(
        chat_id: int, path: Path, filename: str, caption: str
    ) -> None:
        documents.append((chat_id, path, filename, caption))

    notifier = ResultNotifier(text_sender, document_sender, store)
    supervisor = ResultSupervisor(bus, notifier)
    job = Job(
        42,
        "mkimusica",
        "musica",
        "leadsheet_para_musicxml",
        "Converter",
        "Converter leadsheet",
    )
    input_relative, input_path = store.job_path(job.id, "input.ls")
    input_path.write_text("(title Teste)", encoding="utf-8")
    job.artifacts.append(
        JobArtifact("input", input_relative, "input.ls", "application/x-improvisor")
    )
    worker_task = asyncio.create_task(worker.run())
    supervisor_task = asyncio.create_task(supervisor.run())

    await queue.put(job)
    await _wait_until(lambda: bool(documents))
    worker_task.cancel()
    supervisor_task.cancel()
    await asyncio.gather(worker_task, supervisor_task, return_exceptions=True)

    assert job.status is JobStatus.CONCLUIDO
    assert job.resultado == "Leadsheet convertido para MusicXML."
    assert len(client.convert_calls) == 1
    assert client.guidetone_calls == []
    assert [artifact.role for artifact in job.artifacts] == ["input", "output"]
    assert documents[0][0] == 42
    assert documents[0][1].is_file()
    assert documents[0][2] == "resultado.musicxml"
    assert documents[0][3] == "Leadsheet convertido para MusicXML."


@pytest.mark.asyncio
async def test_fluxo_guide_tones_ate_document_sender(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "artifacts")
    queue = QueueManager()
    bus = JobEventBus()
    client = _FakeImproVisorClient()
    worker = MusicWorker(
        queue, client, store, event_bus=bus  # type: ignore[arg-type]
    )
    documents = []

    async def text_sender(chat_id: int, message: str) -> None:
        raise AssertionError("O fluxo com output não deve usar sender textual.")

    async def document_sender(
        chat_id: int, path: Path, filename: str, caption: str
    ) -> None:
        documents.append((chat_id, path, filename, caption))

    notifier = ResultNotifier(text_sender, document_sender, store)
    supervisor = ResultSupervisor(bus, notifier)
    job = Job(
        42,
        "mkimusica",
        "musica",
        "guide_tones",
        "Gerar guide tones",
        "Gerar guide tones sobre o leadsheet",
    )
    input_relative, input_path = store.job_path(job.id, "input.ls")
    input_path.write_text("Dm7 | G7 | Cmaj7 | Cmaj7 |", encoding="utf-8")
    job.artifacts.append(
        JobArtifact("input", input_relative, "input.ls", "application/x-improvisor")
    )
    worker_task = asyncio.create_task(worker.run())
    supervisor_task = asyncio.create_task(supervisor.run())

    await queue.put(job)
    await _wait_until(lambda: bool(documents))
    worker_task.cancel()
    supervisor_task.cancel()
    await asyncio.gather(worker_task, supervisor_task, return_exceptions=True)

    assert job.status is JobStatus.CONCLUIDO
    assert job.resultado == "Guide tones gerados com sucesso."
    assert client.convert_calls == []
    assert len(client.guidetone_calls) == 1
    assert [artifact.role for artifact in job.artifacts] == ["input", "output"]
    output = job.artifacts[-1]
    assert output.filename == "guide_tones.musicxml"
    assert store.resolve(output.relative_path).is_relative_to(store.root)
    assert documents[0][0] == 42
    assert documents[0][1].is_file()
    assert documents[0][2] == "guide_tones.musicxml"
    assert documents[0][3] == "Guide tones gerados com sucesso."


async def _wait_until(predicate) -> None:
    async def wait() -> None:
        while not predicate():
            await asyncio.sleep(0)

    await asyncio.wait_for(wait(), timeout=1)
