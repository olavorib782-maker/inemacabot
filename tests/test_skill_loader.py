from __future__ import annotations

from pathlib import Path

import pytest

from skill_loader import SkillLoader, SkillNotFoundError


def test_carrega_skill_existente_com_conteudo_exato(tmp_path: Path) -> None:
    (tmp_path / "video_explicativo.md").write_text("Conteudo da skill", encoding="utf-8")

    assert SkillLoader(tmp_path).load("video_explicativo") == "Conteudo da skill"


def test_carrega_skill_com_utf8(tmp_path: Path) -> None:
    content = "Instrucoes para narracao: acao e explicacao."
    (tmp_path / "video_explicativo.md").write_text(content, encoding="utf-8")

    assert SkillLoader(tmp_path).load("video_explicativo") == content


def test_skill_inexistente_gera_erro_proprio(tmp_path: Path) -> None:
    with pytest.raises(SkillNotFoundError, match="Skill nao encontrada: ausente"):
        SkillLoader(tmp_path).load("ausente")


def test_nome_logico_sem_extensao_funciona(tmp_path: Path) -> None:
    (tmp_path / "roteiro.md").write_text("Roteiro", encoding="utf-8")

    assert SkillLoader(tmp_path).load("roteiro") == "Roteiro"


@pytest.mark.parametrize("skill_name", ["../segredo", "../../segredo", "subdir/segredo"])
def test_rejeita_tentativa_de_saida_do_diretorio(tmp_path: Path, skill_name: str) -> None:
    outside_file = tmp_path.parent / "segredo.md"
    outside_file.write_text("Nao deve ser lido", encoding="utf-8")

    with pytest.raises(ValueError, match="Nome de skill invalido"):
        SkillLoader(tmp_path).load(skill_name)


def test_rejeita_caminho_absoluto(tmp_path: Path) -> None:
    absolute_name = str((tmp_path / "segredo").resolve())

    with pytest.raises(ValueError, match="Nome de skill invalido"):
        SkillLoader(tmp_path).load(absolute_name)


def test_nao_acessa_arquivo_fora_do_diretorio_de_skills(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    outside_file = tmp_path / "externa.md"
    outside_file.write_text("Conteudo externo", encoding="utf-8")

    with pytest.raises(ValueError):
        SkillLoader(skills_dir).load("../externa")


def test_duas_skills_diferentes_podem_ser_carregadas(tmp_path: Path) -> None:
    (tmp_path / "video.md").write_text("Skill de video", encoding="utf-8")
    (tmp_path / "texto.md").write_text("Skill de texto", encoding="utf-8")
    loader = SkillLoader(tmp_path)

    assert loader.load("video") == "Skill de video"
    assert loader.load("texto") == "Skill de texto"


def test_diretorio_e_fornecido_pelo_construtor(tmp_path: Path) -> None:
    skills_dir = tmp_path / "minhas_skills"
    skills_dir.mkdir()
    (skills_dir / "servico.md").write_text("Skill de servico", encoding="utf-8")

    assert SkillLoader(skills_dir).load("servico") == "Skill de servico"
