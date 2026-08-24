from pathlib import Path

import pytest

from artifact_store import ArtifactPathError, ArtifactStore
from job import Job
from job_artifact import JobArtifact


def test_job_antigo_comeca_sem_artifacts() -> None:
    job = Job(42, "mkitextos", "texto", "teste", "Título", "Descrição")
    assert job.artifacts == []


def test_job_artifact_preserva_metadados() -> None:
    artifact = JobArtifact(
        role="output",
        relative_path="job-1/output.xml",
        filename="resultado.musicxml",
        media_type="application/vnd.recordare.musicxml+xml",
    )
    assert artifact.role == "output"
    assert artifact.relative_path == "job-1/output.xml"


def test_artifact_store_resolve_caminho_dentro_da_raiz(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    assert store.resolve("job/input.ls") == (tmp_path / "job" / "input.ls").resolve()


@pytest.mark.parametrize("path", ["../fora.xml", "job/../../fora.xml"])
def test_artifact_store_rejeita_path_traversal(tmp_path: Path, path: str) -> None:
    with pytest.raises(ArtifactPathError):
        ArtifactStore(tmp_path).resolve(path)


def test_artifact_store_rejeita_caminho_absoluto(tmp_path: Path) -> None:
    with pytest.raises(ArtifactPathError):
        ArtifactStore(tmp_path).resolve(tmp_path / "absoluto.xml")

