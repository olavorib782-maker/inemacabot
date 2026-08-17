from __future__ import annotations

from job import Job, JobPriority, JobStatus


def test_job_e_criado_com_valores_validos() -> None:
    job = Job(
        chat_id=42,
        fila="mkitextos",
        tipo="texto",
        skill="roteiro",
        titulo="Roteiro de apresentação",
        descricao="Criar um roteiro sobre IA.",
    )

    assert job.chat_id == 42
    assert job.fila == "mkitextos"
    assert job.skill == "roteiro"
    assert job.id


def test_job_comeca_aguardando() -> None:
    job = _make_job()
    assert job.status is JobStatus.AGUARDANDO


def test_job_comeca_com_prioridade_normal() -> None:
    job = _make_job()
    assert job.prioridade is JobPriority.NORMAL


def test_job_comeca_sem_resultado() -> None:
    job = _make_job()
    assert job.resultado == ""


def _make_job() -> Job:
    return Job(
        chat_id=42,
        fila="mkitextos",
        tipo="texto",
        skill="roteiro",
        titulo="Roteiro",
        descricao="Criar um roteiro.",
    )
