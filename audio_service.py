"""Serviço compartilhado de geração e validação de áudio."""

from __future__ import annotations

import asyncio
import logging
import math
from pathlib import Path

import aiohttp
import edge_tts

logger = logging.getLogger(__name__)


async def gerar_voz(
    texto: str,
    output_path: Path,
    voz: str = "pt-BR-AntonioNeural",
    velocidade: str = "-8%",
) -> Path:
    """Gera uma locução usando Edge TTS."""

    texto = texto.strip()

    if not texto:
        raise ValueError("Texto da fala não pode estar vazio.")

    output_path = Path(output_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporario = output_path.with_name(
        output_path.name + ".part"
    )

    intervalos = (2, 5)
    max_tentativas = 3

    try:
        for tentativa in range(1, max_tentativas + 1):
            temporario.unlink(missing_ok=True)

            try:
                communicate = edge_tts.Communicate(
                    text=texto,
                    voice=voz,
                    rate=velocidade,
                )

                await asyncio.wait_for(
                    communicate.save(str(temporario)),
                    timeout=60,
                )

                if (
                    not temporario.is_file()
                    or temporario.stat().st_size == 0
                ):
                    raise edge_tts.exceptions.NoAudioReceived(
                        "Edge TTS nao gerou audio valido."
                    )

                temporario.replace(output_path)

                logger.info(
                    "Edge TTS concluido | Tentativa=%s/%s",
                    tentativa,
                    max_tentativas,
                )

                return output_path

            except (
                edge_tts.exceptions.NoAudioReceived,
                aiohttp.ClientConnectionError,
                asyncio.TimeoutError,
            ) as erro:
                logger.warning(
                    "Edge TTS falhou | Tentativa=%s/%s | Erro=%s",
                    tentativa,
                    max_tentativas,
                    type(erro).__name__,
                )

                temporario.unlink(missing_ok=True)

                if tentativa == max_tentativas:
                    raise RuntimeError(
                        "Edge TTS falhou apos 3 tentativas."
                    ) from erro

                await asyncio.sleep(
                    intervalos[tentativa - 1]
                )
    finally:
        temporario.unlink(missing_ok=True)


async def medir_duracao(arquivo: Path) -> float:
    """Mede a duração real de um arquivo de mídia."""

    arquivo = Path(arquivo)

    if not arquivo.is_file():
        raise FileNotFoundError(arquivo)

    proc = await asyncio.create_subprocess_exec(
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(arquivo),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        detalhe = stderr.decode("utf-8", errors="ignore")

        raise RuntimeError(
            f"Falha ao medir duração de {arquivo.name}: "
            f"{detalhe[-800:]}"
        )

    try:
        duracao = float(stdout.decode("utf-8").strip())
    except ValueError as exc:
        raise RuntimeError(
            f"FFprobe retornou duração inválida para {arquivo.name}."
        ) from exc

    if not math.isfinite(duracao) or duracao <= 0:
        raise RuntimeError("Duração de mídia inválida.")

    return duracao


def validar_duracao(
    duracao_real: float,
    duracao_alvo: float,
    proporcao_minima: float = 0.70,
) -> tuple[bool, str]:
    """Valida a duração da locução."""

    if not math.isfinite(duracao_alvo) or duracao_alvo <= 0:
        raise ValueError("Duração alvo inválida.")

    if not math.isfinite(duracao_real) or duracao_real <= 0:
        raise ValueError("Duração real inválida.")

    if not 0 < proporcao_minima <= 1:
        raise ValueError("Proporção mínima inválida.")

    minimo = duracao_alvo * proporcao_minima

    if duracao_real > duracao_alvo:
        return False, "reduzir"

    if duracao_real < minimo:
        return False, "ampliar"

    return True, "aprovado"
