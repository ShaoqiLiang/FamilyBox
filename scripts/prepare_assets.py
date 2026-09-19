"""解密 assets/*.enc → build/assets/（明文工作副本，gitignored）。

用法：uv run python scripts/prepare_assets.py
run.bat / release.bat 在启动与打包前调用。解密私钥在本机
keys/logo_private.pem；缺失时 run.bat 的调用为非致命（运行时图标/动画降级）。
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ASSETS = REPO / "src" / "window" / "assets"
OUT = REPO / "build" / "assets"

sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))
from fbenc import decrypt_bytes  # noqa: E402


def main() -> int:
    encs = sorted(ASSETS.glob("*.enc"))
    if not encs:
        print("[WARN] no .enc assets found in", ASSETS)
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    for enc in encs:
        out = OUT / enc.stem
        out.write_bytes(decrypt_bytes(enc.read_bytes()))
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
