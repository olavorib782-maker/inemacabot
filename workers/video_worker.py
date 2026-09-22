u"""Worker especializado para a fila de vídeos."""

from __future__ import annotations

import asyncio
import os
import shutil

import edge_tts
import httpx
from pathlib import Path

from agent_runner import AgentRunner
from artifact_store import ArtifactStore
from job import Job
from job_artifact import JobArtifact
from queue_manager import QueueManager
from workers.base_worker import BaseWorker
from job_event_bus import JobEventBus
from job_registry import JobRegistry


class VideoWorker(BaseWorker):
    """Processa exclusivamente trabalhos da fila ``mkivideos``."""

    _FILA = "mkivideos"
    _OUTPUT_MEDIA_TYPE = "video/mp4"
    _MUSICAVIDEO_BIN = Path("/home/olavo/musicavideo/musicavideo.sh")
    _MUSICAVIDEO_OUT = Path("/home/olavo/projetos/output/musicavideo")
    _FAIXA_PADRAO = Path(
        "/home/olavo/projetos/output/musicavideo/teste-sax/faixa-1.mp3"
    )
    _MUSICAVIDEO_PYTHON = Path("/home/olavo/musicavideo/.venv/bin/python")
    _AGNES_BRIDGE = Path("/home/olavo/inemacabot/tools/agnes_bridge.py")

    def __init__(
        self,
        queue_manager: QueueManager,
        fila: str = _FILA,
        agent_runner: AgentRunner | None = None,
        artifact_store: ArtifactStore | None = None,
        event_bus: JobEventBus | None = None,
        job_registry: JobRegistry | None = None,
    ) -> None:
        if fila != self._FILA:
            raise ValueError("VideoWorker aceita apenas a fila mkivideos.")

        super().__init__(
            queue_manager,
            fila,
            event_bus=event_bus,
            job_registry=job_registry,
        )

        self.agent_runner = agent_runner
        self.artifact_store = artifact_store or ArtifactStore("artifacts")

    async def process_job(self, job: Job) -> str:
        """Processa vídeo real ou mantém o fluxo textual antigo."""

        if job.skill == "clipe_foto":
            return await self._process_photo_clip(job)

        if job.skill == "foto_para_video":
            return await self._process_photo_to_video(job)
      
        if self.agent_runner is not None:
            return await self.agent_runner.run(job)

        return f"Job {job.id} processado pelo VideoWorker."

    async def _process_photo_to_video(self, job: Job) -> str:
        """Processa várias fotos, mantendo cada uma como base visual do vídeo."""

        imagens = [
            artifact
            for artifact in job.artifacts
            if artifact.role == "input"
            and artifact.media_type.startswith("image/")
        ]

        if not imagens:
            raise ValueError(
                "Job foto_para_video sem imagens de entrada."
            )

        caminhos_imagens: list[Path] = []


        for artifact in imagens:
            caminho = self.artifact_store.resolve(
                artifact.relative_path
            )

            if not caminho.is_file():
                raise ValueError(
                    f"Imagem de entrada não encontrada: {caminho}"
                )

            caminhos_imagens.append(caminho)
        
        fala = str(
            job.dados.get("fala", "")
        ).strip()

        direcao = str(
            job.dados.get("direcao", "")
        ).strip()

        motor_fala = str(
            job.dados.get(
                "motor_fala",
                "infinite_talk",
            )
        ).strip().lower()

        if fala and motor_fala == "infinite_talk":
            voz = str(
                job.dados.get(
                    "voz",
                    "pt-BR-AntonioNeural",
                )
            ).strip()

            final_relative, final_path = (
                self.artifact_store.job_path(
                    job.id,
                    "video-final.mp4",
                )
            )

            voz_relative, voz_path = (
                self.artifact_store.job_path(
                    job.id,
                    "voz.mp3",
                )
            )

            await self._generate_tts_voice(
                fala,
                voz_path,
                voice=voz,
            )

            job.artifacts.append(
                JobArtifact(
                    role="intermediate",
                    relative_path=voz_relative,
                    filename="voz.mp3",
                    media_type="audio/mpeg",
                )
            )

            infinitalk_relative, infinitalk_path = (
                self.artifact_store.job_path(
                    job.id,
                    "video-infinitalk.mp4",
                )
            )

            await self._generate_kie_infinitalk(
                caminhos_imagens[0],
                voz_path,
                infinitalk_path,
            )

            job.artifacts.append(
                JobArtifact(
                    role="intermediate",
                    relative_path=infinitalk_relative,
                    filename="video-infinitalk.mp4",
                    media_type=self._OUTPUT_MEDIA_TYPE,
                )
            )

            await self._mix_voice_and_music(
                infinitalk_path,
                self._FAIXA_PADRAO,
                final_path,
            )

            job.artifacts.append(
                JobArtifact(
                    role="output",
                    relative_path=final_relative,
                    filename="video-final.mp4",
                    media_type=self._OUTPUT_MEDIA_TYPE,
                )
            )

            return (
                f"Job {job.id} recebeu "
                f"{len(caminhos_imagens)} imagem(ns) e gerou "
                f"video-final.mp4 com fala, InfiniteTalk e música."
            )

        prompt_agnes = (
            "Preserve the person's identity faithfully. "
            "Preserve the original emotional warmth of the source image. "
            "Start with a soft, natural, relaxed and welcoming smile from the very beginning of the shot. "
            "Maintain the same gentle smile continuously throughout the entire shot. "
            "Do not let the expression drift into neutral, serious, sad, tired or fatigued at any time. "
            "Facial expression continuity is a top priority. "
            "Keep the head, shoulders and torso relaxed and nearly still. "
            "Allow only very subtle and natural head motion. "
            "Breathing should be natural and barely noticeable. "
            "Avoid visible heavy breathing, sighing, fatigue, or exaggerated chest movement. "
            "Use soft natural blinking and minimal facial micro-expressions only. "
            "Avoid exaggerated gestures, strong head movement, swaying or facial distortion. "
            "Use a very slow, elegant and almost imperceptible camera move. "
            "No speaking and no lip sync. "
            "The overall feeling should be calm, friendly, natural, welcoming and pleasant."
        )

        if direcao:
            prompt_agnes += (
                " Additional creative direction from the user: "
                + direcao
            )

        shots: list[dict] = []

        for i, caminho in enumerate(caminhos_imagens, start=1):
            shots.append(
                {
                    "n": i,
                    "duracao_s": 8,
                    "first_frame": str(caminho),
                    "prompt": prompt_agnes,
                }
            )

        agnes_dir = self.artifact_store.resolve(
            Path(job.id) / "agnes"
        )
        agnes_dir.mkdir(parents=True, exist_ok=True)

        videos_gerados: list[Path] = []
        duracoes: list[float] = []

        for shot in shots:
            video_path = await self._generate_agnes_shot(
                shot,
                agnes_dir,
            )
            videos_gerados.append(video_path)

            duracao = await self._probe_video_duration(
                video_path
            )
            duracoes.append(duracao)

            relative_video = (
                Path(job.id)
                / "agnes"
                / "raw"
                / video_path.name
            ).as_posix()

            job.artifacts.append(
                JobArtifact(
                    role="intermediate",
                    relative_path=relative_video,
                    filename=video_path.name,
                    media_type=self._OUTPUT_MEDIA_TYPE,
                )
            )

        base_relative, base_path = (
            self.artifact_store.job_path(
                job.id,
                "video-base.mp4",
            )
        )

        await self._assemble_with_xfade(
            videos_gerados,
            duracoes,
            base_path,
        )

        job.artifacts.append(
            JobArtifact(
                role="intermediate",
                relative_path=base_relative,
                filename="video-base.mp4",
                media_type=self._OUTPUT_MEDIA_TYPE,
            )
        )

        final_relative, final_path = (
            self.artifact_store.job_path(
                job.id,
                "video-final.mp4",
            )
        )

        fala = str(
            job.dados.get("fala", "")
        ).strip()

        if fala:
            voz = str(
                job.dados.get(
                    "voz",
                    "pt-BR-AntonioNeural",
                )
            ).strip()

            motor_fala = str(
                job.dados.get(
                    "motor_fala",
                    "infinite_talk",
                )
            ).strip().lower()

            voz_relative, voz_path = (
                self.artifact_store.job_path(
                    job.id,
                    "voz.mp3",
                )
            )

            await self._generate_tts_voice(
                fala,
                voz_path,
                voice=voz,
            )

            job.artifacts.append(
                JobArtifact(
                    role="intermediate",
                    relative_path=voz_relative,
                    filename="voz.mp3",
                    media_type="audio/mpeg",
                )
            )

            lipsync_relative, lipsync_path = (
                self.artifact_store.job_path(
                    job.id,
                    "video-lipsync.mp4",
                )
            )

            if motor_fala == "infinite_talk":
                await self._generate_kie_infinitalk(
                    caminhos_imagens[0],
                    voz_path,
                    lipsync_path,
                )
                resultado_audio = (
                    "com fala, InfiniteTalk e música"
                )
            else:
                await self._generate_kie_lipsync(
                    base_path,
                    voz_path,
                    lipsync_path,
                )
                resultado_audio = (
                    "com fala, lip sync e música"
                )

            job.artifacts.append(
                JobArtifact(
                    role="intermediate",
                    relative_path=lipsync_relative,
                    filename="video-lipsync.mp4",
                    media_type=self._OUTPUT_MEDIA_TYPE,
                )
            )

            await self._mix_voice_and_music(
                lipsync_path,
                self._FAIXA_PADRAO,
                final_path,
            )

        else:
            await self._add_music_with_fades(
                base_path,
                self._FAIXA_PADRAO,
                final_path,
            )

            resultado_audio = "com música"

        job.artifacts.append(
            JobArtifact(
                role="output",
                relative_path=final_relative,
                filename="video-final.mp4",
                media_type=self._OUTPUT_MEDIA_TYPE,
            )
        )

        return (
            f"Job {job.id} recebeu "
            f"{len(shots)} imagem(ns), gerou "
            f"{len(videos_gerados)} shot(s) com Agnes 2.5, "
            f"montou as transições e gerou "
            f"video-final.mp4 {resultado_audio}."
        )

    async def _process_photo_clip(self, job: Job) -> str:
        input_artifact = next(
            (
                artifact
                for artifact in job.artifacts
                if artifact.role == "input"
                and artifact.media_type.startswith("image/")
            ),
            None,
        )

        if input_artifact is None:
            raise ValueError("Job de vídeo sem imagem de entrada.")

        input_path = self.artifact_store.resolve(
            input_artifact.relative_path
        )

        if not input_path.is_file():
            raise ValueError(
                "Imagem de entrada não encontrada no armazenamento."
            )

        if not self._MUSICAVIDEO_BIN.is_file():
            raise ValueError(
                f"Musicavideo não encontrado em {self._MUSICAVIDEO_BIN}"
            )

        if not self._FAIXA_PADRAO.is_file():
            raise ValueError(
                f"Faixa padrão não encontrada em {self._FAIXA_PADRAO}"
            )

        slug = f"tg-{job.id[:8]}"

        prompt = (job.descricao or "").strip()
        if not prompt:
            prompt = (
                "clipe musical com atmosfera emotiva, "
                "foco em amizade, saudade e lembranças"
            )

        env = os.environ.copy()
        env["MUSICAVIDEO_OUT"] = str(self._MUSICAVIDEO_OUT)
        env["PATH"] = (
            "/home/olavo/musicavideo/.venv/bin:"
            + env.get("PATH", "")
        )
        cmd = [
            str(self._MUSICAVIDEO_BIN),
            "tudo",
            prompt,
            slug,
            "--faixa-pronta",
            str(self._FAIXA_PADRAO),
            "--foto",
            str(input_path),
            "--sim",
            "--telegram",
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
        )

        linhas: list[str] = []

        if proc.stdout is None:
              raise RuntimeError("Musicavideo iniciou sem saída disponível.")

        async for raw_line in proc.stdout:
            linha = raw_line.decode("utf-8", errors="ignore").rstrip()

            if not linha:
                continue

            linhas.append(linha)

            print(
                f"[musicavideo:{job.id[:8]}] {linha}",
                flush=True,
            )

        returncode = await proc.wait()

        saida_txt = "\n".join(linhas)

        if returncode != 0:
            raise RuntimeError(
                f"Musicavideo falhou: {saida_txt[-1200:]}"
           )

        clipe_path = (
            self._MUSICAVIDEO_OUT
            / slug
            / "clipe.mp4"
        )

        if not clipe_path.is_file():
            raise RuntimeError(
                "Musicavideo terminou sem gerar clipe.mp4."
            )

        output_relative, output_path = (
            self.artifact_store.job_path(
                job.id,
                "clipe.mp4",
            )
        )

        shutil.copy2(clipe_path, output_path)

        limite_telegram = 45 * 1024 * 1024

        if output_path.stat().st_size > limite_telegram:
            telegram_relative, telegram_path = (
                self.artifact_store.job_path(
                    job.id,
                    "clipe-telegram.mp4",
                )
            )

            print(
                f"[musicavideo:{job.id[:8]}] "
                "clipe acima de 45 MB; criando versão para Telegram...",
                flush=True,
            )

            ffmpeg_cmd = [
                "ffmpeg",
                "-y",
                "-i",
                str(output_path),
                "-c:v",
                "libx264",
                "-crf",
                "29",
                "-preset",
                "medium",
                "-c:a",
                "aac",
                "-b:a",
                "112k",
                "-movflags",
                "+faststart",
                str(telegram_path),
            ]

            ffmpeg_proc = await asyncio.create_subprocess_exec(
                *ffmpeg_cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )

            _, ffmpeg_stderr = await ffmpeg_proc.communicate()

            if ffmpeg_proc.returncode != 0:
                detalhe = ffmpeg_stderr.decode(
                    "utf-8",
                    errors="ignore",
                )
                raise RuntimeError(
                    f"Falha ao comprimir vídeo: {detalhe[-1200:]}"
                )

            if not telegram_path.is_file():
                raise RuntimeError(
                    "FFmpeg terminou sem gerar clipe-telegram.mp4."
                )

            tamanho_mb = telegram_path.stat().st_size / (1024 * 1024)

            print(
                f"[musicavideo:{job.id[:8]}] "
                f"versão Telegram pronta: {tamanho_mb:.1f} MB",
                flush=True,
            )

            if telegram_path.stat().st_size > limite_telegram:
                print(
                    f"[musicavideo:{job.id[:8]}] "
                    "primeira compressão ainda acima de 45 MB; "
                    "tentando versão mais compacta...",
                    flush=True,
                )

                ffmpeg_cmd_2 = [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(output_path),
                    "-c:v",
                    "libx264",
                    "-crf",
                    "31",
                    "-preset",
                    "medium",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "96k",
                    "-movflags",
                    "+faststart",
                    str(telegram_path),
                ]

                ffmpeg_proc_2 = await asyncio.create_subprocess_exec(
                    *ffmpeg_cmd_2,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )

                _, ffmpeg_stderr_2 = await ffmpeg_proc_2.communicate()

                if ffmpeg_proc_2.returncode != 0:
                    detalhe = ffmpeg_stderr_2.decode(
                        "utf-8",
                        errors="ignore",
                    )
                    raise RuntimeError(
                        f"Falha na segunda compressão: {detalhe[-1200:]}"
                    )

                tamanho_mb = telegram_path.stat().st_size / (1024 * 1024)

                print(
                    f"[musicavideo:{job.id[:8]}] "
                    f"segunda versão Telegram pronta: {tamanho_mb:.1f} MB",
                    flush=True,
                )

                if telegram_path.stat().st_size > limite_telegram:
                    raise RuntimeError(
                        "Mesmo após a segunda compressão, "
                )

            job.artifacts.append(
                JobArtifact(
                    role="master",
                    relative_path=output_relative,
                    filename="clipe.mp4",
                    media_type=self._OUTPUT_MEDIA_TYPE,
                )
            )

            job.artifacts.append(
                JobArtifact(
                    role="output",
                    relative_path=telegram_relative,
                    filename="clipe-telegram.mp4",
                    media_type=self._OUTPUT_MEDIA_TYPE,
                )
            )

        else:
            job.artifacts.append(
                JobArtifact(
                    role="output",
                    relative_path=output_relative,
                    filename="clipe.mp4",
                    media_type=self._OUTPUT_MEDIA_TYPE,
                )
            )

        return "✅ Clipe gerado com sucesso a partir da foto enviada."

    async def _generate_agnes_shot(
        self,
        shot: dict,
        agnes_dir: Path,
    ) -> Path:
        """Gera um shot usando a ponte com a Agnes 2.5."""

        if not self._MUSICAVIDEO_PYTHON.is_file():
            raise RuntimeError(
                f"Python do Musicavideo não encontrado: "
                f"{self._MUSICAVIDEO_PYTHON}"
            )

        if not self._AGNES_BRIDGE.is_file():
            raise RuntimeError(
                f"Bridge da Agnes não encontrado: "
                f"{self._AGNES_BRIDGE}"
            )

        proc = await asyncio.create_subprocess_exec(
            str(self._MUSICAVIDEO_PYTHON),
            str(self._AGNES_BRIDGE),
            str(shot["first_frame"]),
            str(agnes_dir),
            str(shot["n"]),
            str(shot["prompt"]),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            detalhe = stderr.decode(
                "utf-8",
                errors="ignore",
            )
            raise RuntimeError(
                f"Agnes falhou no shot {shot['n']}: "
                f"{detalhe[-1200:]}"
            )

        linhas = stdout.decode(
            "utf-8",
            errors="ignore",
        ).strip().splitlines()

        if not linhas:
            raise RuntimeError(
                f"Agnes não informou o arquivo do shot {shot['n']}."
            )

        video_path = Path(linhas[-1])

        if not video_path.is_file():
            raise RuntimeError(
                f"Agnes terminou sem gerar o shot {shot['n']}: "
                f"{video_path}"
            )

        return video_path

    async def _probe_video_duration(self, video_path: Path) -> float:
        """Obtém a duração real de um vídeo usando ffprobe."""

        proc = await asyncio.create_subprocess_exec(
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            detalhe = stderr.decode(
                "utf-8",
                errors="ignore",
            )
            raise RuntimeError(
                f"Falha ao medir duração de {video_path.name}: "
                f"{detalhe[-800:]}"
            )

        try:
            return float(stdout.decode("utf-8").strip())
        except ValueError as exc:
            raise RuntimeError(
                f"ffprobe retornou duração inválida para "
                f"{video_path.name}."
            ) from exc

    @staticmethod
    def _calculate_xfade_offsets(
        duracoes: list[float],
        transicao_s: float = 0.8,
    ) -> list[float]:
        """Calcula os pontos de início das transições xfade."""

        if len(duracoes) < 2:
            return []

        offsets: list[float] = []
        acumulado = duracoes[0]

        for duracao in duracoes[1:]:
            offset = acumulado - transicao_s
            offsets.append(offset)
            acumulado = offset + duracao

        return offsets

    async def _assemble_with_xfade(
        self,
        videos: list[Path],
        duracoes: list[float],
        output_path: Path,
        transicao_s: float = 0.8,
    ) -> Path:
        """Monta vários shots com transições xfade."""

        if not videos:
            raise ValueError("Nenhum vídeo recebido para montagem.")

        if len(videos) != len(duracoes):
            raise ValueError(
                "Quantidade de vídeos e durações não corresponde."
            )

        if len(videos) == 1:
            shutil.copy2(videos[0], output_path)
            return output_path

        offsets = self._calculate_xfade_offsets(
            duracoes,
            transicao_s,
        )

        cmd: list[str] = ["ffmpeg", "-y"]

        for video in videos:
            cmd.extend(["-i", str(video)])

        filtros: list[str] = []

        for i in range(len(videos)):
            filtros.append(
                f"[{i}:v]"
                "scale=720:1280:"
                "force_original_aspect_ratio=decrease,"
                "pad=720:1280:(ow-iw)/2:(oh-ih)/2,"
                "setsar=1,"
                "format=yuv420p"
                f"[v{i}]"
            )

        entrada_anterior = "v0"

        for i in range(1, len(videos)):
            saida = f"x{i}"
            filtros.append(
                f"[{entrada_anterior}][v{i}]"
                f"xfade=transition=fade:"
                f"duration={transicao_s}:"
                f"offset={offsets[i - 1]}"
                f"[{saida}]"
            )
            entrada_anterior = saida

        filtro_complexo = ";".join(filtros)

        cmd.extend(
            [
                "-filter_complex",
                filtro_complexo,
                "-map",
                f"[{entrada_anterior}]",
                "-c:v",
                "libx264",
                "-crf",
                "18",
                "-preset",
                "medium",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                "-an",
                str(output_path),
            ]
        )

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )

        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            detalhe = stderr.decode(
                "utf-8",
                errors="ignore",
            )
            raise RuntimeError(
                f"Falha na montagem xfade: {detalhe[-1600:]}"
            )

        if not output_path.is_file():
            raise RuntimeError(
                "FFmpeg terminou sem gerar o vídeo montado."
            )

        return output_path

    async def _add_music_with_fades(
        self,
        video_path: Path,
        audio_path: Path,
        output_path: Path,
    ) -> Path:
        """Adiciona música ao vídeo com fade-in e fade-out."""

        if not video_path.is_file():
            raise ValueError(
                f"Vídeo não encontrado: {video_path}"
            )

        if not audio_path.is_file():
            raise ValueError(
                f"Áudio não encontrado: {audio_path}"
            )

        duracao_video = await self._probe_video_duration(
            video_path
        )

        fade_out_duracao = 1.5
        fade_out_inicio = max(
            0.0,
            duracao_video - fade_out_duracao,
        )

        filtro_audio = (
            "afade=t=in:st=0:d=1,"
            f"afade=t=out:st={fade_out_inicio}:"
            f"d={fade_out_duracao}"
        )

        proc = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-filter_complex",
            f"[1:a]{filtro_audio}[a]",
            "-map",
            "0:v",
            "-map",
            "[a]",
            "-shortest",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(output_path),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )

        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            detalhe = stderr.decode(
                "utf-8",
                errors="ignore",
            )
            raise RuntimeError(
                f"Falha ao adicionar música: "
                f"{detalhe[-1600:]}"
            )

        if not output_path.is_file():
            raise RuntimeError(
                "FFmpeg terminou sem gerar video-final.mp4."
            )

        return output_path

    async def _mix_voice_and_music(
        self,
        video_path: Path,
        music_path: Path,
        output_path: Path,
    ) -> Path:
        """Mistura a voz do vídeo com música usando a referência v2."""

        if not video_path.is_file():
            raise ValueError(
                f"Vídeo com voz não encontrado: {video_path}"
            )

        if not music_path.is_file():
            raise ValueError(
                f"Música não encontrada: {music_path}"
            )

        duracao = await self._probe_video_duration(video_path)

        if duracao <= 0:
            raise ValueError("Duração inválida do vídeo.")

        # Mantém proporcionalmente o comportamento aprovado
        # no vídeo-referência de 5 segundos.
        fade_in_duracao = min(0.4, duracao * 0.08)
        ponto_baixo = duracao * 0.64
        ponto_subida = duracao * 0.80
        fade_out_duracao = min(1.0, duracao * 0.20)
        fade_out_inicio = max(
            0.0,
            duracao - fade_out_duracao,
        )

        volume_expr = (
            f"if(lt(t,{fade_in_duracao}),0.10,"
            f"if(lt(t,{ponto_baixo}),0.16,"
            f"if(lt(t,{ponto_subida}),0.28,0.22)))"
        )

        filtro = (
            "[0:a]volume=1.0[voz];"
            f"[1:a]volume='{volume_expr}',"
            f"afade=t=in:st=0:d={fade_in_duracao},"
            f"afade=t=out:st={fade_out_inicio}:"
            f"d={fade_out_duracao}[musica];"
            "[voz][musica]"
            "amix=inputs=2:duration=first:"
            "dropout_transition=0[a]"
        )

        proc = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(music_path),
            "-filter_complex",
            filtro,
            "-map",
            "0:v",
            "-map",
            "[a]",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(output_path),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )

        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            detalhe = stderr.decode(
                "utf-8",
                errors="ignore",
            )
            raise RuntimeError(
                "Falha ao misturar voz e música: "
                f"{detalhe[-1600:]}"
            )

        if not output_path.is_file():
            raise RuntimeError(
                "FFmpeg não gerou o vídeo final."
            )

        return output_path

    async def _generate_tts_voice(
        self,
        text: str,
        output_path: Path,
        voice: str = "pt-BR-AntonioNeural",
    ) -> Path:
        """Gera a voz do personagem usando Edge TTS."""

        text = text.strip()

        if not text:
            raise ValueError(
                "Texto da fala não pode estar vazio."
            )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        communicate = edge_tts.Communicate(
            text=text,
            voice=voice,
            rate="-8%",
        )

        await communicate.save(str(output_path))

        if not output_path.is_file():
            raise RuntimeError(
                "Edge TTS não gerou o arquivo de voz."
            )

        if output_path.stat().st_size == 0:
            raise RuntimeError(
                "Edge TTS gerou um arquivo de voz vazio."
            )

        return output_path

    def _get_kie_api_key(self) -> str:
        """Obtém a chave KIE do ambiente ou do arquivo .env."""

        chave = os.getenv("KIE_API_KEY", "").strip()

        if chave:
            return chave

        env_path = Path("/home/olavo/inemacabot/.env")

        if env_path.is_file():
            for linha in env_path.read_text(
                encoding="utf-8"
            ).splitlines():
                if linha.startswith("KIE_API_KEY="):
                    chave = linha.split("=", 1)[1].strip()
                    if chave:
                        return chave

        raise RuntimeError(
            "KIE_API_KEY não configurada."
        )

    async def _upload_kie_file(
        self,
        file_path: Path,
    ) -> str:
        """Envia um arquivo local para a KIE e retorna a URL temporária."""

        if not file_path.is_file():
            raise ValueError(
                f"Arquivo para upload não encontrado: {file_path}"
            )

        kie_key = self._get_kie_api_key()

        url = (
            "https://kieai.redpandaai.co/"
            "api/file-stream-upload"
        )

        headers = {
            "Authorization": f"Bearer {kie_key}",
        }

        data = {
            "uploadPath": "inemacabot/lipsync",
            "fileName": file_path.name,
        }

        async with httpx.AsyncClient(
            timeout=120.0
        ) as client:
            with file_path.open("rb") as arquivo:
                files = {
                    "file": (
                        file_path.name,
                        arquivo,
                        "application/octet-stream",
                    )
                }

                resposta = await client.post(
                    url,
                    headers=headers,
                    data=data,
                    files=files,
                )

        resposta.raise_for_status()

        payload = resposta.json()

        download_url = (
            payload.get("data", {})
            .get("downloadUrl")
        )

        if not download_url:
            raise RuntimeError(
                f"KIE não retornou downloadUrl: {payload}"
            )

        return str(download_url)

    async def _create_kie_infinitalk_task(
        self,
        image_url: str,
        audio_url: str,
        prompt: str | None = None,
        resolution: str = "480p",
    ) -> str:
        """Cria uma tarefa InfiniteTalk na KIE e retorna o taskId."""

        kie_key = self._get_kie_api_key()

        url = "https://api.kie.ai/api/v1/jobs/createTask"

        if prompt is None:
            prompt = (
                "A friendly, calm and happy person welcoming someone to a new place. "
                "Maintain a relaxed posture, steady head and shoulders, and gentle natural movement. "
                "Use a soft pleasant expression throughout the speech, with a subtle smile visible from the beginning. "
                "Keep warm, reassuring eye contact and natural blinking. "
                "Facial expressions should feel positive, welcoming and relaxed, never exaggerated. "
                "Lip synchronization must remain accurate, with moderate and natural mouth movement. "
                "Avoid sudden head movement, strong eyebrow emphasis, leaning forward, rocking, or large gestures. "
                "Near the end, let the smile become slightly warmer and hold it naturally. "
                "The overall performance should feel welcoming, peaceful, confident and genuinely happy."
            )

        payload = {
            "model": "infinitalk/from-audio",
            "input": {
                "image_url": image_url,
                "audio_url": audio_url,
                "prompt": prompt,
                "resolution": resolution,
            },
        }

        headers = {
            "Authorization": f"Bearer {kie_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(
            timeout=120.0
        ) as client:
            resposta = await client.post(
                url,
                headers=headers,
                json=payload,
            )

        resposta.raise_for_status()

        data = resposta.json()

        task_id = (
            data.get("data", {})
            .get("taskId")
        )

        if not task_id:
            raise RuntimeError(
                f"KIE InfiniteTalk não retornou taskId: {data}"
            )

        return str(task_id)


    async def _create_kie_lipsync_task(
        self,
        video_url: str,
        audio_url: str,
    ) -> str:
        """Cria uma tarefa de lip sync na KIE e retorna o taskId."""

        kie_key = self._get_kie_api_key()

        url = "https://api.kie.ai/api/v1/jobs/createTask"

        payload = {
            "model": "volcengine/video-to-video-lip-sync",
            "input": {
                "mode": "basic",
                "video_url": video_url,
                "audio_url": audio_url,
                "separate_vocal": False,
                "open_scenedet": False,
                "align_audio": True,
                "align_audio_reverse": False,
                "templ_start_seconds": 0,
            },
        }

        headers = {
            "Authorization": f"Bearer {kie_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(
            timeout=120.0
        ) as client:
            resposta = await client.post(
                url,
                headers=headers,
                json=payload,
            )

        resposta.raise_for_status()

        data = resposta.json()

        task_id = (
            data.get("data", {})
            .get("taskId")
        )

        if not task_id:
            raise RuntimeError(
                f"KIE não retornou taskId: {data}"
            )

        return str(task_id)

    async def _wait_kie_task_result(
        self,
        task_id: str,
        timeout_s: float = 900.0,
        interval_s: float = 5.0,
    ) -> str:
        """Aguarda uma tarefa KIE e retorna a primeira URL gerada."""

        kie_key = self._get_kie_api_key()

        url = (
            "https://api.kie.ai/api/v1/jobs/recordInfo"
            f"?taskId={task_id}"
        )

        headers = {
            "Authorization": f"Bearer {kie_key}",
        }

        inicio = asyncio.get_running_loop().time()

        async with httpx.AsyncClient(
            timeout=120.0
        ) as client:
            while True:
                resposta = await client.get(
                    url,
                    headers=headers,
                )

                resposta.raise_for_status()

                payload = resposta.json()
                data = payload.get("data", {})
                state = data.get("state")

                if state == "success":
                    response = data.get("response") or {}
                    urls = response.get("resultUrls") or []

                    if not urls:
                        result_json = data.get("resultJson")

                        if result_json:
                            import json

                            parsed = json.loads(result_json)
                            urls = parsed.get("resultUrls") or []

                    if not urls:
                        raise RuntimeError(
                            f"KIE concluiu sem resultUrls: {payload}"
                        )

                    return str(urls[0])

                if state == "fail":
                    raise RuntimeError(
                        "KIE falhou: "
                        f"{data.get('failMsg') or payload}"
                    )

                agora = asyncio.get_running_loop().time()

                if agora - inicio >= timeout_s:
                    raise TimeoutError(
                        "Tempo esgotado aguardando tarefa KIE."
                    )

                await asyncio.sleep(interval_s)


    async def _wait_kie_lipsync_result(
        self,
        task_id: str,
        timeout_s: float = 900.0,
        interval_s: float = 5.0,
    ) -> str:
        """Aguarda a KIE concluir o lip sync e retorna a URL final."""

        kie_key = self._get_kie_api_key()

        url = (
            "https://api.kie.ai/api/v1/jobs/recordInfo"
            f"?taskId={task_id}"
        )

        headers = {
            "Authorization": f"Bearer {kie_key}",
        }

        inicio = asyncio.get_running_loop().time()

        async with httpx.AsyncClient(
            timeout=120.0
        ) as client:
            while True:
                resposta = await client.get(
                    url,
                    headers=headers,
                )

                resposta.raise_for_status()

                payload = resposta.json()
                data = payload.get("data", {})
                state = data.get("state")

                if state == "success":
                    response = data.get("response") or {}
                    urls = response.get("resultUrls") or []

                    if not urls:
                        raise RuntimeError(
                            f"KIE concluiu sem resultUrls: {payload}"
                        )

                    return str(urls[0])

                if state == "fail":
                    raise RuntimeError(
                        "KIE falhou no lip sync: "
                        f"{data.get('failMsg') or payload}"
                    )

                agora = asyncio.get_running_loop().time()

                if agora - inicio >= timeout_s:
                    raise TimeoutError(
                        "Tempo esgotado aguardando lip sync da KIE."
                    )

                await asyncio.sleep(interval_s)

    async def _download_kie_result(
        self,
        result_url: str,
        output_path: Path,
    ) -> Path:
        """Baixa o vídeo final gerado pela KIE."""

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        async with httpx.AsyncClient(
            timeout=180.0,
            follow_redirects=True,
        ) as client:
            resposta = await client.get(result_url)

        resposta.raise_for_status()

        output_path.write_bytes(resposta.content)

        if not output_path.is_file():
            raise RuntimeError(
                "Download da KIE não gerou arquivo."
            )

        if output_path.stat().st_size == 0:
            raise RuntimeError(
                "Arquivo baixado da KIE está vazio."
            )

        return output_path

    async def _generate_kie_infinitalk(
        self,
        image_path: Path,
        audio_path: Path,
        output_path: Path,
        prompt: str | None = None,
        resolution: str = "480p",
    ) -> Path:
        """Executa o ciclo completo do InfiniteTalk pela KIE."""

        image_url, audio_url = await asyncio.gather(
            self._upload_kie_file(image_path),
            self._upload_kie_file(audio_path),
        )

        task_id = await self._create_kie_infinitalk_task(
            image_url,
            audio_url,
            prompt=prompt,
            resolution=resolution,
        )

        result_url = await self._wait_kie_task_result(
            task_id
        )

        return await self._download_kie_result(
            result_url,
            output_path,
        )


    async def _generate_kie_lipsync(
        self,
        video_path: Path,
        audio_path: Path,
        output_path: Path,
    ) -> Path:
        """Executa o ciclo completo de lip sync pela KIE."""

        video_url, audio_url = await asyncio.gather(
            self._upload_kie_file(video_path),
            self._upload_kie_file(audio_path),
        )

        task_id = await self._create_kie_lipsync_task(
            video_url,
            audio_url,
        )

        result_url = await self._wait_kie_lipsync_result(
            task_id
        )

        return await self._download_kie_result(
            result_url,
            output_path,
        )

