"""检查更新（S4 v1）——查询 GitHub Releases 最新版本，供帮助菜单手动触发。

只查询与打开发布页；**不做自动下载/替换**（安装目录写入需管理员且需原子性，
后续再议）。自愈路径 = 用户重下新包 + 外部签名清单验证（scripts/verify_release.py）。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

RELEASES_LATEST_API = (
    "https://api.github.com/repos/ShaoqiLiang/FamilyBox/releases/latest"
)
RELEASES_PAGE = "https://github.com/ShaoqiLiang/FamilyBox/releases/latest"
DEFAULT_TIMEOUT = 8.0


@dataclass
class UpdateReport:
    """error 非空 = 查询失败；latest 为发布 tag 去掉 v 前缀后的版本号。"""

    current: str
    latest: str | None = None
    error: str | None = None

    @property
    def has_update(self) -> bool:
        if self.error or not self.latest:
            return False
        return _version_tuple(self.latest) > _version_tuple(self.current)


def _version_tuple(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for piece in version.strip().lstrip("vV").split("."):
        try:
            parts.append(int(piece))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def fetch_latest(current: str, timeout: float = DEFAULT_TIMEOUT) -> UpdateReport:
    """查 latest release；网络/解析失败折叠进 error 字段，不抛异常。"""
    request = urllib.request.Request(
        RELEASES_LATEST_API,
        headers={
            "User-Agent": "FamilyBox-Update-Check",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return UpdateReport(current=current, error=str(exc))
    tag = str(data.get("tag_name", "")).strip()
    if not tag:
        return UpdateReport(current=current, error="release tag missing")
    return UpdateReport(current=current, latest=tag.lstrip("vV"))
