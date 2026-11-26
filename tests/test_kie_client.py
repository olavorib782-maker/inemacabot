"""Testes do cliente KIE sem chamadas externas."""

import asyncio
import json

import httpx
import pytest

from kie_client import KieClient, KieError


@pytest.fixture
def cliente():
    return KieClient(api_key="chave-ficticia")


def simular_http(monkeypatch, handler):
    original = httpx.AsyncClient
    transport = httpx.MockTransport(handler)

    def factory(*args, **kwargs):
        kwargs["transport"] = transport
        return original(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)


def test_criar_tarefa(cliente, monkeypatch):
    def handler(request):
        assert request.method == "POST"
        assert request.url.path.endswith("/createTask")
        assert request.headers["Authorization"] == "Bearer chave-ficticia"

        payload = json.loads(request.content)
        assert payload["model"] == "modelo-teste"
        assert payload["input"] == {"text": "Ola"}

        return httpx.Response(
            200,
            json={"code": 200, "data": {"taskId": "teste-123"}},
        )

    simular_http(monkeypatch, handler)

    resultado = asyncio.run(
        cliente.criar_tarefa("modelo-teste", {"text": "Ola"})
    )

    assert resultado == "teste-123"


def test_consultar_tarefa(cliente, monkeypatch):
    def handler(request):
        assert request.method == "GET"
        assert request.url.path.endswith("/recordInfo")
        assert request.url.params["taskId"] == "teste-123"

        return httpx.Response(
            200,
            json={"code": 200, "data": {"state": "generating"}},
        )

    simular_http(monkeypatch, handler)

    dados = asyncio.run(cliente.consultar_tarefa("teste-123"))
    assert dados["state"] == "generating"


def test_extrair_url_response(cliente):
    dados = {
        "response": {
            "resultUrls": ["https://example.com/audio.mp3"]
        }
    }

    assert cliente.extrair_url(dados) == "https://example.com/audio.mp3"


def test_extrair_url_result_json(cliente):
    dados = {
        "resultJson": json.dumps({
            "resultUrls": ["https://example.com/audio.mp3"]
        })
    }

    assert cliente.extrair_url(dados) == "https://example.com/audio.mp3"


@pytest.mark.parametrize("dados", [
    {},
    {"resultJson": "json-invalido"},
    {"response": {"resultUrls": []}},
    {"response": {"resultUrls": ["http://example.com/audio.mp3"]}},
])
def test_url_invalida(cliente, dados):
    with pytest.raises(KieError):
        cliente.extrair_url(dados)


def test_aguardar_sucesso(cliente, monkeypatch):
    estados = iter([
        {"state": "waiting"},
        {"state": "generating"},
        {
            "state": "success",
            "response": {
                "resultUrls": ["https://example.com/audio.mp3"]
            },
        },
    ])

    async def consultar(task_id):
        return next(estados)

    monkeypatch.setattr(cliente, "consultar_tarefa", consultar)

    resultado = asyncio.run(
        cliente.aguardar_resultado(
            "teste-123", timeout_s=2, interval_s=0.01
        )
    )

    assert resultado == "https://example.com/audio.mp3"


def test_aguardar_falha(cliente, monkeypatch):
    async def consultar(task_id):
        return {"state": "fail"}

    monkeypatch.setattr(cliente, "consultar_tarefa", consultar)

    with pytest.raises(KieError, match="KIE falhou"):
        asyncio.run(cliente.aguardar_resultado("teste-123"))


def test_aguardar_timeout(cliente, monkeypatch):
    async def consultar(task_id):
        return {"state": "generating"}

    monkeypatch.setattr(cliente, "consultar_tarefa", consultar)

    with pytest.raises(KieError, match="Tempo esgotado"):
        asyncio.run(
            cliente.aguardar_resultado(
                "teste-123", timeout_s=0.05, interval_s=0.01
            )
        )


def test_criacao_sem_retry(cliente, monkeypatch):
    chamadas = []

    def handler(request):
        chamadas.append(request)
        raise httpx.ReadTimeout("Timeout simulado", request=request)

    simular_http(monkeypatch, handler)

    with pytest.raises(KieError):
        asyncio.run(
            cliente.criar_tarefa("modelo-teste", {"text": "Ola"})
        )

    assert len(chamadas) == 1


def test_download(cliente, monkeypatch, tmp_path):
    def handler(request):
        assert "Authorization" not in request.headers
        return httpx.Response(200, content=b"audio-simulado")

    simular_http(monkeypatch, handler)

    destino = tmp_path / "audio.mp3"

    resultado = asyncio.run(
        cliente.baixar_resultado(
            "https://example.com/audio.mp3", destino
        )
    )

    assert resultado == destino
    assert destino.read_bytes() == b"audio-simulado"
    assert not (tmp_path / "audio.mp3.part").exists()


@pytest.mark.parametrize("conteudo,limite", [
    (b"", 100),
    (b"1234567890", 5),
])
def test_download_invalido(
    cliente, monkeypatch, tmp_path, conteudo, limite
):
    def handler(request):
        return httpx.Response(200, content=conteudo)

    simular_http(monkeypatch, handler)

    destino = tmp_path / "audio.mp3"

    with pytest.raises(KieError):
        asyncio.run(
            cliente.baixar_resultado(
                "https://example.com/audio.mp3",
                destino,
                max_bytes=limite,
            )
        )

    assert not destino.exists()
    assert not (tmp_path / "audio.mp3.part").exists()
