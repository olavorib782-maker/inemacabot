from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

import pytest

from ai_client import AIClientError
from artifact_store import ArtifactStore
from job_artifact import JobArtifact

from job import Job, JobStatus
from queue_manager import QueueManager
from workers.base_worker import BaseWorker
from workers.video_worker import VideoWorker


def test_video_worker_herda_base_worker_e_usa_fila_correta() -> None:
    worker = VideoWorker(QueueManager())

    assert isinstance(worker, BaseWorker)
    assert worker.fila == "mkivideos"


def test_video_worker_processa_job_com_sucesso() -> None:
    async def scenario() -> None:
        agent_runner = _FakeAgentRunner("Resultado do agente")
        worker = VideoWorker(QueueManager(), agent_runner=agent_runner)
        job = _make_job("mkivideos")

        result = await worker.process_job(job)

        assert agent_runner.calls == [job]
        assert result == "Resultado do agente"

    asyncio.run(scenario())


def test_video_worker_conclui_job_enfileirado() -> None:
    async def scenario() -> None:
        manager = QueueManager()
        worker = VideoWorker(manager, agent_runner=_FakeAgentRunner("Resultado do agente"))
        job = _make_job("mkivideos")
        task = asyncio.create_task(worker.run())

        await manager.put(job)
        await _wait_until(lambda: job.status is JobStatus.CONCLUIDO)

        assert job.resultado == "Resultado do agente"
        await _cancel(task)

    asyncio.run(scenario())


def test_video_worker_rejeita_fila_incorreta() -> None:
    with pytest.raises(ValueError, match="VideoWorker aceita apenas a fila mkivideos"):
        VideoWorker(QueueManager(), "mkitextos")


def test_erro_do_agent_runner_coloca_job_em_erro_pelo_ciclo_base() -> None:
    async def scenario() -> None:
        manager = QueueManager()
        worker = VideoWorker(manager, agent_runner=_FailingAgentRunner(AIClientError("Falha da IA")))
        job = _make_job("mkivideos")
        task = asyncio.create_task(worker.run())

        await manager.put(job)
        await _wait_until(lambda: job.status is JobStatus.ERRO)

        assert job.resultado == ""
        await _cancel(task)

    asyncio.run(scenario())


def test_video_worker_nao_altera_job_fora_do_ciclo_base() -> None:
    async def scenario() -> None:
        worker = VideoWorker(QueueManager(), agent_runner=_FakeAgentRunner("Resultado do agente"))
        job = _make_job("mkivideos")

        await worker.process_job(job)

        assert job.status is JobStatus.AGUARDANDO
        assert job.resultado == ""

    asyncio.run(scenario())



@pytest.mark.asyncio
async def test_foto_para_video_monta_first_frame(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ArtifactStore(tmp_path)
    worker = VideoWorker(
        QueueManager(),
        artifact_store=store,
    )

    job = Job(
        42,
        "mkivideos",
        "video",
        "foto_para_video",
        "Vídeo",
        "Teste com foto.",
    )

    relative, path = store.job_path(job.id, "foto.jpg")
    path.write_bytes(b"imagem falsa")

    job.artifacts.append(
        JobArtifact(
            "input",
            relative,
            "foto.jpg",
            "image/jpeg",
        )
    )

    chamadas: list[dict] = []

    async def fake_generate_agnes_shot(
        shot: dict,
        agnes_dir: Path,
    ) -> Path:
        chamadas.append(shot)

        raw_dir = agnes_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)

        video_path = raw_dir / f"shot-{shot['n']:02d}.mp4"
        video_path.write_bytes(b"video falso")

        return video_path

    monkeypatch.setattr(
        worker,
        "_generate_agnes_shot",
        fake_generate_agnes_shot,
    )

    async def fake_probe_video_duration(
        video_path: Path,
    ) -> float:
        return 5.175

    monkeypatch.setattr(
        worker,
        "_probe_video_duration",
        fake_probe_video_duration,
    )


    async def fake_add_music_with_fades(
        video_path: Path,
        audio_path: Path,
        output_path: Path,
    ) -> Path:
        output_path.write_bytes(b"video final falso")
        return output_path

    monkeypatch.setattr(
        worker,
        "_add_music_with_fades",
        fake_add_music_with_fades,
    )

    result = await worker.process_job(job)

    assert len(chamadas) == 1
    assert chamadas[0]["first_frame"] == str(path)
    assert chamadas[0]["n"] == 1

    intermediarios = [
        artifact
        for artifact in job.artifacts
        if artifact.role == "intermediate"
    ]

    assert len(intermediarios) == 2
    assert intermediarios[0].filename == "shot-01.mp4"
    assert intermediarios[0].media_type == "video/mp4"
    assert intermediarios[0].relative_path.endswith(
        "/agnes/raw/shot-01.mp4"
    )

    outputs = [
        artifact
        for artifact in job.artifacts
        if artifact.role == "output"
    ]

    assert len(outputs) == 1
    assert outputs[0].filename == "video-final.mp4"
    assert outputs[0].media_type == "video/mp4"
    assert outputs[0].relative_path.endswith(
        "/video-final.mp4"
    )

    assert "1 imagem(ns)" in result
    assert "1 shot(s)" in result
    assert "video-final.mp4" in result




