from __future__ import annotations

import asyncio

import pytest

from agent_runner import AgentRunner
from ai_client import AIClientError
from job import Job, JobStatus
from skill_loader import SkillNotFoundError


def test_agent_runner_carrega_skill_e_chama_ai_client_com_historico_vazio() -> None:
    async def scenario() -> None:
        ai_client = _FakeAIClient("Resposta da IA")
        skill_loader = _FakeSkillLoader({"roteiro": "Instrucoes da skill"})
        runner = AgentRunner(ai_client, skill_loader)
        job = _make_job("Descricao do trabalho", skill="roteiro")

        result = await runner.run(job)

        assert skill_loader.calls == ["roteiro"]
        assert ai_client.calls == [
            ([], "INSTRUCOES DA SKILL:\nInstrucoes da skill\n\nTAREFA:\nDescricao do trabalho")
        ]
        assert result == "Resposta da IA"

    asyncio.run(scenario())


def test_agent_runner_propaga_ai_client_error() -> None:
    async def scenario() -> None:
        error = AIClientError("Servico indisponivel.")
        runner = AgentRunner(_FailingAIClient(error), _FakeSkillLoader({"roteiro": "Skill"}))

        with pytest.raises(AIClientError, match="Servico indisponivel"):
            await runner.run(_make_job("Descricao", skill="roteiro"))

    asyncio.run(scenario())


def test_agent_runner_nao_altera_status_nem_resultado_do_job() -> None:
    async def scenario() -> None:
        runner = AgentRunner(_FakeAIClient("Resposta"), _FakeSkillLoader({"roteiro": "Skill"}))
        job = _make_job("Descricao", skill="roteiro")
        original_status = job.status
        original_resultado = job.resultado

        await runner.run(job)

        assert job.status is original_status is JobStatus.AGUARDANDO
        assert job.resultado == original_resultado == ""

    asyncio.run(scenario())


def test_skill_nao_encontrada_e_propagada() -> None:
    async def scenario() -> None:
        error = SkillNotFoundError("Skill nao encontrada: ausente.")
        runner = AgentRunner(_FakeAIClient("Resposta"), _FailingSkillLoader(error))

        with pytest.raises(SkillNotFoundError, match="Skill nao encontrada: ausente"):
            await runner.run(_make_job("Descricao", skill="ausente"))

    asyncio.run(scenario())


def test_diferentes_skills_podem_ser_utilizadas_por_jobs_distintos() -> None:
    async def scenario() -> None:
        ai_client = _FakeAIClient("Resposta")
        skill_loader = _FakeSkillLoader({"video": "Skill de video", "texto": "Skill de texto"})
        runner = AgentRunner(ai_client, skill_loader)
        first_job = _make_job("Primeira descricao", skill="video")
        second_job = _make_job("Segunda descricao", skill="texto")

        await runner.run(first_job)
        await runner.run(second_job)

        assert ai_client.calls == [
            ([], "INSTRUCOES DA SKILL:\nSkill de video\n\nTAREFA:\nPrimeira descricao"),
            ([], "INSTRUCOES DA SKILL:\nSkill de texto\n\nTAREFA:\nSegunda descricao"),
        ]

    asyncio.run(scenario())


class _FakeAIClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[tuple[list[dict[str, str]], str]] = []

    async def get_response(self, history: list[dict[str, str]], message: str) -> str:
        self.calls.append((history, message))
        return self.response


class _FailingAIClient:
    def __init__(self, error: AIClientError) -> None:
        self.error = error

    async def get_response(self, history: list[dict[str, str]], message: str) -> str:
        raise self.error


class _FakeSkillLoader:
    def __init__(self, skills: dict[str, str]) -> None:
        self.skills = skills
        self.calls: list[str] = []

    def load(self, skill_name: str) -> str:
        self.calls.append(skill_name)
        return self.skills[skill_name]


class _FailingSkillLoader:
    def __init__(self, error: SkillNotFoundError) -> None:
        self.error = error

    def load(self, skill_name: str) -> str:
        raise self.error


def _make_job(descricao: str, skill: str) -> Job:
    return Job(42, "mkitextos", "texto", skill, "Titulo", descricao)
