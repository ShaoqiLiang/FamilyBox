"""把 src/images 明文素材加密为 src/window/assets/*.enc（FBENC2 混合加密）。

用法：uv run python scripts/encrypt_assets.py
明文原件不入库（.gitignore /src/images/）；密钥对本机 keys/logo_public.pem
（加密）/ logo_private.pem（解密），见 scripts/fbenc.py 与 scripts/gen_keys.py。
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC_DIR = REPO / "src" / "images"
OUT_DIR = REPO / "src" / "window" / "assets"

sys.path.insert(0, str(REPO / "scripts"))
from fbenc import encrypt_bytes  # noqa: E402

FILES = ["logo.png", "logo2.png", "logo.webm"]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        src = SRC_DIR / name
        if not src.is_file():
            print(f"[SKIP] missing plaintext: {src}")
            continue
        out = OUT_DIR / (name + ".enc")
        out.write_bytes(encrypt_bytes(src.read_bytes()))
        print(f"{out}  ({out.stat().st_size} bytes)")
    print("done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
