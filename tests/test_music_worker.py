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
        self.convert_calls: list[tuple[Path, Path]] = []
        self.guidetone_calls: list[tuple[Path, Path]] = []

    async def convert(self, input_path: Path, output_path: Path) -> object:
        self.convert_calls.append((input_path, output_path))
        return await self._complete(output_path)

    async def generate_guidetones(
        self, input_path: Path, output_path: Path
    ) -> object:
        self.guidetone_calls.append((input_path, output_path))
        return await self._complete(output_path)

    async def _complete(self, output_path: Path) -> object:
        if self.fail:
            raise ImproVisorClientError("detalhe técnico")
        output_path.write_text("<score-partwise/>", encoding="utf-8")
        return object()


def _job_with_input(
    store: ArtifactStore, skill: str = "leadsheet_para_musicxml"
) -> Job:
    job = Job(42, "mkimusica", "musica", skill, "T", "D")
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
    assert client.convert_calls == [
        (store.resolve(job.artifacts[0].relative_path), store.resolve(f"{job.id}/output.xml"))
    ]
    assert client.guidetone_calls == []
    output = job.artifacts[-1]
    assert output.role == "output"
    assert output.filename == "resultado.musicxml"
    assert output.media_type == "application/vnd.recordare.musicxml+xml"


@pytest.mark.asyncio
async def test_guide_tones_chama_cliente_e_adiciona_output(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    client = _FakeImproVisorClient()
    worker = MusicWorker(QueueManager(), client, store)  # type: ignore[arg-type]
    job = _job_with_input(store, "guide_tones")

    result = await worker.process_job(job)

    expected_input = store.resolve(job.artifacts[0].relative_path)
    expected_output = store.resolve(f"{job.id}/output.xml")
    assert result == "Guide tones gerados com sucesso."
    assert client.convert_calls == []
    assert client.guidetone_calls == [(expected_input, expected_output)]
    assert expected_input.is_relative_to(store.root)
    assert expected_output.is_relative_to(store.root)
    output = job.artifacts[-1]
    assert output.role == "output"
    assert output.relative_path == f"{job.id}/output.xml"
    assert output.filename == "guide_tones.musicxml"
    assert output.media_type == "application/vnd.recordare.musicxml+xml"


@pytest.mark.asyncio
async def test_skill_musical_desconhecida_falha_sem_output(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    client = _FakeImproVisorClient()
    worker = MusicWorker(QueueManager(), client, store)  # type: ignore[arg-type]
    job = _job_with_input(store, "skill_desconhecida")

    with pytest.raises(ValueError, match="Skill musical não suportada"):
        await worker.process_job(job)

    assert client.convert_calls == []
    assert client.guidetone_calls == []
    assert [artifact.role for artifact in job.artifacts] == ["input"]


@pytest.mark.asyncio
async def test_guide_tones_exige_artefato_ls_de_entrada(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    client = _FakeImproVisorClient()
    worker = MusicWorker(QueueManager(), client, store)  # type: ignore[arg-type]
    job = Job(42, "mkimusica", "musica", "guide_tones", "T", "D")

    with pytest.raises(ValueError, match="artefato .ls de entrada"):
        await worker.process_job(job)

    assert client.guidetone_calls == []
    assert job.artifacts == []


@pytest.mark.asyncio
async def test_falha_do_guide_tones_nao_adiciona_output(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    client = _FakeImproVisorClient(fail=True)
    worker = MusicWorker(QueueManager(), client, store)  # type: ignore[arg-type]
    job = _job_with_input(store, "guide_tones")

    with pytest.raises(ImproVisorClientError):
        await worker.process_job(job)

    assert len(client.guidetone_calls) == 1
    assert [artifact.role for artifact in job.artifacts] == ["input"]


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
