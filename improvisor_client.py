"""Cliente assíncrono isolado para a ponte headless do Impro-Visor."""

from __future__ import annotations

import asyncio
import os
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


class ImproVisorClientError(RuntimeError):
    """Erro seguro e esperado ao converter um leadsheet."""


@dataclass(frozen=True, slots=True)
class ImproVisorClientConfig:
    """Configuração local necessária para executar a ponte Java."""

    classpath: str
    improvisor_home: Path
    user_home: Path
    java_executable: str = "java"
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not self.classpath.strip():
            raise ValueError("classpath não pode ser vazio")
        if not self.java_executable.strip():
            raise ValueError("java_executable não pode ser vazio")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds deve ser positivo")

    @classmethod
    def from_env(cls) -> "ImproVisorClientConfig":
        """Carrega caminhos locais sem fixá-los no código versionado."""
        try:
            classpath = os.environ["IMPROVISOR_BRIDGE_CLASSPATH"]
            improvisor_home = Path(os.environ["IMPROVISOR_HOME"])
            user_home = Path(os.environ["IMPROVISOR_USER_HOME"])
        except KeyError as error:
            raise ImproVisorClientError(
                "Configuração do Impro-Visor ausente."
            ) from error

        timeout_text = os.getenv("IMPROVISOR_TIMEOUT_SECONDS", "30")
        try:
            timeout = float(timeout_text)
        except ValueError as error:
            raise ImproVisorClientError(
                "Configuração de timeout do Impro-Visor inválida."
            ) from error

        try:
            return cls(
                java_executable=os.getenv("IMPROVISOR_JAVA_EXECUTABLE", "java"),
                classpath=classpath,
                improvisor_home=improvisor_home,
                user_home=user_home,
                timeout_seconds=timeout,
            )
        except ValueError as error:
            raise ImproVisorClientError(
                "Configuração do Impro-Visor inválida."
            ) from error


@dataclass(frozen=True, slots=True)
class ImproVisorConversionResult:
    output_path: Path
    stdout: str
    duration_seconds: float


class ImproVisorClient:
    """Executa somente a classe conhecida ``ImproVisorBridge``."""

    def __init__(self, config: ImproVisorClientConfig) -> None:
        self._config = config

    async def convert(
        self, input_path: str | Path, output_path: str | Path
    ) -> ImproVisorConversionResult:
        return await self._run_bridge(input_path, output_path)

    async def generate_guidetones(
        self, input_path: str | Path, output_path: str | Path
    ) -> ImproVisorConversionResult:
        """Gera uma linha de guide tones e a exporta como MusicXML."""
        return await self._run_bridge(input_path, output_path, "guidetones")

    async def _run_bridge(
        self,
        input_path: str | Path,
        output_path: str | Path,
        *operation_args: str,
    ) -> ImproVisorConversionResult:
        input_file = Path(input_path)
        output_file = Path(output_path)
        self._validate_paths(input_file, output_file)

        # Impede que um XML antigo seja confundido com a saída desta execução.
        try:
            output_file.unlink(missing_ok=True)
        except OSError as error:
            raise ImproVisorClientError(
                "Não foi possível preparar o arquivo de saída."
            ) from error

        command = (
            self._config.java_executable,
            "-Djava.awt.headless=true",
            f"-Duser.home={self._config.user_home}",
            "-Xmx256m",
            "-cp",
            self._config.classpath,
            "ImproVisorBridge",
            *operation_args,
            str(input_file),
            str(output_file),
        )

        started_at = time.monotonic()
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(self._config.improvisor_home),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (OSError, ValueError) as error:
            raise ImproVisorClientError(
                "Não foi possível iniciar a conversão musical."
            ) from error

        try:
            stdout_bytes, _stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=self._config.timeout_seconds
            )
        except TimeoutError as error:
            process.kill()
            await process.wait()
            raise ImproVisorClientError(
                "A conversão musical excedeu o tempo limite."
            ) from error

        if process.returncode != 0:
            raise ImproVisorClientError("A conversão musical falhou.")
        if not output_file.is_file():
            raise ImproVisorClientError("A conversão não gerou o arquivo MusicXML.")

        try:
            ET.parse(output_file)
        except (ET.ParseError, OSError) as error:
            raise ImproVisorClientError(
                "A conversão gerou um arquivo MusicXML inválido."
            ) from error

        return ImproVisorConversionResult(
            output_path=output_file,
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            duration_seconds=time.monotonic() - started_at,
        )

    @staticmethod
    def _validate_paths(input_file: Path, output_file: Path) -> None:
        if input_file.suffix.lower() != ".ls":
            raise ImproVisorClientError("O arquivo de entrada deve usar a extensão .ls.")
        if not input_file.is_file():
            raise ImproVisorClientError("O arquivo .ls de entrada não existe.")
        if output_file.suffix.lower() != ".xml":
            raise ImproVisorClientError("O arquivo de saída deve usar a extensão .xml.")
        if not output_file.parent.is_dir():
            raise ImproVisorClientError("O diretório de saída não existe.")
