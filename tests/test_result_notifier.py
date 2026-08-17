import pytest

from job import Job, JobStatus
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