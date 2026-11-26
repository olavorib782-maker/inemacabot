"""Protecao persistente contra duplicidade de tarefas pagas."""

import sqlite3
from pathlib import Path


class PaidTaskError(RuntimeError):
    """Falha ou duplicidade de tarefa paga."""


class PaidTaskGuard:

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(
            parents=True, exist_ok=True
        )

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS paid_tasks (
                    job_id TEXT PRIMARY KEY,
                    model TEXT NOT NULL,
                    state TEXT NOT NULL,
                    task_id TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def reservar(self, job_id: str, modelo: str):
        """Reserva antes de enviar uma tarefa paga."""

        if not job_id.strip() or not modelo.strip():
            raise ValueError("Job ou modelo invalido.")

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO paid_tasks
                    (job_id, model, state)
                    VALUES (?, ?, ?)
                    """,
                    (job_id, modelo, "reserved"),
                )

        except sqlite3.IntegrityError as erro:
            raise PaidTaskError(
                "Tarefa paga ja registrada. "
                "Novo envio bloqueado."
            ) from erro

    def registrar_task_id(
        self, job_id: str, task_id: str
    ):
        """Registra o identificador recebido da KIE."""

        if not task_id.strip():
            raise ValueError("Task ID invalido.")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                UPDATE paid_tasks
                SET task_id = ?, state = ?
                WHERE job_id = ?
                AND state = ?
                """,
                (task_id, "submitted", job_id, "reserved"),
            )

            if cursor.rowcount != 1:
                raise PaidTaskError(
                    "Reserva inexistente ou ja submetida."
                )

    def consultar(self, job_id: str):
        """Recupera uma tarefa registrada."""

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            registro = conn.execute(
                """
                SELECT * FROM paid_tasks
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()

            return dict(registro) if registro else None
