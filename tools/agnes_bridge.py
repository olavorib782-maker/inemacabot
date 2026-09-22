from __future__ import annotations

import json
import sys
from pathlib import Path

MUSICAVIDEO_ROOT = Path("/home/olavo/musicavideo")
AGNES_DECL = MUSICAVIDEO_ROOT / "providers" / "agnes.models.json"

sys.path.insert(0, str(MUSICAVIDEO_ROOT))

from providers.agnes import Agnes  # noqa: E402


def main() -> int:
    if len(sys.argv) != 5:
        print(
            "Uso: agnes_bridge.py <foto> <saida_dir> <shot_n> <prompt>",
            file=sys.stderr,
        )
        return 2

    foto = Path(sys.argv[1]).resolve()
    saida_dir = Path(sys.argv[2]).resolve()
    shot_n = int(sys.argv[3])
    prompt = sys.argv[4]

    if not foto.is_file():
        print(f"Imagem não encontrada: {foto}", file=sys.stderr)
        return 3

    saida_dir.mkdir(parents=True, exist_ok=True)

    decl = json.loads(
        AGNES_DECL.read_text(encoding="utf-8")
    )

    agnes = Agnes(decl)

    shot = {
        "n": shot_n,
        "duracao_s": 8,
        "first_frame": str(foto),
    }

    video = agnes._um_shot(
        prompt,
        shot,
        "736",
        "1312",
        saida_dir,
        modelo="agnes-video-2.5-flash",
    )

    print(video)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
