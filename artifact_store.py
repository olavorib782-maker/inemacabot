"""Resolução segura de caminhos sob a raiz de artefatos dos Jobs."""

from __future__ import annotations

from pathlib import Path


class ArtifactPathError(ValueError):
    """Indica um caminho absoluto ou fora da raiz de artefatos."""


class ArtifactStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def resolve(self, relative_path: str | Path) -> Path:
        relative = Path(relative_path)
        if relative.is_absolute():
            raise ArtifactPathError("O caminho do artefato deve ser relativo.")

        resolved = (self.root / relative).resolve()
        if resolved != self.root and self.root not in resolved.parents:
            raise ArtifactPathError("O caminho do artefato sai da raiz permitida.")
        return resolved

    def job_path(self, job_id: str, filename: str) -> tuple[str, Path]:
        relative = Path(job_id) / filename
        resolved = self.resolve(relative)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        return relative.as_posix(), resolved