@pytest.mark.asyncio
async def test_foto_para_video_com_duas_imagens(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ArtifactStore(tmp_path)
    worker = VideoWorker(
        QueueManager(),
        artifact_store=store,
    )

    job = Job(
        42,
        "mkivideos",
        "video",
        "foto_para_video",
        "Vídeo",
        "Teste com duas fotos.",
    )

    for nome in ("foto-1.jpg", "foto-2.jpg"):
        relative, path = store.job_path(job.id, nome)
        path.write_bytes(b"imagem falsa")
        job.artifacts.append(
            JobArtifact(
                "input",
                relative,
                nome,
                "image/jpeg",
            )
        )

    chamadas: list[dict] = []

    async def fake_generate_agnes_shot(
        shot: dict,
        agnes_dir: Path,
    ) -> Path:
        chamadas.append(shot)

        raw_dir = agnes_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)

        video_path = raw_dir / f"shot-{shot['n']:02d}.mp4"
        video_path.write_bytes(b"video falso")
        return video_path

    async def fake_probe_video_duration(
        video_path: Path,
    ) -> float:
        return 5.175

    async def fake_assemble_with_xfade(
        videos: list[Path],
        duracoes: list[float],
        output_path: Path,
        transicao_s: float = 0.8,
    ) -> Path:
        assert len(videos) == 2
        assert duracoes == [5.175, 5.175]
        output_path.write_bytes(b"video final falso")
        return output_path

    monkeypatch.setattr(
        worker,
        "_generate_agnes_shot",
        fake_generate_agnes_shot,
    )
    monkeypatch.setattr(
        worker,
        "_probe_video_duration",
        fake_probe_video_duration,
    )
    monkeypatch.setattr(
        worker,
        "_assemble_with_xfade",
        fake_assemble_with_xfade,
    )


    async def fake_add_music_with_fades(
        video_path: Path,
        audio_path: Path,
        output_path: Path,
    ) -> Path:
        output_path.write_bytes(b"video final falso")
        return output_path

    monkeypatch.setattr(
        worker,
        "_add_music_with_fades",
        fake_add_music_with_fades,
    )

    result = await worker.process_job(job)

    assert len(chamadas) == 2
    assert chamadas[0]["n"] == 1
    assert chamadas[1]["n"] == 2
    assert chamadas[0]["first_frame"].endswith("foto-1.jpg")
    assert chamadas[1]["first_frame"].endswith("foto-2.jpg")

    intermediarios = [
        artifact
        for artifact in job.artifacts
        if artifact.role == "intermediate"
    ]
    assert len(intermediarios) == 3

    outputs = [
        artifact
        for artifact in job.artifacts
        if artifact.role == "output"
    ]
    assert len(outputs) == 1
    assert outputs[0].filename == "video-final.mp4"

    assert "2 imagem(ns)" in result
    assert "2 shot(s)" in result
    assert "video-final.mp4" in result


def test_calculate_xfade_offsets() -> None:
    offsets = VideoWorker._calculate_xfade_offsets(
        [5.175, 5.083, 5.201],
        0.8,
    )

    assert offsets == pytest.approx(
        [4.375, 8.658]
    )

def _make_job(fila: str) -> Job:
    return Job(42, fila, "video", "teste", "Vídeo", "Descrição de teste.")


class _FakeAgentRunner:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[Job] = []

    async def run(self, job: Job) -> str:
        self.calls.append(job)
        return self.response


class _FailingAgentRunner:
    def __init__(self, error: AIClientError) -> None:
        self.error = error

    async def run(self, job: Job) -> str:
        raise self.error


