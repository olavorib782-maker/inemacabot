
"""Worker especializado para a fila de textos."""

from __future__ import annotations

import re
from dataclasses import replace

from agent_runner import AgentRunner
from artifact_store import ArtifactStore
from job import Job
from job_artifact import JobArtifact
from narration_service import NarrationService
from queue_manager import QueueManager
from roteiro_validator import (
    contar_palavras,
    extrair_duracao,
    extrair_narracao,
    limite_palavras,
    validar_roteiro,
)
from workers.base_worker import BaseWorker
from job_event_bus import JobEventBus
from job_registry import JobRegistry


class TextWorker(BaseWorker):
    """Processa exclusivamente trabalhos da fila ``mkitextos``."""

    _FILA = "mkitextos"

    def __init__(
        self,
        queue_manager: QueueManager,
        fila: str = _FILA,
        event_bus: JobEventBus | None = None,
        job_registry: JobRegistry | None = None,
        agent_runner: AgentRunner | None = None,
        artifact_store: ArtifactStore | None = None,
    ) -> None:
        if fila != self._FILA:
            raise ValueError("TextWorker aceita apenas a fila mkitextos.")

        super().__init__(
            queue_manager,
            fila,
            event_bus=event_bus,
            job_registry=job_registry,
        )
        self.agent_runner = agent_runner
        self.artifact_store = artifact_store

    async def process_job(self, job: Job) -> str:
        """Gera textos e revisa roteiros que excedam a duração."""

        if self.agent_runner is None:
            return f"Job {job.id} processado pelo TextWorker."

        if (
            job.skill == "texto_avatar"
            and job.dados.get("gerar_audio") is True
        ):
            return await self._preparar_narracao(job)

        resultado = await self.agent_runner.run(job)

        # As outras habilidades não passam pelo validador.
        if job.skill not in {"roteiro", "texto_avatar"}:
            return resultado

        segundos = extrair_duracao(job.descricao)

        # Sem duração explícita, não há limite a conferir.
        if segundos is None:
            return resultado

        # Duração inválida: não solicitar uma revisão impossível.
        if segundos <= 0:
            return (
                "⚠️ Duração inválida.\n"
                "Informe uma duração maior que zero segundos "
                "para gerar um roteiro com tempo definido."
            )

        aprovado, motivo = validar_roteiro(
            job.descricao,
            resultado,
        )

        if aprovado:
            return self._atualizar_contagem(resultado)

        # Faz somente uma tentativa de revisão.
        limite = limite_palavras(segundos) if segundos > 0 else 0

        instrucao_revisao = (
            f"{job.descricao}\n\n"
            "REVISÃO OBRIGATÓRIA:\n"
            "O roteiro anterior não passou na validação.\n"
            f"Motivo: {motivo}\n"
            f"Limite máximo: {limite} palavras na narração.\n\n"
            "Reescreva o roteiro completo em português brasileiro.\n"
            "Entregue o texto no formato da skill, incluindo "
            "a seção 'Narração pronta:'.\n"
            "Não ultrapasse o limite de palavras.\n"
            "Mantenha a qualidade, a naturalidade e o objetivo.\n\n"
            f"ROTEIRO ANTERIOR:\n{resultado}"
        )

        # Cria um trabalho temporário sem alterar o original.
        job_revisao = replace(
            job,
            descricao=instrucao_revisao,
        )

        revisado = await self.agent_runner.run(job_revisao)

        aprovado, motivo = validar_roteiro(
            job.descricao,
            revisado,
        )

        if aprovado:
            return self._atualizar_contagem(revisado)

        return (
            "⚠️ Roteiro gerado, mas não aprovado "
            "pelo controle de duração.\n"
            f"Motivo: {motivo}\n\n"
            f"{revisado}"
        )

    async def _preparar_narracao(self, job: Job) -> str:
        if self.artifact_store is None:
            raise RuntimeError("ArtifactStore não configurado.")

        if self.agent_runner is None:
            raise RuntimeError("AgentRunner não configurado.")

        segundos = extrair_duracao(job.descricao)

        if segundos is None or segundos <= 0:
            raise ValueError(
                "Informe uma duração positiva para a narração."
            )

        service = NarrationService(
            agent_runner=self.agent_runner,
            artifact_store=self.artifact_store,
        )

        resposta = await self.agent_runner.run(job)

        narracao = await service.preparar(
            job=job,
            resposta=resposta,
            voz=job.dados.get("voz", "pt-BR-AntonioNeural"),
        )

        job.artifacts.append(
            JobArtifact(
                role="output",
                relative_path=narracao.relative_path,
                filename="narracao.mp3",
                media_type="audio/mpeg",
            )
        )

        job.dados["narracao"] = narracao.texto
        job.dados["duracao_real"] = narracao.duracao_real
        job.dados["duracao_alvo"] = narracao.duracao_alvo
        job.dados["tentativas_narracao"] = narracao.tentativas

        return (
            self._atualizar_contagem(narracao.resposta)
            + f"\\n\\nDuração real do áudio: "
            f"{narracao.duracao_real:.2f} segundos."
            f"\\nTentativas: {narracao.tentativas}"
            "\\nLocução aprovada!"
        )

    @staticmethod
    def _atualizar_contagem(resultado: str) -> str:
        """Corrige a contagem declarada usando o texto real."""

        narracao = extrair_narracao(resultado)

        if narracao is None:
            return resultado

        palavras = contar_palavras(narracao)

        padrao = (
            r"(?im)^([ \t]*\*{0,2}Palavras da narração:"
            r"\*{0,2}[ \t]*)\d+[ \t]*$"
        )

        if re.search(padrao, resultado):
            return re.sub(
                padrao,
                lambda match: f"{match.group(1)}{palavras}",
                resultado,
                count=1,
            )

        return resultado
