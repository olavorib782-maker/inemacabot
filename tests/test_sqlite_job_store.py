from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from job import Job, JobPriority, JobStatus
from sqlite_job_store import SQLiteJobStore


def test_initialize_cria_tabela_jobs(tmp_path: Path) -> None:
    database_path = tmp_path / "jobs.sqlite3"
    store = SQLiteJobStore(database_path)

    store.initialize()

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'jobs'"
        ).fetchone()
    assert row == ("jobs",)


def test_save_e_load_all_preservam_job(tmp_path: Path) -> None:
    store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
    store.initialize()
    job = _make_job()

    store.save(job)
    restored = store.load_all()

    assert len(restored) == 1
    loaded = restored[0]
    assert loaded.id == job.id
    assert loaded.chat_id == job.chat_id
    assert loaded.fila == job.fila
    assert loaded.tipo == job.tipo
    assert loaded.skill == job.skill
    assert loaded.titulo == job.titulo
    assert loaded.descricao == job.descricao
    assert loaded.status is JobStatus.AGUARDANDO
    assert loaded.prioridade is JobPriority.ALTA
    assert loaded.criada_em == job.criada_em
    assert loaded.atualizada_em == job.atualizada_em
    assert loaded.resultado == ""


def test_save_atualiza_status_e_resultado(tmp_path: Path) -> None:
    database_path = tmp_path / "jobs.sqlite3"
    store = SQLiteJobStore(database_path)
    store.initialize()
    job = _make_job()
    store.save(job)

    job.status = JobStatus.CONCLUIDO
    job.resultado = "Resultado persistido"
    job.atualizada_em = datetime.now(timezone.utc)
    store.save(job)

    loaded = SQLiteJobStore(database_path)
    loaded.initialize()
    restored = loaded.load_all()
    assert len(restored) == 1
    assert restored[0].status is JobStatus.CONCLUIDO
    assert restored[0].resultado == "Resultado persistido"
    assert restored[0].atualizada_em == job.atualizada_em


def _make_job() -> Job:
    return Job(
        chat_id=42,
        fila="mkitextos",
        tipo="texto",
        skill="teste",
        titulo="Trabalho persistido",
        descricao="Descrição persistida",
        prioridade=JobPriority.ALTA,
    )