async def _wait_until(predicate: Callable[[], bool]) -> None:
    async def wait() -> None:
        while not predicate():
            await asyncio.sleep(0)

    await asyncio.wait_for(wait(), timeout=1)


async def _cancel(task: asyncio.Task[None]) -> None:
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_foto_para_video_com_fala_lipsync_e_musica(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ArtifactStore(tmp_path)

    worker = VideoWorker(
        QueueManager(),
        artifact_store=store,
    )

    job = Job(
        42,
        "mkivideos",
        "video",
        "foto_para_video",
        "Vídeo com fala",
        "Teste completo com fala.",
    )

    job.dados["fala"] = "Olá! Este é um teste."
    job.dados["voz"] = "pt-BR-AntonioNeural"

    relative, foto_path = store.job_path(
        job.id,
        "foto.jpg",
    )
    foto_path.write_bytes(b"imagem falsa")

    job.artifacts.append(
        JobArtifact(
            "input",
            relative,
            "foto.jpg",
            "image/jpeg",
        )
    )

    chamadas = {
        "tts": 0,
        "infinitalk": 0,
        "mix": 0,
        "musica_antiga": 0,
    }

    async def fake_generate_agnes_shot(
        shot: dict,
        agnes_dir: Path,
    ) -> Path:
        raw_dir = agnes_dir / "raw"
        raw_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        video_path = raw_dir / "shot-01.mp4"
        video_path.write_bytes(b"video agnes")
        return video_path

    async def fake_probe_video_duration(
        video_path: Path,
    ) -> float:
        return 5.0

    async def fake_generate_tts_voice(
        text: str,
        output_path: Path,
        voice: str = "pt-BR-AntonioNeural",
    ) -> Path:
        chamadas["tts"] += 1

        assert text == "Olá! Este é um teste."
        assert voice == "pt-BR-AntonioNeural"

        output_path.write_bytes(b"voz falsa")
        return output_path

    async def fake_generate_kie_infinitalk(
        image_path: Path,
        audio_path: Path,
        output_path: Path,
        prompt: str | None = None,
        resolution: str = "480p",
    ) -> Path:
        chamadas["infinitalk"] += 1

        assert image_path.name == "foto.jpg"
        assert audio_path.name == "voz.mp3"
        assert resolution == "480p"

        output_path.write_bytes(b"infinitalk falso")
        return output_path

    async def fake_mix_voice_and_music(
        video_path: Path,
        music_path: Path,
        output_path: Path,
    ) -> Path:
        chamadas["mix"] += 1

        assert video_path.name == "video-infinitalk.mp4"

        output_path.write_bytes(b"video final")
        return output_path

    async def fake_add_music_with_fades(
        video_path: Path,
        audio_path: Path,
        output_path: Path,
    ) -> Path:
        chamadas["musica_antiga"] += 1
        return output_path

    monkeypatch.setattr(
        worker,
        "_generate_agnes_shot",
        fake_generate_agnes_shot,
    )
    monkeypatch.setattr(
        worker,
        "_probe_video_duration",
        fake_probe_video_duration,
    )
    monkeypatch.setattr(
        worker,
        "_generate_tts_voice",
        fake_generate_tts_voice,
    )
    monkeypatch.setattr(
        worker,
        "_generate_kie_infinitalk",
        fake_generate_kie_infinitalk,
    )
    monkeypatch.setattr(
        worker,
        "_mix_voice_and_music",
        fake_mix_voice_and_music,
    )
    monkeypatch.setattr(
        worker,
        "_add_music_with_fades",
        fake_add_music_with_fades,
    )

    result = await worker.process_job(job)

    assert chamadas["tts"] == 1
    assert chamadas["infinitalk"] == 1
    assert chamadas["mix"] == 1

    # Com fala, o fluxo antigo de música não deve ser usado.
    assert chamadas["musica_antiga"] == 0

    intermediarios = [
        artifact
        for artifact in job.artifacts
        if artifact.role == "intermediate"
    ]

    nomes = [
        artifact.filename
        for artifact in intermediarios
    ]

    assert "shot-01.mp4" not in nomes
    assert "video-base.mp4" not in nomes
    assert "voz.mp3" in nomes
    assert "video-infinitalk.mp4" in nomes

    outputs = [
        artifact
        for artifact in job.artifacts
        if artifact.role == "output"
    ]

    assert len(outputs) == 1
    assert outputs[0].filename == "video-final.mp4"

    assert "com fala, InfiniteTalk e música" in result

