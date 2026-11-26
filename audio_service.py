"""Serviço compartilhado de geração e validação de áudio."""

from __future__ import annotations

import asyncio
import logging
import json
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


async def validar_audio_mp3(arquivo: Path) -> float:
    """Valida formato, codec e duracao de um audio MP3."""

    arquivo = Path(arquivo).resolve()

    if not arquivo.is_file():
        raise FileNotFoundError(arquivo)

    if arquivo.stat().st_size == 0:
        raise RuntimeError("Arquivo de audio vazio.")

    proc = await asyncio.create_subprocess_exec(
        "ffprobe",
        "-v", "error",
        "-show_entries",
        "stream=codec_type,codec_name:format=format_name,duration",
        "-of", "json",
        str(arquivo),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=30,
        )
    except asyncio.TimeoutError as erro:
        if proc.returncode is None:
            proc.kill()
        await proc.communicate()
        raise RuntimeError(
            "Tempo esgotado na validacao do audio."
        ) from erro

    if proc.returncode != 0 or stderr.strip():
        raise RuntimeError(
            "FFprobe encontrou um audio invalido."
        )

    try:
        dados = json.loads(stdout)
        formato = dados.get("format", {})
        streams = dados.get("streams", [])

        duracao = float(formato.get("duration", 0))

    except (ValueError, TypeError) as erro:
        raise RuntimeError(
            "Metadados de audio invalidos."
        ) from erro

    if formato.get("format_name") != "mp3":
        raise RuntimeError("Formato recebido nao e MP3.")

    audios = [
        stream for stream in streams
        if stream.get("codec_type") == "audio"
    ]

    if not audios:
        raise RuntimeError("Nenhuma faixa de audio encontrada.")

    if any(
        stream.get("codec_name") != "mp3"
        for stream in audios
    ):
        raise RuntimeError("Codec de audio incompativel.")

    if not math.isfinite(duracao) or duracao <= 0:
        raise RuntimeError("Duracao de audio invalida.")

    logger.info(
        "Audio MP3 validado | Arquivo=%s | Duracao=%.3fs",
        arquivo.name,
        duracao,
    )

    return duracao
