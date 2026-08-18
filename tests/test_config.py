from __future__ import annotations

import pytest

from config import ConfigurationError, load_config


REQUIRED_ENV = {
    "TELEGRAM_BOT_TOKEN": "123456:abc-token",
    "TELEGRAM_ALLOWED_USER_ID": "42",
    "AI_API_KEY": "sk-test",
    "AI_BASE_URL": "https://api.openai.com/v1",
    "AI_MODEL": "gpt-4o-mini",
    "AI_SYSTEM_PROMPT": "Você é um assistente prestativo.",
}


@pytest.fixture(autouse=True)
def disable_dotenv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("config.load_dotenv", lambda: None)


def _set_env(
    monkeypatch: pytest.MonkeyPatch,
    overrides: dict[str, str] | None = None,
) -> None:
    values = {**REQUIRED_ENV, **(overrides or {})}

    for key, value in values.items():
        monkeypatch.setenv(key, value)


def _unset_env(monkeypatch: pytest.MonkeyPatch, key: str) -> None:
    monkeypatch.delenv(key, raising=False)


def test_load_config_com_todas_variaveis_validas(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_env(monkeypatch)
    monkeypatch.delenv("HISTORY_MAX_MESSAGES", raising=False)

    settings = load_config()

    assert settings.telegram_bot_token == REQUIRED_ENV["TELEGRAM_BOT_TOKEN"]
    assert settings.telegram_allowed_user_id == 42
    assert settings.ai_api_key == REQUIRED_ENV["AI_API_KEY"]
    assert settings.ai_base_url == REQUIRED_ENV["AI_BASE_URL"]
    assert settings.ai_model == REQUIRED_ENV["AI_MODEL"]
    assert settings.history_max_messages == 20
    assert settings.jobs_db_path == "jobs.db"


@pytest.mark.parametrize("missing_key", sorted(REQUIRED_ENV.keys()))
def test_load_config_falha_quando_variavel_obrigatoria_ausente(
    monkeypatch: pytest.MonkeyPatch,
    missing_key: str,
) -> None:
    _set_env(monkeypatch)
    _unset_env(monkeypatch, missing_key)

    with pytest.raises(ConfigurationError):
        load_config()


def test_load_config_falha_com_user_id_nao_numerico(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_env(monkeypatch, {"TELEGRAM_ALLOWED_USER_ID": "nao-e-um-numero"})

    with pytest.raises(ConfigurationError):
        load_config()


def test_load_config_falha_com_user_id_nao_positivo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_env(monkeypatch, {"TELEGRAM_ALLOWED_USER_ID": "0"})

    with pytest.raises(ConfigurationError):
        load_config()


def test_load_config_falha_com_base_url_invalida(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_env(monkeypatch, {"AI_BASE_URL": "nao-e-uma-url"})

    with pytest.raises(ConfigurationError):
        load_config()


def test_load_config_falha_com_history_max_messages_invalido(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_env(monkeypatch, {"HISTORY_MAX_MESSAGES": "-5"})

    with pytest.raises(ConfigurationError):
        load_config()


def test_load_config_usa_history_max_messages_customizado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_env(monkeypatch, {"HISTORY_MAX_MESSAGES": "5"})

    settings = load_config()

    assert settings.history_max_messages == 5


def test_load_config_usa_caminho_de_jobs_customizado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_env(monkeypatch, {"JOBS_DB_PATH": "dados/jobs.sqlite3"})

    settings = load_config()

    assert settings.jobs_db_path == "dados/jobs.sqlite3"
