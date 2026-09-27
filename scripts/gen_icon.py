"""从加密的 logo 素材派生应用图标（D1）。

用法：uv run python scripts/gen_icon.py
编译时解密（FBENC1），按背景色垫成正方形后生成：
  src/window/assets/icon.png        32×32，窗口/任务栏图标 ← logo.png（白底橙标）
  src/window/assets/familybox.ico   多尺寸（16/24/32/48/64/256），exe 图标 ← logo2（橙底白标）
Pillow 仅开发期使用，产物入库，运行时零 PIL 依赖。
"""

from __future__ import annotations

import hashlib
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "src" / "window" / "assets"
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (256, 256)]

sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))
from fbenc import decrypt_bytes, encrypt_bytes  # noqa: E402

ASSETS_DIR = REPO / "src" / "window" / "assets"


def square_pad(img: Image.Image) -> Image.Image:
    """非正方形素材按角落背景色垫成正方形（logo 系列为 4:3）。"""
    side = max(img.size)
    bg = img.getpixel((2, 2))
    canvas = Image.new("RGB", (side, side), bg)
    canvas.paste(img, ((side - img.width) // 2, (side - img.height) // 2))
    return canvas


def load_square(stem: str) -> Image.Image:
    raw = decrypt_bytes((ASSETS_DIR / f"{stem}.enc").read_bytes())
    return square_pad(Image.open(BytesIO(raw)).convert("RGB"))


def main() -> int:
    win_icon = load_square("logo.png")  # 窗口/任务栏：白底
    exe_icon = load_square("logo2.png")  # exe 文件：橙底
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 产物一律密文入库（FBENC2）——明文只在 prepare_assets（开发）/打包（发行）时存在：
    #   icon.png.enc        prepare_assets 解密 → build/assets/icon.png（窗口图标）
    #   familybox.ico.enc   prepare_assets/release 解密 → exe 嵌入
    png_buf = BytesIO()
    win_icon.resize((32, 32), Image.Resampling.LANCZOS).save(png_buf, "PNG")
    ico_buf = BytesIO()
    exe_icon.resize((256, 256), Image.Resampling.LANCZOS).save(
        ico_buf, format="ICO", sizes=ICO_SIZES
    )
    for stem, blob in (
        ("icon.png", png_buf.getvalue()),
        ("familybox.ico", ico_buf.getvalue()),
    ):
        out = OUT_DIR / (stem + ".enc")
        out.write_bytes(encrypt_bytes(blob))
        digest = hashlib.sha256(out.read_bytes()).hexdigest()
        print(f"{out}  sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
