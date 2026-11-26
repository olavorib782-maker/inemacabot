"""Configuracao de narracao ElevenLabs V3 via KIE."""

from __future__ import annotations

from pathlib import Path

from kie_client import KieClient
from paid_task_guard import PaidTaskGuard, PaidTaskError
from audio_service import validar_audio_mp3

MODELO_ELEVENLABS = "elevenlabs/text-to-dialogue-v3"
VOZ_BRIAN = "nPczCjzI2devNBz1zQrb"

MAX_CARACTERES = 5000


def preparar_parametros(
    texto: str,
    voz: str = VOZ_BRIAN,
    estabilidade: float = 0.5,
) -> dict:
    """Prepara a narracao sem realizar chamadas externas."""

    texto = texto.strip()

    if not texto:
        raise ValueError("Texto da narracao vazio.")

    if len(texto) > MAX_CARACTERES:
        raise ValueError("Texto excede 5000 caracteres.")

    if not voz.strip():
        raise ValueError("Voz nao informada.")

    if estabilidade not in (0.0, 0.5, 1.0):
        raise ValueError("Estabilidade invalida.")

    return {
        "dialogue": [
            {
                "text": texto,
                "voice": voz.strip(),
            }
        ],
        "stability": estabilidade,
        "language_code": "pt",
    }


async def gerar_narracao_premium(
    job_id: str,
    texto: str,
    output_path: Path,
    guard: PaidTaskGuard,
    cliente: KieClient,
    autorizado: bool = False,
    voz: str = VOZ_BRIAN,
) -> dict:
    """Gera narracao premium com controle de duplicidade."""

    if autorizado is not True:
        raise PermissionError(
            "Geracao premium nao autorizada."
        )

    parametros = preparar_parametros(texto, voz=voz)

    output_path = Path(output_path)

    registro = guard.consultar(job_id)

    if registro is not None:
        raise PaidTaskError(
            "Tarefa paga ja registrada. "
            "Consulte o registro antes de repetir."
        )

    guard.reservar(job_id, MODELO_ELEVENLABS)

    task_id = await cliente.criar_tarefa(
        MODELO_ELEVENLABS,
        parametros,
    )

    guard.registrar_task_id(job_id, task_id)

    url = await cliente.aguardar_resultado(task_id)

    arquivo = await cliente.baixar_resultado(
        url, output_path
    )

    duracao = await validar_audio_mp3(arquivo)

    return {
        "task_id": task_id,
        "arquivo": arquivo,
        "duracao_real": duracao,
        "voz": voz,
        "modelo": MODELO_ELEVENLABS,
        "caracteres": len(texto.strip()),
    }


async def recuperar_narracao_premium(
    job_id: str,
    output_path: Path,
    guard: PaidTaskGuard,
    cliente: KieClient,
) -> dict:
    """Recupera uma narracao sem criar nova tarefa paga."""

    registro = guard.consultar(job_id)

    if registro is None:
        raise PaidTaskError(
            "Nenhuma tarefa registrada para este job."
        )

    if registro["model"] != MODELO_ELEVENLABS:
        raise PaidTaskError(
            "Modelo incompativel com ElevenLabs."
        )

    task_id = registro.get("task_id")

    if registro["state"] != "submitted" or not task_id:
        raise PaidTaskError(
            "Task ID indisponivel. "
            "Confira o painel KIE antes de repetir."
        )

    url = await cliente.aguardar_resultado(task_id)

    arquivo = await cliente.baixar_resultado(
        url, Path(output_path)
    )

    duracao = await validar_audio_mp3(arquivo)

    return {
        "task_id": task_id,
        "arquivo": arquivo,
        "duracao_real": duracao,
        "modelo": MODELO_ELEVENLABS,
        "recuperado": True,
    }
