"""Preparação inteligente de narrações para produção audiovisual."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from pathlib import Path

from agent_runner import AgentRunner
from artifact_store import ArtifactStore
from audio_service import (
    gerar_voz,
    medir_duracao,
    validar_duracao,
)
from job import Job
from roteiro_validator import (
    contar_palavras,
    extrair_duracao,
    extrair_narracao,
    limite_palavras,
    validar_roteiro,
)


logger = logging.getLogger(__name__)


class NarrationError(RuntimeError):
    """Indica que a narração não pôde ser aprovada."""


@dataclass(frozen=True, slots=True)
class NarrationResult:
    resposta: str
    texto: str
    relative_path: str
    audio_path: Path
    duracao_real: float
    duracao_alvo: int
    tentativas: int


class NarrationService:
    """Gera, mede e revisa locuções automaticamente."""

    def __init__(
        self,
        agent_runner: AgentRunner,
        artifact_store: ArtifactStore,
        max_revisoes: int = 2,
    ) -> None:
        if max_revisoes < 0:
            raise ValueError("Quantidade de revisões inválida.")

        self.agent_runner = agent_runner
        self.artifact_store = artifact_store
        self.max_revisoes = max_revisoes

    async def preparar(
        self,
        job: Job,
        resposta: str,
        voz: str = "pt-BR-AntonioNeural",
    ) -> NarrationResult:

        alvo = extrair_duracao(job.descricao)

        if alvo is None or alvo <= 0:
            raise NarrationError(
                "Informe uma duração positiva para a narração."
            )

        relative_path, audio_path = self.artifact_store.job_path(
            job.id,
            "narracao.mp3",
        )

        _, temporario = self.artifact_store.job_path(
            job.id,
            "narracao-temporaria.mp3",
        )

        limite = limite_palavras(alvo)
        motivo = ""

        try:
            for tentativa in range(1, self.max_revisoes + 2):

                aprovado_texto, motivo = validar_roteiro(
                    job.descricao,
                    resposta,
                )

                texto = extrair_narracao(resposta)
                orientacao = ""

                if aprovado_texto and texto:

                    temporario.unlink(missing_ok=True)

                    await gerar_voz(
                        texto=texto,
                        output_path=temporario,
                        voz=voz,
                    )

                    duracao = await medir_duracao(temporario)

                    aprovado, acao = validar_duracao(
                        duracao,
                        alvo,
                    )

                    palavras = contar_palavras(texto)

                    logger.info(
                        "Job %s | Narracao %s/%s | "
                        "Palavras=%s | Audio=%.3fs | "
                        "Alvo=%ss | Resultado=%s",
                        job.id,
                        tentativa,
                        self.max_revisoes + 1,
                        palavras,
                        duracao,
                        alvo,
                        acao,
                    )

                    if aprovado:
                        temporario.replace(audio_path)

                        return NarrationResult(
                            resposta=resposta,
                            texto=texto,
                            relative_path=relative_path,
                            audio_path=audio_path,
                            duracao_real=duracao,
                            duracao_alvo=alvo,
                            tentativas=tentativa,
                        )

                    motivo = (
                        f"Duração real: {duracao:.3f}s. "
                        f"Duração alvo: {alvo}s. "
                        f"Necessário {acao} a narração."
                    )

                    meta = round(
                        palavras / duracao * alvo * 0.85
                    )

                    if acao == "ampliar":
                        meta = max(palavras + 1, meta)
                    elif acao == "reduzir":
                        meta = min(palavras - 1, meta)

                    meta = max(1, min(limite, meta))

                    orientacao = (
                        f"A narracao anterior tinha "
                        f"{palavras} palavras.\n"
                        f"Velocidade real observada: "
                        f"{palavras / duracao * 60:.1f} "
                        "palavras por minuto.\n"
                        f"Nova meta: {meta} palavras.\n"
                        "Ajuste efetivamente o texto falado "
                        "para se aproximar dessa meta.\n"
                        "Nao altere apenas a duracao "
                        "estimada informada na resposta.\n"
                    )

                if tentativa > self.max_revisoes:
                    break

                instrucao = (
                    f"{job.descricao}\n\n"
                    "REVISÃO OBRIGATÓRIA DA NARRAÇÃO:\n"
                    f"{motivo}\n"
                    f"{orientacao}"
                    f"Limite máximo: {limite} palavras.\n"
                    f"Busque uma duração entre "
                    f"{alvo * 0.70:.2f} e {alvo} segundos.\n"
                    "Preserve os fatos fornecidos pelo usuário.\n"
                    "Não invente datas, nomes ou informações.\n"
                    "Mantenha a naturalidade da locução.\n"
                    "Entregue a resposta completa no formato "
                    "original da skill.\n\n"
                    f"RESPOSTA ANTERIOR:\n{resposta}"
                )

                job_revisao = replace(
                    job,
                    descricao=instrucao,
                )

                resposta = await self.agent_runner.run(
                    job_revisao
                )

            raise NarrationError(
                "Narração não aprovada após as tentativas "
                f"permitidas. Motivo: {motivo}"
            )

        finally:
            temporario.unlink(missing_ok=True)
