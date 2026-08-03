"""Carregamento e validação da configuração do bot.

As credenciais devem ser fornecidas por variáveis de ambiente, normalmente por
meio de um arquivo ``.env`` local que não deve ser versionado.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse

from dotenv import load_dotenv


DEFAULT_HISTORY_MAX_MESSAGES = 20


class ConfigurationError(ValueError):
    """Indica uma variável de configuração ausente ou inválida."""


@dataclass(frozen=True, slots=True)
class Settings:
    """Configurações validadas necessárias para executar o bot."""

    telegram_bot_token: str
    telegram_allowed_user_id: int
    ai_api_key: str
    ai_base_url: str
    ai_model: str
    ai_system_prompt: str
    history_max_messages: int


def _required_value(name: str) -> str:
    """Obtém uma variável obrigatória e rejeita valores vazios."""
    value = os.getenv(name)
    if value is None or not value.strip():
        raise ConfigurationError(
            f"Configuração obrigatória ausente ou vazia: {name}. "
            "Defina-a no ambiente ou no arquivo .env."
        )
    return value.strip()


def _positive_integer(name: str, value: str) -> int:
    """Converte uma configuração numérica em inteiro positivo."""
    try:
        number = int(value)
    except ValueError as error:
        raise ConfigurationError(
            f"Configuração inválida: {name} deve ser um número inteiro positivo."
        ) from error

    if number <= 0:
        raise ConfigurationError(
            f"Configuração inválida: {name} deve ser um número inteiro positivo."
        )
    return number


def _validate_base_url(value: str) -> str:
    """Garante que a URL base da API use HTTP ou HTTPS e tenha host."""
    parsed_url = urlparse(value)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ConfigurationError(
            "Configuração inválida: AI_BASE_URL deve ser uma URL HTTP ou HTTPS válida."
        )
    return value


def load_config() -> Settings:
    """Carrega o arquivo .env e retorna as configurações já validadas."""
    load_dotenv()

    telegram_allowed_user_id = _positive_integer(
        "TELEGRAM_ALLOWED_USER_ID", _required_value("TELEGRAM_ALLOWED_USER_ID")
    )

    history_value = os.getenv("HISTORY_MAX_MESSAGES", str(DEFAULT_HISTORY_MAX_MESSAGES))
    if not history_value.strip():
        history_value = str(DEFAULT_HISTORY_MAX_MESSAGES)

    return Settings(
        telegram_bot_token=_required_value("TELEGRAM_BOT_TOKEN"),
        telegram_allowed_user_id=telegram_allowed_user_id,
        ai_api_key=_required_value("AI_API_KEY"),
        ai_base_url=_validate_base_url(_required_value("AI_BASE_URL")),
        ai_model=_required_value("AI_MODEL"),
        ai_system_prompt=_required_value("AI_SYSTEM_PROMPT"),
        history_max_messages=_positive_integer("HISTORY_MAX_MESSAGES", history_value),
    )
