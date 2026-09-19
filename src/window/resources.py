"""随包资源路径解析（运行时只消费明文；解密属于开发/打包环节）。

优先级：
1. PyInstaller 冻结 → ``sys._MEIPASS/<name>``（release.bat 打包前解密进包）；
2. 源码开发 → ``build/assets/<name>``（scripts/prepare_assets.py 解密出的
   明文工作副本，gitignored，密钥在本机 keys/logo_private）；
3. 兜底 → ``src/window/<name>`` 原样（.enc 等由调用方自行处理）。

不做异常处理：解析结果可能不存在，调用方自行 try/except 降级。
"""

from __future__ import annotations

import sys
from pathlib import Path


def asset_path(name: str) -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / name
    dev = Path(__file__).resolve().parents[2] / "build" / "assets" / Path(name).name
    if dev.is_file():
        return dev
    return Path(__file__).resolve().parent / name
