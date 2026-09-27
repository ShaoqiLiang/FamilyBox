"""随包资源路径解析、产品版本读取（运行时只消费明文；解密属于开发/打包环节）。

优先级：
1. PyInstaller 冻结 → ``sys._MEIPASS/<name>``（release.bat 打包前解密进包）；
2. 源码开发 → ``build/assets/<name>``（scripts/prepare_assets.py 解密出的
   明文工作副本，gitignored，密钥在本机 keys/logo_private.pem）；
3. 兜底 → ``src/window/<name>`` 原样（.enc 等由调用方自行处理）。

不做异常处理：解析结果可能不存在，调用方自行 try/except 降级。
产品版本：src/Version.ini（唯一来源）——get_version() 读取，冻结时随包。
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

log = logging.getLogger(__name__)


def asset_path(name: str) -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / name
    dev = Path(__file__).resolve().parents[2] / "build" / "assets" / Path(name).name
    if dev.is_file():
        return dev
    return Path(__file__).resolve().parent / name


def version_ini_path() -> Path:
    """src/Version.ini 路径:冻结取 _MEIPASS,开发取 src/。"""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "Version.ini"
    return Path(__file__).resolve().parents[1] / "Version.ini"


_version_cache: str | None = None


def get_version() -> str:
    """读 src/Version.ini 首行「Version x.y.z.w」的产品版本号(结果缓存)。

    文件缺失/格式不符 → 返回 "0.0.0" 并记警告,不抛异常。
    """
    global _version_cache
    if _version_cache is not None:
        return _version_cache
    ver = "0.0.0"
    try:
        text = version_ini_path().read_text(encoding="utf-8")
    except OSError as e:
        log.warning("version ini unavailable: %s", e)
    else:
        m = re.search(r"(?mi)^\s*Version\s+(\S+)\s*$", text)
        if m:
            ver = m.group(1)
        else:
            log.warning("version ini has no 'Version x.y.z' line")
    _version_cache = ver
    return ver
