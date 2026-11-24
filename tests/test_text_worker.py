from __future__ import annotations

import asyncio
from collections.abc import Callable

import pytest

from job import Job, JobStatus
from queue_manager import QueueManager
from workers.base_worker import BaseWorker
from workers.text_worker import TextWorker


def test_text_worker_herda_base_worker_e_usa_fila_correta() -> None:
    worker = TextWorker(QueueManager())

    assert isinstance(worker, BaseWorker)
    assert worker.fila == "mkitextos"


def test_text_worker_processa_job_com_sucesso() -> None:
    async def scenario() -> None:
        worker = TextWorker(QueueManager())
        job = _make_job("mkitextos")

        result = await worker.process_job(job)

        assert result == f"Job {job.id} processado pelo TextWorker."

    asyncio.run(scenario())


def test_text_worker_conclui_job_enfileirado() -> None:
    async def scenario() -> None:
        manager = QueueManager()
        worker = TextWorker(manager)
        job = _make_job("mkitextos")
        task = asyncio.create_task(worker.run())

        await manager.put(job)
        await _wait_until(lambda: job.status is JobStatus.CONCLUIDO)

        assert job.resultado == f"Job {job.id} processado pelo TextWorker."
        await _cancel(task)

    asyncio.run(scenario())


def test_text_worker_rejeita_fila_incorreta() -> None:
    with pytest.raises(ValueError, match="TextWorker aceita apenas a fila mkitextos"):
        TextWorker(QueueManager(), "mkivideos")


def _make_job(fila: str) -> Job:
    return Job(42, fila, "texto", "teste", "Texto", "Descrição de teste.")


async def _wait_until(predicate: Callable[[], bool]) -> None:
    async def wait() -> None:
        while not predicate():
            await asyncio.sleep(0)

    await asyncio.wait_for(wait(), timeout=1)


async def _cancel(task: asyncio.Task[None]) -> None:
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

def test_text_worker_revisa_roteiro_longo_uma_vez() -> None:
    class FakeAgentRunner:
        def __init__(self) -> None:
            self.descricoes: list[str] = []

        async def run(self, job: Job) -> str:
            self.descricoes.append(job.descricao)

            if len(self.descricoes) == 1:
                narracao = " ".join(["música"] * 45)
            else:
                narracao = "Boa noite! Recebam nosso saxofonista."

            return (
                "Título: Apresentação\n\n"
                "Narração pronta:\n"
                f"{narracao}\n\n"
                "Palavras da narração: 45\n"
            )

    async def scenario() -> None:
        runner = FakeAgentRunner()
        worker = TextWorker(
            QueueManager(),
            agent_runner=runner,
        )
        job = Job(
            42,
            "mkitextos",
            "texto",
            "roteiro",
            "Apresentação",
            "Crie um roteiro de 20 segundos.",
        )

        resultado = await worker.process_job(job)

        assert len(runner.descricoes) == 2
        assert "Recebam nosso saxofonista" in resultado
        assert job.descricao == "Crie um roteiro de 20 segundos."

    asyncio.run(scenario())

def test_roteiro_aprovado_nao_faz_revisao() -> None:
    class FakeRunner:
        def __init__(self) -> None:
            self.calls = 0

        async def run(self, job: Job) -> str:
            self.calls += 1
            return (
                "Título: Apresentação\n\n"
                "Narração pronta:\n"
                "Boa noite! Recebam nosso saxofonista.\n\n"
                "Palavras da narração: 5\n"
            )

    async def scenario() -> None:
        runner = FakeRunner()
        worker = TextWorker(QueueManager(), agent_runner=runner)
        job = Job(
            42, "mkitextos", "texto", "roteiro",
            "Apresentação", "Crie um roteiro de 20 segundos."
        )

        resultado = await worker.process_job(job)

        assert runner.calls == 1
        assert "Recebam nosso saxofonista" in resultado

    asyncio.run(scenario())


def test_roteiro_longo_apos_revisao_recebe_aviso() -> None:
    class FakeRunner:
        def __init__(self) -> None:
            self.calls = 0

        async def run(self, job: Job) -> str:
            self.calls += 1
            narracao = " ".join(["música"] * 45)
            return (
                "Título: Apresentação\n\n"
                "Narração pronta:\n"
                f"{narracao}\n\n"
                "Palavras da narração: 45\n"
            )

    async def scenario() -> None:
        runner = FakeRunner()
        worker = TextWorker(QueueManager(), agent_runner=runner)
        job = Job(
            42, "mkitextos", "texto", "roteiro",
            "Apresentação", "Crie um roteiro de 20 segundos."
        )

        resultado = await worker.process_job(job)

        assert runner.calls == 2
        assert "não aprovado" in resultado
        assert "45 palavras" in resultado

    asyncio.run(scenario())


def test_outra_skill_nao_passa_pelo_validador() -> None:
    class FakeRunner:
        def __init__(self) -> None:
            self.calls = 0

        async def run(self, job: Job) -> str:
            self.calls += 1
            return "Texto gerado normalmente."

    async def scenario() -> None:
        runner = FakeRunner()
        worker = TextWorker(QueueManager(), agent_runner=runner)
        job = Job(
            42, "mkitextos", "texto", "traducao",
            "Tradução", "Traduza este texto."
        )

        resultado = await worker.process_job(job)

        assert runner.calls == 1
        assert resultado == "Texto gerado normalmente."

    asyncio.run(scenario())
def test_atualizar_contagem_corrige_numero_incorreto() -> None:
    resposta = """Título: Apresentação

Narração pronta:
Boa noite! Recebam nosso saxofonista.

Palavras da narração: 45

Duração estimada: 20 segundos
"""

    resultado = TextWorker._atualizar_contagem(resposta)

    assert "Palavras da narração: 5" in resultado
    assert "Palavras da narração: 45" not in resultado
    assert "Duração estimada: 20 segundos" in resultado


def test_roteiro_duracao_zero_nao_faz_revisao() -> None:
    class FakeRunner:
        def __init__(self) -> None:
            self.calls = 0

        async def run(self, job: Job) -> str:
            self.calls += 1
            return "Roteiro gerado."

    async def scenario() -> None:
        runner = FakeRunner()
        worker = TextWorker(QueueManager(), agent_runner=runner)

        job = Job(
            42,
            "mkitextos",
            "texto",
            "roteiro",
            "Apresentação",
            "Crie um roteiro de 0 segundos.",
        )

        resultado = await worker.process_job(job)

        assert runner.calls == 1
        assert "Duração inválida" in resultado

    asyncio.run(scenario())


def test_roteiro_incompleto_apos_revisao_recebe_aviso() -> None:
    class FakeRunner:
        def __init__(self) -> None:
            self.calls = 0

        async def run(self, job: Job) -> str:
            self.calls += 1
            return "Título: Apresentação\\n\\nRoteiro ainda sem narração."

    async def scenario() -> None:
        runner = FakeRunner()
        worker = TextWorker(QueueManager(), agent_runner=runner)

        job = Job(
            42,
            "mkitextos",
            "texto",
            "roteiro",
            "Apresentação",
            "Crie um roteiro de 20 segundos.",
        )

        resultado = await worker.process_job(job)

        assert runner.calls == 2
        assert "não aprovado" in resultado
        assert "Não foi possível identificar a narração" in resultado
        assert job.descricao == "Crie um roteiro de 20 segundos."

    asyncio.run(scenario())
