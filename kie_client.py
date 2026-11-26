"""Cliente compartilhado para tarefas da KIE AI."""

from __future__ import annotations

import asyncio
import json
import os
import logging
from pathlib import Path

import httpx
from dotenv import dotenv_values

logger = logging.getLogger(__name__)

BASE_URL = "https://api.kie.ai/api/v1/jobs"


class KieError(RuntimeError):
    """Falha na comunicacao ou processamento da KIE."""


class KieClient:

    def __init__(
        self,
        api_key: str | None = None,
        env_path: Path | None = None,
    ):
        chave = api_key or os.getenv("KIE_API_KEY", "")

        if not chave.strip():
            caminho = env_path or (
                Path(__file__).resolve().parent / ".env"
            )

            if caminho.is_file():
                chave = dotenv_values(caminho).get(
                    "KIE_API_KEY"
                ) or ""

        self._api_key = chave.strip()

        if not self._api_key:
            raise KieError("KIE_API_KEY nao configurada.")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _dados(resposta: httpx.Response) -> dict:
        try:
            resposta.raise_for_status()
            payload = resposta.json()
        except (httpx.HTTPError, ValueError) as erro:
            raise KieError(
                "Resposta HTTP invalida da KIE."
            ) from erro

        if not isinstance(payload, dict):
            raise KieError("Resposta KIE invalida.")

        if payload.get("code") != 200:
            raise KieError(
                f"KIE retornou codigo {payload.get('code')}."
            )

        dados = payload.get("data")

        if not isinstance(dados, dict):
            raise KieError("Resposta KIE sem dados validos.")

        return dados

    async def criar_tarefa(
        self,
        modelo: str,
        parametros: dict,
    ) -> str:
        """Cria uma tarefa sem repeticao automatica."""

        try:
            async with httpx.AsyncClient(
                timeout=60.0
            ) as client:
                resposta = await client.post(
                    f"{BASE_URL}/createTask",
                    headers=self._headers(),
                    json={
                        "model": modelo,
                        "input": parametros,
                    },
                )
        except httpx.RequestError as erro:
            raise KieError(
                "Falha no envio. Verifique o painel KIE "
                "antes de solicitar nova geracao."
            ) from erro

        dados = self._dados(resposta)
        task_id = dados.get("taskId")

        if not isinstance(task_id, str) or not task_id:
            raise KieError("KIE nao retornou taskId.")

        logger.info(
            "KIE tarefa criada | Modelo=%s | TaskId=%s",
            modelo,
            task_id,
        )

        return task_id


    async def consultar_tarefa(
        self,
        task_id: str,
    ) -> dict:
        """Consulta uma tarefa existente."""

        async with httpx.AsyncClient(
            timeout=30.0
        ) as client:
            resposta = await client.get(
                f"{BASE_URL}/recordInfo",
                headers=self._headers(),
                params={"taskId": task_id},
            )

        return self._dados(resposta)

    @staticmethod
    def extrair_url(dados: dict) -> str:
        """Extrai a URL do resultado da KIE."""

        response = dados.get("response") or {}

        urls = (
            response.get("resultUrls")
            if isinstance(response, dict)
            else None
        )

        if not urls:
            resultado = dados.get("resultJson")

            try:
                if isinstance(resultado, str):
                    resultado = json.loads(resultado)
            except ValueError as erro:
                raise KieError(
                    "resultJson invalido."
                ) from erro

            if isinstance(resultado, dict):
                urls = resultado.get("resultUrls")

        if (
            not isinstance(urls, list)
            or not urls
            or not isinstance(urls[0], str)
            or not urls[0].startswith("https://")
        ):
            raise KieError(
                "KIE concluiu sem URL valida."
            )

        return urls[0]

    async def aguardar_resultado(
        self,
        task_id: str,
        timeout_s: float = 300.0,
        interval_s: float = 5.0,
    ) -> str:
        """Acompanha uma tarefa sem criar outra."""

        if timeout_s <= 0 or interval_s <= 0:
            raise ValueError(
                "Intervalo ou timeout invalido."
            )

        try:
            async with asyncio.timeout(timeout_s):
                while True:
                    try:
                        dados = await self.consultar_tarefa(
                            task_id
                        )
                    except httpx.RequestError:
                        await asyncio.sleep(interval_s)
                        continue

                    estado = dados.get("state")

                    if estado == "success":
                        return self.extrair_url(dados)

                    if estado == "fail":
                        raise KieError(
                            f"KIE falhou | TaskId={task_id}"
                        )

                    if estado not in {
                        "waiting", "queuing", "generating"
                    }:
                        raise KieError(
                            "Estado KIE desconhecido."
                        )

                    await asyncio.sleep(interval_s)

        except TimeoutError as erro:
            raise KieError(
                f"Tempo esgotado | TaskId={task_id}. "
                "Consulte a tarefa antes de repetir."
            ) from erro


    async def baixar_resultado(
        self,
        url: str,
        output_path: Path,
        max_bytes: int = 50 * 1024 * 1024,
    ) -> Path:
        """Baixa o resultado sem expor a chave KIE."""

        if not url.startswith("https://"):
            raise KieError("URL de download invalida.")

        if max_bytes <= 0:
            raise ValueError("Limite de download invalido.")

        output_path = Path(output_path)
        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporario = output_path.with_name(
            output_path.name + ".part"
        )

        total = 0

        try:
            async with asyncio.timeout(120):
                async with httpx.AsyncClient(
                    timeout=30.0,
                    follow_redirects=False,
                ) as client:
                    async with client.stream(
                        "GET", url
                    ) as resposta:

                        resposta.raise_for_status()

                        with temporario.open("wb") as destino:
                            async for bloco in resposta.aiter_bytes():
                                total += len(bloco)

                                if total > max_bytes:
                                    raise KieError(
                                        "Arquivo excede limite permitido."
                                    )

                                destino.write(bloco)

            if total == 0:
                raise KieError("Arquivo baixado vazio.")

            temporario.replace(output_path)

            logger.info(
                "KIE download concluido | Bytes=%s",
                total,
            )

            return output_path

        except (httpx.HTTPError, TimeoutError) as erro:
            raise KieError(
                "Falha no download do resultado KIE."
            ) from erro

        finally:
            temporario.unlink(missing_ok=True)
