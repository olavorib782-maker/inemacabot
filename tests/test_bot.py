from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from bot import TELEGRAM_MAX_MESSAGE_LENGTH, _is_authorized, split_message


@dataclass
class _FakeSettings:
    telegram_allowed_user_id: int = 42


def _fake_update(user_id: int | None) -> SimpleNamespace:
    user = None if user_id is None else SimpleNamespace(id=user_id)
    return SimpleNamespace(effective_user=user)


def _fake_services(allowed_user_id: int = 42) -> SimpleNamespace:
    return SimpleNamespace(settings=_FakeSettings(telegram_allowed_user_id=allowed_user_id))


def test_is_authorized_permite_usuario_correto() -> None:
    assert _is_authorized(_fake_update(42), _fake_services()) is True


def test_is_authorized_bloqueia_usuario_diferente() -> None:
    assert _is_authorized(_fake_update(999), _fake_services()) is False


def test_is_authorized_bloqueia_quando_sem_usuario() -> None:
    assert _is_authorized(_fake_update(None), _fake_services()) is False


def test_split_message_nao_divide_texto_curto() -> None:
    text = "Olá, tudo bem?"
    assert split_message(text) == [text]


def test_split_message_divide_texto_acima_do_limite() -> None:
    text = "a" * (TELEGRAM_MAX_MESSAGE_LENGTH + 100)
    parts = split_message(text)
    assert len(parts) == 2
    assert all(len(part) <= TELEGRAM_MAX_MESSAGE_LENGTH for part in parts)
    assert "".join(parts) == text


def test_split_message_prefere_quebrar_em_espaco() -> None:
    limit = 20
    text = "palavra " * 10
    parts = split_message(text, limit=limit)
    assert all(len(part) <= limit for part in parts)
    for part in parts[:-1]:
        assert not part.endswith("palavr")


def test_split_message_prefere_quebrar_em_quebra_de_linha() -> None:
    limit = 15
    text = "linha um\nlinha dois\nlinha tres"
    parts = split_message(text, limit=limit)
    assert all(len(part) <= limit for part in parts)


def test_split_message_corta_palavra_unica_maior_que_limite() -> None:
    limit = 10
    text = "a" * 25
    parts = split_message(text, limit=limit)
    assert all(len(part) <= limit for part in parts)
    assert "".join(parts) == text


def test_split_message_preserva_conteudo_total() -> None:
    text = ("Frase número. " * 500).strip()
    parts = split_message(text)
    assert all(len(part) <= TELEGRAM_MAX_MESSAGE_LENGTH for part in parts)
    assert sum(len(p) for p in parts) <= len(text)
    assert len(parts) > 0
