from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from artifact_store import ArtifactStore
from job import JobStatus
from job_service import (
    GuideTonesRequestError,
    JobService,
    extract_guide_tones_chords,
)
from job_registry import JobRegistry
from leadsheet_builder import LeadsheetBuilder, LeadsheetValidationError
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


def test_documento_musical_e_persistido_antes_de_mkimusica(tmp_path: Path) -> None:
    async def scenario() -> None:
        store = SQLiteJobStore(tmp_path / "jobs.sqlite3")
        store.initialize()
        registry = JobRegistry(store)

        class InspectingQueueManager(QueueManager):
            async def put(self, job) -> None:  # type: ignore[no-untyped-def]
                restored = store.load_all()
                assert restored[0].artifacts[0].relative_path == "job-1/input.ls"
                await super().put(job)

        manager = InspectingQueueManager()
        service = JobService(Router(), manager, registry)
        job = await service.submit_music_document(
            42, "job-1", "original.ls", "job-1/input.ls"
        )

        assert job.fila == "mkimusica"
        assert await manager.get("mkimusica") is job

    asyncio.run(scenario())


def test_submit_guide_tones_cria_artifact_persiste_e_enfileira(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        artifact_store = ArtifactStore(tmp_path / "artifacts")
        registry = JobRegistry()
        builder = LeadsheetBuilder()

        class InspectingQueueManager(QueueManager):
            async def put(self, job) -> None:  # type: ignore[no-untyped-def]
                assert registry.get(job.id) is job
                assert job.artifacts[0].relative_path == f"{job.id}/input.ls"
                input_path = artifact_store.resolve(job.artifacts[0].relative_path)
                assert input_path.is_file()
                assert input_path.read_text(encoding="utf-8") == builder.render_guidetones(
                    ["Dm7", "G7", "Cmaj7", "Cmaj7"]
                )
                await super().put(job)

        manager = InspectingQueueManager()
        service = JobService(
            Router(), manager, registry, builder, artifact_store
        )

        job = await service.submit_guide_tones(
            42, ["Dm7", "G7", "Cmaj7", "Cmaj7"]
        )

        assert job.fila == "mkimusica"
        assert job.tipo == "musica"
        assert job.skill == "guide_tones"
        assert job.titulo == "Gerar guide tones"
        assert job.descricao == (
            "Geração de guide tones a partir de uma progressão harmônica."
        )
        assert registry.get(job.id) is job
        assert await manager.get("mkimusica") is job
        assert len(job.artifacts) == 1
        artifact = job.artifacts[0]
        assert artifact.role == "input"
        assert artifact.filename == "guide_tones.ls"
        assert artifact.media_type == "application/x-improvisor-leadsheet"
        input_path = artifact_store.resolve(artifact.relative_path)
        assert input_path.is_relative_to(artifact_store.root)

    asyncio.run(scenario())


def test_submit_guide_tones_persiste_sqlite_antes_do_enqueue(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        database = SQLiteJobStore(tmp_path / "jobs.sqlite3")
        database.initialize()
        registry = JobRegistry(database)
        artifact_store = ArtifactStore(tmp_path / "artifacts")

        class InspectingQueueManager(QueueManager):
            async def put(self, job) -> None:  # type: ignore[no-untyped-def]
                restored = database.load_all()
                assert len(restored) == 1
                assert restored[0].skill == "guide_tones"
                assert restored[0].artifacts[0].relative_path == f"{job.id}/input.ls"
                await super().put(job)

        manager = InspectingQueueManager()
        service = JobService(
            Router(), manager, registry, LeadsheetBuilder(), artifact_store
        )

        job = await service.submit_guide_tones(42, ["D/F#", "G7/B"])

        assert await manager.get("mkimusica") is job

    asyncio.run(scenario())


def test_progressao_invalida_nao_cria_nem_enfileira_job(tmp_path: Path) -> None:
    async def scenario() -> None:
        manager = QueueManager()
        registry = JobRegistry()
        service = JobService(
            Router(),
            manager,
            registry,
            LeadsheetBuilder(),
            ArtifactStore(tmp_path),
        )

        with pytest.raises(LeadsheetValidationError):
            await service.submit_guide_tones(42, [])

        assert registry.list_all() == []
        assert manager.size("mkimusica") == 0
        assert list(tmp_path.rglob("input.ls")) == []

    asyncio.run(scenario())


def test_falha_de_escrita_nao_persiste_nem_enfileira(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario() -> None:
        manager = QueueManager()
        registry = JobRegistry()
        service = JobService(
            Router(),
            manager,
            registry,
            LeadsheetBuilder(),
            ArtifactStore(tmp_path),
        )

        def fail_write(*args, **kwargs) -> None:  # type: ignore[no-untyped-def]
            raise OSError("falha simulada")

        monkeypatch.setattr(Path, "write_text", fail_write)

        with pytest.raises(OSError, match="falha simulada"):
            await service.submit_guide_tones(42, ["Cmaj7"])

        assert registry.list_all() == []
        assert manager.size("mkimusica") == 0
        assert list(tmp_path.rglob("input.ls")) == []

    asyncio.run(scenario())


def test_falha_de_persistencia_remove_artifact_e_nao_enfileira(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        class FailingRegistry(JobRegistry):
            def add(self, job) -> None:  # type: ignore[no-untyped-def]
                raise RuntimeError("persistência indisponível")

        manager = QueueManager()
        service = JobService(
            Router(),
            manager,
            FailingRegistry(),
            LeadsheetBuilder(),
            ArtifactStore(tmp_path),
        )

        with pytest.raises(RuntimeError, match="persistência indisponível"):
            await service.submit_guide_tones(42, ["Cmaj7"])

        assert manager.size("mkimusica") == 0
        assert list(tmp_path.rglob("input.ls")) == []

    asyncio.run(scenario())


def test_falha_de_enqueue_marca_job_persistido_como_erro(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        class FailingQueueManager(QueueManager):
            def __init__(self) -> None:
                super().__init__()
                self.received_job = None

            async def put(self, job) -> None:  # type: ignore[no-untyped-def]
                self.received_job = job
                raise RuntimeError("fila indisponível")

        manager = FailingQueueManager()
        registry = JobRegistry()
        artifact_store = ArtifactStore(tmp_path)
        service = JobService(
            Router(), manager, registry, LeadsheetBuilder(), artifact_store
        )

        with pytest.raises(RuntimeError, match="fila indisponível"):
            await service.submit_guide_tones(42, ["Cmaj7"])

        job = manager.received_job
        assert job is not None
        assert registry.get(job.id) is job
        assert job.status is JobStatus.ERRO
        assert artifact_store.resolve(job.artifacts[0].relative_path).is_file()
        assert manager.size("mkimusica") == 0

    asyncio.run(scenario())


def test_extrator_retorna_quatro_acordes() -> None:
    assert extract_guide_tones_chords(
        "Crie guide tones para Dm7 | G7 | Cmaj7 | Cmaj7"
    ) == ["Dm7", "G7", "Cmaj7", "Cmaj7"]


def test_extrator_preserva_slash_chords() -> None:
    assert extract_guide_tones_chords(
        "Gere guide tones para D/F# | G7/B"
    ) == ["D/F#", "G7/B"]


def test_extrator_aceita_barra_final_opcional() -> None:
    without_final_bar = extract_guide_tones_chords("guide tones para Dm7 | G7")
    with_final_bar = extract_guide_tones_chords("guide tones para Dm7 | G7 |")

    assert without_final_bar == with_final_bar == ["Dm7", "G7"]


@pytest.mark.parametrize(
    "message",
    [
        "guide tones para Dm7 || G7",
        "guide tones para | Dm7 | G7",
        "guide tones para",
        "guide tones para   ",
    ],
)
def test_extrator_rejeita_progressao_ausente_ou_compasso_vazio(
    message: str,
) -> None:
    with pytest.raises(GuideTonesRequestError):
        extract_guide_tones_chords(message)


def test_extrator_rejeita_limites_de_tamanho() -> None:
    with pytest.raises(GuideTonesRequestError, match="solicitação"):
        extract_guide_tones_chords("x" * 2001)
    with pytest.raises(GuideTonesRequestError, match="progressão"):
        extract_guide_tones_chords("guide tones para " + "C" * 1025)


def test_submit_textual_guide_tones_cria_input_e_enfileira(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        manager = QueueManager()
        registry = JobRegistry()
        artifact_store = ArtifactStore(tmp_path / "artifacts")
        builder = LeadsheetBuilder()
        service = JobService(
            Router(), manager, registry, builder, artifact_store
        )

        job = await service.submit(
            42, "Crie guide tones para Dm7 | G7 | Cmaj7 | Cmaj7"
        )

        assert job is not None
        assert job.skill == "guide_tones"
        assert registry.get(job.id) is job
        assert await manager.get("mkimusica") is job
        artifact = job.artifacts[0]
        assert artifact.filename == "guide_tones.ls"
        assert artifact_store.resolve(artifact.relative_path).read_text(
            encoding="utf-8"
        ) == builder.render_guidetones(["Dm7", "G7", "Cmaj7", "Cmaj7"])

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
