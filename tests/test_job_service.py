from __future__ import annotations

import asyncio

from job import JobStatus
from job_service import JobService
from queue_manager import QueueManager
from router import Router


def test_mensagem_reconhecida_cria_job_com_dados_corretos() -> None:
    async def scenario() -> None:
        service, _ = _make_service()

        job = await service.submit(42, "Quero criar um vídeo explicativo sobre agentes de IA.")

        assert job is not None
        assert job.fila == "mkivideos"
        assert job.tipo == "video"
        assert job.skill == "video_explicativo"
        assert job.status is JobStatus.AGUARDANDO

    asyncio.run(scenario())


def test_job_criado_e_colocado_na_queue_manager() -> None:
    async def scenario() -> None:
        service, manager = _make_service()

        submitted_job = await service.submit(42, "Preciso de um roteiro para um vídeo")

        assert submitted_job is not None
        assert manager.size("mkitextos") == 1
        assert await manager.get("mkitextos") is submitted_job

    asyncio.run(scenario())


def test_mensagem_normal_nao_cria_job_nem_altera_filas() -> None:
    async def scenario() -> None:
        service, manager = _make_service()

        job = await service.submit(42, "Bom dia, Inemaca!")

        assert job is None
        assert manager.size("mkivideos") == 0
        assert manager.size("mkitextos") == 0
        assert manager.size("mkiservicos") == 0

    asyncio.run(scenario())


def test_chat_id_e_descricao_originais_sao_preservados() -> None:
    async def scenario() -> None:
        service, _ = _make_service()
        message = "Pesquise ferramentas gratuitas para edição de vídeo"

        job = await service.submit(987, message)

        assert job is not None
        assert job.chat_id == 987
        assert job.descricao == message

    asyncio.run(scenario())


def test_tipos_de_trabalho_chegam_as_filas_corretas() -> None:
    async def scenario() -> None:
        service, manager = _make_service()

        video_job = await service.submit(42, "Quero um vídeo explicativo")
        text_job = await service.submit(42, "Preciso de um roteiro")
        service_job = await service.submit(42, "Pesquise ferramentas para edição")

        assert video_job is not None
        assert text_job is not None
        assert service_job is not None
        assert await manager.get("mkivideos") is video_job
        assert await manager.get("mkitextos") is text_job
        assert await manager.get("mkiservicos") is service_job

    asyncio.run(scenario())


def _make_service() -> tuple[JobService, QueueManager]:
    manager = QueueManager()
    return JobService(Router(), manager), manager
