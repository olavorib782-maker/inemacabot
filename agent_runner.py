"""Execucao de um trabalho por meio do cliente de IA existente."""

from __future__ import annotations

from ai_client import AIClient
from job import Job
from skill_loader import SkillLoader


class AgentRunner:
    """Encaminha a descricao de um trabalho ao cliente de IA."""

    def __init__(self, ai_client: AIClient, skill_loader: SkillLoader) -> None:
        self.ai_client = ai_client
        self.skill_loader = skill_loader

    async def run(self, job: Job) -> str:
        """Retorna a resposta da IA para a skill e descricao do trabalho."""
        skill_instructions = self.skill_loader.load(job.skill)
        message = f"INSTRUCOES DA SKILL:\n{skill_instructions}\n\nTAREFA:\n{job.descricao}"
        return await self.ai_client.get_response([], message)
