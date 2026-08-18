"""Notificação de resultados de Jobs."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from job import Job


Sender = Callable[[int, str], Awaitable[None]]


class ResultNotifier:
    """Entrega resultados de Jobs ao usuário através de um sender."""

    def __init__(self, sender: Sender) -> None:
        self.sender = sender

    async def notify(self, job: Job) -> None:
        """Envia o resultado do Job para o chat correspondente."""
        message = self._build_message(job)
        await self.sender(job.chat_id, message)

    async def notify_failure(self, job: Job) -> None:
        """Informa com segurança que o processamento do Job falhou."""
        message = self._build_failure_message(job)
        await self.sender(job.chat_id, message)

    @staticmethod
    def _build_message(job: Job) -> str:
        """Monta a mensagem de resultado."""
        return (
            "✅ Trabalho concluído!\n\n"
            f"Job: {job.id}\n"
            f"Skill: {job.skill}\n\n"
            f"{job.resultado}"
        )

    @staticmethod
    def _build_failure_message(job: Job) -> str:
        """Monta uma mensagem de falha sem detalhes técnicos."""
        return (
            "❌ Não foi possível concluir o trabalho.\n\n"
            f"Job: {job.id}\n"
            f"Skill: {job.skill}\n\n"
            "Tente novamente mais tarde."
        )
