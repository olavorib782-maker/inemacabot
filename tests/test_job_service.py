from __future__ import annotations

import asyncio
from pathlib import Path

from job import JobStatus
from job_service import JobService
from job_registry import JobRegistry
from queue_manager import QueueManager
from router import Router
from workers.base_worker import BaseWorker
from sqlite_job_store import SQLiteJobStore


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


def test_job_e_persistido_antes_de_ser_enfileirado(tmp_path: Path) -> None:
    async def scenario() -> None:
        store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
        store.initialize()
        registry = JobRegistry(store)

        class InspectingQueueManager(QueueManager):
            async def put(self, job) -> None:  # type: ignore[no-untyped-def]
                assert registry.get(job.id) is job
                persisted = store.load_all()
                assert len(persisted) == 1
                assert persisted[0].status is JobStatus.AGUARDANDO
                await super().put(job)

        manager = InspectingQueueManager()
        service = JobService(Router(), manager, registry)
        job = await service.submit(42, "Preciso de um roteiro")

        assert job is not None
        assert registry.get(job.id) is job

    asyncio.run(scenario())


def test_registry_observa_as_mutacoes_feitas_pelo_worker() -> None:
    class ControlledWorker(BaseWorker):
        def __init__(self, manager: QueueManager) -> None:
            super().__init__(manager, "mkitextos")
            self.processing = asyncio.Event()
            self.release = asyncio.Event()

        async def process_job(self, job) -> str:  # type: ignore[no-untyped-def]
            self.processing.set()
            await self.release.wait()
            return "resultado"

    async def scenario() -> None:
        registry = JobRegistry()
        manager = QueueManager()
        service = JobService(Router(), manager, registry)
        worker = ControlledWorker(manager)

        job = await service.submit(42, "Preciso de um roteiro")
        assert job is not None
        registered_job = registry.get(job.id)
        assert registered_job is job
        assert registered_job.status is JobStatus.AGUARDANDO

        task = asyncio.create_task(worker.run())
        await asyncio.wait_for(worker.processing.wait(), timeout=1)
        assert registered_job.status is JobStatus.PROCESSANDO

        worker.release.set()
        async def wait_until_completed() -> None:
            while registered_job.status is not JobStatus.CONCLUIDO:
                await asyncio.sleep(0)
        await asyncio.wait_for(wait_until_completed(), timeout=1)
        assert registered_job.status is JobStatus.CONCLUIDO

        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

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
    return JobService(Router(), manager, JobRegistry()), manager
