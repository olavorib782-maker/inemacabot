"""Carregamento seguro de especificacoes de skills em Markdown."""

from __future__ import annotations

from pathlib import Path


class SkillNotFoundError(FileNotFoundError):
    """Indica que uma skill solicitada nao existe no diretorio configurado."""


class SkillLoader:
    """Localiza skills Markdown por seu nome logico."""

    def __init__(self, skills_dir: Path | str = "skills") -> None:
        self.skills_dir = Path(skills_dir).resolve()

    def load(self, skill_name: str) -> str:
        """Retorna o conteudo UTF-8 da skill solicitada."""
        path = self._skill_path(skill_name)
        if not path.is_file():
            raise SkillNotFoundError(f"Skill nao encontrada: {skill_name}.")
        return path.read_text(encoding="utf-8")

    def _skill_path(self, skill_name: str) -> Path:
        if not isinstance(skill_name, str) or not skill_name:
            raise ValueError("O nome da skill deve ser um texto nao vazio.")

        name_path = Path(skill_name)
        if name_path.is_absolute() or name_path.name != skill_name or skill_name.endswith(".md"):
            raise ValueError(f"Nome de skill invalido: {skill_name}.")

        path = (self.skills_dir / f"{skill_name}.md").resolve()
        try:
            path.relative_to(self.skills_dir)
        except ValueError as error:
            raise ValueError(f"Nome de skill invalido: {skill_name}.") from error
        return path
