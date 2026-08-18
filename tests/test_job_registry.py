from __future__ import annotations

from job import Job
from job_registry import JobRegistry


def test_add_e_get_retornam_a_mesma_instancia() -> None:
    registry = JobRegistry()
    job = _make_job()
    registry.add(job)
    assert registry.get(job.id) is job


def test_get_de_id_inexistente_retorna_none() -> None:
    assert JobRegistry().get("inexistente") is None


def test_list_all_retorna_jobs_registrados() -> None:
    registry = JobRegistry()
    first = _make_job("primeiro")
    second = _make_job("segundo")
    registry.add(first)
    registry.add(second)
    assert registry.list_all() == [first, second]


def test_add_substitui_job_com_o_mesmo_id() -> None:
    registry = JobRegistry()
    original = _make_job("original")
    replacement = _make_job("substituto")
    replacement.id = original.id
    registry.add(original)
    registry.add(replacement)
    assert registry.get(original.id) is replacement
    assert registry.list_all() == [replacement]


def _make_job(titulo: str = "Trabalho") -> Job:
    return Job(
        chat_id=42,
        fila="mkitextos",
        tipo="texto",
        skill="teste",
        titulo=titulo,
        descricao="Descrição de teste.",
    )
