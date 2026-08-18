from __future__ import annotations

from pathlib import Path

from job import Job
from job_registry import JobRegistry
from sqlite_job_store import SQLiteJobStore


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


def test_add_e_update_persistem_job(tmp_path: Path) -> None:
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    store.initialize()
    registry = JobRegistry(store)
    job = _make_job()

    registry.add(job)
    job.resultado = "pronto"
    registry.update(job)

    restored = store.load_all()
    assert len(restored) == 1
    assert restored[0].resultado == "pronto"


def test_restore_reconstroi_dicionario_em_memoria(tmp_path: Path) -> None:
    database_path = tmp_path / "jobs.sqlite3"
    store = SQLiteJobStore(database_path)
    store.initialize()
    job = _make_job()
    store.save(job)

    registry = JobRegistry(SQLiteJobStore(database_path))
    restored = registry.restore()

    assert len(restored) == 1
    assert registry.get(job.id) is restored[0]
    assert registry.list_all() == restored


def _make_job(titulo: str = "Trabalho") -> Job:
    return Job(
        chat_id=42,
        fila="mkitextos",
        tipo="texto",
        skill="teste",
        titulo=titulo,
        descricao="Descrição de teste.",
    )
