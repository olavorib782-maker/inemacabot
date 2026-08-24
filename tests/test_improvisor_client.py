from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Callable

import pytest

from improvisor_client import (
    ImproVisorClient,
    ImproVisorClientConfig,
    ImproVisorClientError,
)


class _FakeProcess:
    def __init__(
        self,
        returncode: int = 0,
        on_communicate: Callable[[], None] | None = None,
        never_finishes: bool = False,
    ) -> None:
        self.returncode = returncode
        self._on_communicate = on_communicate
        self._never_finishes = never_finishes
        self.killed = False
        self.waited = False

    async def communicate(self) -> tuple[bytes, bytes]:
        if self._never_finishes:
            await asyncio.Event().wait()
        if self._on_communicate is not None:
            self._on_communicate()
        return b"concluido", b"detalhe tecnico"

    def kill(self) -> None:
        self.killed = True

    async def wait(self) -> int:
        self.waited = True
        return self.returncode


def _config(tmp_path: Path, timeout: float = 1.0) -> ImproVisorClientConfig:
    return ImproVisorClientConfig(
        java_executable="java-test",
        classpath="bridge;improvisor",
        improvisor_home=tmp_path,
        user_home=tmp_path / "home",
        timeout_seconds=timeout,
    )


def _input(tmp_path: Path) -> Path:
    input_file = tmp_path / "entrada.ls"
    input_file.write_text("(title Teste)", encoding="utf-8")
    return input_file


def _install_process(
    monkeypatch: pytest.MonkeyPatch, process: _FakeProcess
) -> list[tuple[tuple[object, ...], dict[str, object]]]:
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    async def fake_create_subprocess_exec(
        *args: object, **kwargs: object
    ) -> _FakeProcess:
        calls.append((args, kwargs))
        return process

    monkeypatch.setattr(
        "improvisor_client.asyncio.create_subprocess_exec",
        fake_create_subprocess_exec,
    )
    return calls


@pytest.mark.asyncio
async def test_conversao_bem_sucedida(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "saida.xml"
    process = _FakeProcess(
        on_communicate=lambda: output.write_text("<score-partwise/>", encoding="utf-8")
    )
    calls = _install_process(monkeypatch, process)

    result = await ImproVisorClient(_config(tmp_path)).convert(_input(tmp_path), output)

    assert result.output_path == output
    assert result.stdout == "concluido"
    args, kwargs = calls[0]
    assert args[0] == "java-test"
    assert "-Djava.awt.headless=true" in args
    assert "-Xmx256m" in args
    assert args[-2:] == (str(tmp_path / "entrada.ls"), str(output))
    assert kwargs["stdout"] == asyncio.subprocess.PIPE
    assert kwargs["stderr"] == asyncio.subprocess.PIPE
    assert "shell" not in kwargs


@pytest.mark.asyncio
async def test_generate_guidetones_chama_operacao_sem_shell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "guide-tones.xml"
    process = _FakeProcess(
        on_communicate=lambda: output.write_text("<score-partwise/>", encoding="utf-8")
    )
    calls = _install_process(monkeypatch, process)

    result = await ImproVisorClient(_config(tmp_path)).generate_guidetones(
        _input(tmp_path), output
    )

    assert result.output_path == output
    assert result.stdout == "concluido"
    args, kwargs = calls[0]
    assert args[-4:] == (
        "ImproVisorBridge",
        "guidetones",
        str(tmp_path / "entrada.ls"),
        str(output),
    )
    assert kwargs["stdout"] == asyncio.subprocess.PIPE
    assert kwargs["stderr"] == asyncio.subprocess.PIPE
    assert "shell" not in kwargs


@pytest.mark.asyncio
async def test_generate_guidetones_exit_code_diferente_de_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_process(monkeypatch, _FakeProcess(returncode=7))

    with pytest.raises(ImproVisorClientError, match="conversão musical falhou"):
        await ImproVisorClient(_config(tmp_path)).generate_guidetones(
            _input(tmp_path), tmp_path / "saida.xml"
        )


@pytest.mark.asyncio
async def test_generate_guidetones_timeout_mata_e_aguarda_processo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    process = _FakeProcess(never_finishes=True)
    _install_process(monkeypatch, process)

    with pytest.raises(ImproVisorClientError, match="tempo limite"):
        await ImproVisorClient(
            _config(tmp_path, timeout=0.01)
        ).generate_guidetones(_input(tmp_path), tmp_path / "saida.xml")

    assert process.killed is True
    assert process.waited is True


@pytest.mark.asyncio
async def test_generate_guidetones_xml_nao_criado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_process(monkeypatch, _FakeProcess())

    with pytest.raises(ImproVisorClientError, match="não gerou"):
        await ImproVisorClient(_config(tmp_path)).generate_guidetones(
            _input(tmp_path), tmp_path / "saida.xml"
        )


@pytest.mark.asyncio
async def test_generate_guidetones_xml_invalido(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "saida.xml"
    process = _FakeProcess(
        on_communicate=lambda: output.write_text("<score>", encoding="utf-8")
    )
    _install_process(monkeypatch, process)

    with pytest.raises(ImproVisorClientError, match="MusicXML inválido"):
        await ImproVisorClient(_config(tmp_path)).generate_guidetones(
            _input(tmp_path), output
        )


@pytest.mark.asyncio
async def test_exit_code_diferente_de_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_process(monkeypatch, _FakeProcess(returncode=7))

    with pytest.raises(ImproVisorClientError, match="conversão musical falhou"):
        await ImproVisorClient(_config(tmp_path)).convert(
            _input(tmp_path), tmp_path / "saida.xml"
        )


@pytest.mark.asyncio
async def test_timeout_mata_e_aguarda_processo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    process = _FakeProcess(never_finishes=True)
    _install_process(monkeypatch, process)

    with pytest.raises(ImproVisorClientError, match="tempo limite"):
        await ImproVisorClient(_config(tmp_path, timeout=0.01)).convert(
            _input(tmp_path), tmp_path / "saida.xml"
        )

    assert process.killed is True
    assert process.waited is True


@pytest.mark.asyncio
async def test_xml_nao_criado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_process(monkeypatch, _FakeProcess())

    with pytest.raises(ImproVisorClientError, match="não gerou"):
        await ImproVisorClient(_config(tmp_path)).convert(
            _input(tmp_path), tmp_path / "saida.xml"
        )


@pytest.mark.asyncio
async def test_xml_invalido(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "saida.xml"
    process = _FakeProcess(
        on_communicate=lambda: output.write_text("<score>", encoding="utf-8")
    )
    _install_process(monkeypatch, process)

    with pytest.raises(ImproVisorClientError, match="MusicXML inválido"):
        await ImproVisorClient(_config(tmp_path)).convert(_input(tmp_path), output)


@pytest.mark.asyncio
async def test_input_invalido(tmp_path: Path) -> None:
    input_file = tmp_path / "entrada.txt"
    input_file.write_text("conteudo", encoding="utf-8")

    with pytest.raises(ImproVisorClientError, match="extensão .ls"):
        await ImproVisorClient(_config(tmp_path)).convert(
            input_file, tmp_path / "saida.xml"
        )


@pytest.mark.asyncio
async def test_output_invalido(tmp_path: Path) -> None:
    with pytest.raises(ImproVisorClientError, match="extensão .xml"):
        await ImproVisorClient(_config(tmp_path)).convert(
            _input(tmp_path), tmp_path / "saida.txt"
        )
