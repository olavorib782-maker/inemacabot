from __future__ import annotations

import asyncio

import pytest

from conversation_history import ConversationHistory


@pytest.mark.parametrize("invalid_value", [0, -1, -10])
def test_init_rejeita_max_messages_nao_positivo(invalid_value: int) -> None:
    with pytest.raises(ValueError):
        ConversationHistory(invalid_value)


@pytest.mark.parametrize("invalid_value", ["10", 3.5, None, True, False])
def test_init_rejeita_max_messages_nao_inteiro_ou_bool(invalid_value: object) -> None:
    with pytest.raises(ValueError):
        ConversationHistory(invalid_value)  # type: ignore[arg-type]


def test_init_aceita_max_messages_valido() -> None:
    history = ConversationHistory(10)
    assert history.max_messages == 10


def test_get_messages_comeca_vazio() -> None:
    history = ConversationHistory(10)
    assert history.get_messages() == []


def test_add_pair_adiciona_mensagens_user_e_assistant_na_ordem() -> None:
    history = ConversationHistory(10)
    history.add_pair("Oi", "Olá! Como posso ajudar?")
    assert history.get_messages() == [
        {"role": "user", "content": "Oi"},
        {"role": "assistant", "content": "Olá! Como posso ajudar?"},
    ]


def test_get_messages_retorna_copia_independente() -> None:
    history = ConversationHistory(10)
    history.add_pair("Oi", "Olá!")
    messages = history.get_messages()
    messages.append({"role": "user", "content": "mutação externa"})
    messages[0]["content"] = "alterado"
    assert history.get_messages() == [
        {"role": "user", "content": "Oi"},
        {"role": "assistant", "content": "Olá!"},
    ]


def test_add_pair_respeita_limite_par() -> None:
    history = ConversationHistory(4)
    history.add_pair("um", "resposta um")
    history.add_pair("dois", "resposta dois")
    history.add_pair("tres", "resposta tres")
    messages = history.get_messages()
    assert len(messages) == 4
    assert messages[0] == {"role": "user", "content": "dois"}
    assert messages[-1] == {"role": "assistant", "content": "resposta tres"}


def test_add_pair_com_limite_impar_arredonda_para_baixo() -> None:
    history = ConversationHistory(5)
    history.add_pair("um", "resposta um")
    history.add_pair("dois", "resposta dois")
    history.add_pair("tres", "resposta tres")
    messages = history.get_messages()
    assert len(messages) == 4
    assert messages[0] == {"role": "user", "content": "dois"}


def test_add_pair_com_limite_minimo_mantem_apenas_ultimo_par() -> None:
    history = ConversationHistory(1)
    history.add_pair("um", "resposta um")
    assert history.get_messages() == []


def test_clear_remove_todo_historico() -> None:
    history = ConversationHistory(10)
    history.add_pair("Oi", "Olá!")
    history.clear()
    assert history.get_messages() == []


def test_clear_em_historico_ja_vazio_nao_falha() -> None:
    history = ConversationHistory(10)
    history.clear()
    assert history.get_messages() == []


def test_history_expoe_asyncio_lock() -> None:
    history = ConversationHistory(10)
    assert isinstance(history.lock, asyncio.Lock)
