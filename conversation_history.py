"""Histórico em memória para o contexto enviado ao cliente de IA."""

from __future__ import annotations

import asyncio


HistoryMessage = dict[str, str]


class ConversationHistory:
    """Armazena pares completos de mensagens de uma conversa em memória."""

    def __init__(self, max_messages: int) -> None:
        if isinstance(max_messages, bool) or not isinstance(max_messages, int) or max_messages <= 0:
            raise ValueError("max_messages deve ser um número inteiro positivo.")

        self._max_messages = max_messages
        # Um limite ímpar é reduzido para o par completo imediatamente anterior.
        self._pair_limit = max_messages - (max_messages % 2)
        self._messages: list[HistoryMessage] = []
        # O bot futuro deve manter esta trava durante leitura, chamada à IA e gravação.
        self.lock = asyncio.Lock()

    @property
    def max_messages(self) -> int:
        """Retorna o limite de mensagens individuais solicitado na configuração."""
        return self._max_messages

    def get_messages(self) -> list[HistoryMessage]:
        """Retorna uma cópia do histórico atual, segura para o chamador alterar."""
        return [message.copy() for message in self._messages]

    def add_pair(self, user_message: str, assistant_message: str) -> None:
        """Adiciona um par user/assistant após uma resposta bem-sucedida da IA."""
        self._messages.extend(
            (
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_message},
            )
        )

        overflow = len(self._messages) - self._pair_limit
        if overflow > 0:
            del self._messages[:overflow]

    def clear(self) -> None:
        """Remove completamente o histórico mantido em memória."""
        self._messages.clear()
