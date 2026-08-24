import pytest
from pathlib import Path

from artifact_store import ArtifactStore
from job import Job, JobStatus
from job_artifact import JobArtifact
from result_notifier import ResultNotifier


@pytest.mark.asyncio
async def test_notifica_resultado_para_chat_do_job():
    mensagens = []

    async def sender(chat_id: int, message: str) -> None:
        mensagens.append((chat_id, message))

    job = Job(
        chat_id=123,
        fila="mkivideos",
        tipo="video",
        skill="video_explicativo",
        titulo="Teste",
        descricao="Teste",
        status=JobStatus.CONCLUIDO,
        resultado="Resultado do teste.",
    )

    notifier = ResultNotifier(sender)

    await notifier.notify(job)

    assert len(mensagens) == 1
    assert mensagens[0][0] == 123
    assert "Trabalho concluído!" in mensagens[0][1]
    assert job.id in mensagens[0][1]
    assert "video_explicativo" in mensagens[0][1]
    assert "Resultado do teste." in mensagens[0][1]


@pytest.mark.asyncio
async def test_notifica_falha_sem_expor_detalhes_tecnicos():
    mensagens = []

    async def sender(chat_id: int, message: str) -> None:
        mensagens.append((chat_id, message))

    job = Job(
        chat_id=123,
        fila="mkivideos",
        tipo="video",
        skill="video_explicativo",
        titulo="Teste",
        descricao="Teste",
        status=JobStatus.ERRO,
        resultado="resultado parcial confidencial",
    )
    notifier = ResultNotifier(sender)

    await notifier.notify_failure(job)

    assert len(mensagens) == 1
    chat_id, message = mensagens[0]
    assert chat_id == 123
    assert job.id in message
    assert "video_explicativo" in message
    assert "Traceback" not in message
    assert "RuntimeError" not in message
    assert "falha de laboratório" not in message
    assert "resultado parcial confidencial" not in message


@pytest.mark.asyncio
async def test_notifier_envia_documento_para_output(tmp_path: Path) -> None:
    texts = []
    documents = []

    async def sender(chat_id: int, message: str) -> None:
        texts.append((chat_id, message))

    async def document_sender(
        chat_id: int, path: Path, filename: str, caption: str
    ) -> None:
        documents.append((chat_id, path, filename, caption))

    store = ArtifactStore(tmp_path)
    job = Job(123, "mkimusica", "musica", "leadsheet_para_musicxml", "T", "D")
    relative, path = store.job_path(job.id, "output.xml")
    path.write_text("<score-partwise/>", encoding="utf-8")
    job.artifacts.append(
        JobArtifact("output", relative, "resultado.musicxml", "music/xml")
    )

    await ResultNotifier(sender, document_sender, store).notify(job)

    assert texts == []
    assert documents == [
        (123, path, "resultado.musicxml", "Leadsheet convertido para MusicXML.")
    ]


@pytest.mark.asyncio
async def test_notifier_nao_envia_documento_ausente(tmp_path: Path) -> None:
    texts = []
    documents = []

    async def sender(chat_id: int, message: str) -> None:
        texts.append((chat_id, message))

    async def document_sender(*args: object) -> None:
        documents.append(args)

    job = Job(123, "mkimusica", "musica", "leadsheet_para_musicxml", "T", "D")
    job.artifacts.append(JobArtifact("output", f"{job.id}/missing.xml", "r.musicxml", "music/xml"))

    await ResultNotifier(sender, document_sender, ArtifactStore(tmp_path)).notify(job)

    assert documents == []
    assert len(texts) == 1
    assert "não está disponível" in texts[0][1]
