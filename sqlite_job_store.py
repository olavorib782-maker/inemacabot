"""Persistência SQLite dos Jobs do InemacaBot."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from threading import Lock

from job import Job, JobPriority, JobStatus


class SQLiteJobStore:
    """Salva e reconstrói Jobs em um arquivo SQLite."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        self._lock = Lock()

    def initialize(self) -> None:
        """Cria a tabela de Jobs quando ela ainda não existe."""
        with self._lock, closing(self._connect()) as connection, connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    chat_id INTEGER NOT NULL,
                    fila TEXT NOT NULL,
                    tipo TEXT NOT NULL,
                    skill TEXT NOT NULL,
                    titulo TEXT NOT NULL,
                    descricao TEXT NOT NULL,
                    status TEXT NOT NULL,
                    prioridade TEXT NOT NULL,
                    criada_em TEXT NOT NULL,
                    atualizada_em TEXT NOT NULL,
                    resultado TEXT NOT NULL DEFAULT ''
                )
                """
            )

    def save(self, job: Job) -> None:
        """Insere ou atualiza integralmente um Job em uma transação curta."""
        values = (
            job.id,
            job.chat_id,
            job.fila,
            job.tipo,
            job.skill,
            job.titulo,
            job.descricao,
            job.status.value,
            job.prioridade.value,
            job.criada_em.isoformat(),
            job.atualizada_em.isoformat(),
            job.resultado,
        )
        with self._lock, closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO jobs (
                    id, chat_id, fila, tipo, skill, titulo, descricao,
                    status, prioridade, criada_em, atualizada_em, resultado
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    chat_id = excluded.chat_id,
                    fila = excluded.fila,
                    tipo = excluded.tipo,
                    skill = excluded.skill,
                    titulo = excluded.titulo,
                    descricao = excluded.descricao,
                    status = excluded.status,
                    prioridade = excluded.prioridade,
                    criada_em = excluded.criada_em,
                    atualizada_em = excluded.atualizada_em,
                    resultado = excluded.resultado
                """,
                values,
            )

    def load_all(self) -> list[Job]:
        """Carrega todos os Jobs persistidos."""
        with self._lock, closing(self._connect()) as connection, connection:
            rows = connection.execute(
                """
                SELECT id, chat_id, fila, tipo, skill, titulo, descricao,
                       status, prioridade, criada_em, atualizada_em, resultado
                FROM jobs
                ORDER BY criada_em, id
                """
            ).fetchall()

        return [
            Job(
                id=row[0],
                chat_id=row[1],
                fila=row[2],
                tipo=row[3],
                skill=row[4],
                titulo=row[5],
                descricao=row[6],
                status=JobStatus(row[7]),
                prioridade=JobPriority(row[8]),
                criada_em=datetime.fromisoformat(row[9]),
                atualizada_em=datetime.fromisoformat(row[10]),
                resultado=row[11],
            )
            for row in rows
        ]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection
