from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest
from openai import APITimeoutError

from ai_client import AIClient, AIClientError


@dataclass
class _FakeSettings:
    ai_model: str = "gpt-4o-mini"
    ai_system_prompt: str = "system prompt"
    ai_api_key: str = "sk-test"
    ai_base_url: str = "https://api.openai.com/v1"


class _FakeCompletions:
    def __init__(self, response: Any = None, error: Exception | None = None) -> None:
        self._response = response
        self._error = error
        self.last_kwargs: dict[str, Any] | None = None

    async def create(self, **kwargs: Any) -> Any:
        self.last_kwargs = kwargs
        if self._error is not None:
            raise self._error
        return self._response


def _build_client(monkeypatch: pytest.MonkeyPatch, completions: _FakeCompletions) -> AIClient:
    fake_openai_instance = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    monkeypatch.setattr("ai_client.AsyncOpenAI", lambda **kwargs: fake_openai_instance)
    return AIClient(_FakeSettings())


def _make_response(content: str) -> Any:
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    return SimpleNamespace(choices=[choice])


@pytest.mark.asyncio
async def test_get_response_retorna_conteudo_da_ia(monkeypatch: pytest.MonkeyPatch) -> None:
    completions = _FakeCompletions(response=_make_response("  Olá, como posso ajudar?  "))
    client = _build_client(monkeypatch, completions)
    result = await client.get_response(history=[], user_message="Oi")
    assert result == "Olá, como posso ajudar?"
    assert completions.last_kwargs["messages"][0] == {
        "role": "system", "content": "system prompt",
    }
    assert completions.last_kwargs["messages"][-1] == {"role": "user", "content": "Oi"}


@pytest.mark.asyncio
async def test_get_response_inclui_historico_na_chamada(monkeypatch: pytest.MonkeyPatch) -> None:
    completions = _FakeCompletions(response=_make_response("ok"))
    client = _build_client(monkeypatch, completions)
    history = [{"role": "user", "content": "primeira"}, {"role": "assistant", "content": "resposta"}]
    await client.get_response(history=history, user_message="segunda")
    messages = completions.last_kwargs["messages"]
    assert messages[1] == history[0]
    assert messages[2] == history[1]


@pytest.mark.asyncio
async def test_get_response_trata_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    completions = _FakeCompletions(error=APITimeoutError(request=SimpleNamespace()))
    client = _build_client(monkeypatch, completions)
    with pytest.raises(AIClientError):
        await client.get_response(history=[], user_message="Oi")


@pytest.mark.asyncio
async def test_get_response_trata_resposta_vazia(monkeypatch: pytest.MonkeyPatch) -> None:
    completions = _FakeCompletions(response=_make_response(""))
    client = _build_client(monkeypatch, completions)
    with pytest.raises(AIClientError):
        await client.get_response(history=[], user_message="Oi")


@pytest.mark.asyncio
async def test_get_response_trata_resposta_sem_choices(monkeypatch: pytest.MonkeyPatch) -> None:
    completions = _FakeCompletions(response=SimpleNamespace(choices=[]))
    client = _build_client(monkeypatch, completions)
    with pytest.raises(AIClientError):
        await client.get_response(history=[], user_message="Oi")


@pytest.mark.asyncio
async def test_get_response_trata_erro_inesperado(monkeypatch: pytest.MonkeyPatch) -> None:
    completions = _FakeCompletions(error=RuntimeError("boom"))
    client = _build_client(monkeypatch, completions)
    with pytest.raises(AIClientError):
        await client.get_response(history=[], user_message="Oi")
