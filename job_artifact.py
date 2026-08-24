"""Metadados persistíveis de arquivos associados a um Job."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class JobArtifact:
    """Referencia um arquivo sob a raiz controlada de artefatos."""

    role: str
    relative_path: str
    filename: str
    media_type: str

