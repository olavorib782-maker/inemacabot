"""Cliente assíncrono para provedores compatíveis com a API OpenAI."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any

from openai import APIError, APIStatusError, APITimeoutError, AsyncOpenAI, OpenAIError

from config import Settings


DEFAULT_TIMEOUT_SECONDS = 30.0

logger = logging.getLogger(__name__)

HistoryMessage = Mapping[str, str]


class AIClientError(RuntimeError):
    """Erro seguro para exibir quando o provedor de IA não responde."""


class AIClient:
    """Envia contexto de conversa a um provedor compatível com OpenAI."""

    def __init__(self, settings: Settings, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self._model = settings.ai_model
        self._system_prompt = settings.ai_system_prompt
        self._client = AsyncOpenAI(
            api_key=settings.ai_api_key,
            base_url=settings.ai_base_url,
            timeout=timeout,
        )

    async def get_response(
        self, history: Sequence[HistoryMessage], user_message: str
    ) -> str:
        """Retorna a resposta textual da IA para o histórico e mensagem fornecidos."""
        messages: list[dict[str, str]] = [
            {"role": "system", "content": self._system_prompt},
        ]
        messages.extend(dict(message) for message in history)
        messages.append({"role": "user", "content": user_message})

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
            )
        except APITimeoutError as error:
            logger.warning("Tempo limite ao chamar a API de IA (%s).", type(error).__name__)
            raise AIClientError("A IA demorou para responder. Tente novamente em instantes.") from None
        except (APIStatusError, APIError, OpenAIError) as error:
            logger.warning("Falha ao chamar a API de IA (%s).", type(error).__name__)
            raise AIClientError("A IA está indisponível no momento. Tente novamente mais tarde.") from None
        except Exception as error:
            logger.error("Falha inesperada ao chamar a API de IA (%s).", type(error).__name__)
            raise AIClientError("Não foi possível obter uma resposta da IA no momento.") from None

        return self._extract_content(response)

    @staticmethod
    def _extract_content(response: Any) -> str:
        """Extrai uma resposta textual não vazia de uma conclusão de chat."""
        choices = getattr(response, "choices", None)
        if not choices:
            raise AIClientError("A IA retornou uma resposta inválida. Tente novamente.")

        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None)
        if not isinstance(content, str) or not content.strip():
            raise AIClientError("A IA retornou uma resposta vazia. Tente novamente.")

        return content.strip()
