"""A1 启动动画测试：真实视频在 SDL dummy 下全链路播放 + 缺文件降级。

明文视频由本测试现场解密到临时目录（运行时本身只读明文路径）。
play_logo_video 自建无边框 display（PyCharm 式），测试无需预建 screen。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pygame
import pytest

from window.resources import asset_path
from window.splash import play_logo_video

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from fbenc import decrypt_bytes  # noqa: E402


@pytest.fixture()
def plain_video(tmp_path: Path) -> Path:
    src = asset_path("assets/logo.webm.enc")
    out = tmp_path / "logo.webm"
    out.write_bytes(decrypt_bytes(src.read_bytes()))
    return out


@pytest.fixture()
def dummy_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    pygame.display.init()  # 上一个用例 teardown 可能 quit 过,必须确保就绪
    yield
    pygame.display.quit()
    pygame.display.init()  # 留给后续用例


class TestPlayLogoVideo:
    def test_full_playback_returns_true(
        self, plain_video: Path, dummy_env: None
    ) -> None:
        """解密产物 → H.264 解码 → 缩放 blit 全链路；fps 放开避免 wall-clock 等待。"""
        assert play_logo_video(plain_video, fps=1000) is True

    def test_user_skip_returns_true(self, plain_video: Path, dummy_env: None) -> None:
        """首帧后立即有按键事件 → 跳过并返回 True。"""
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_SPACE))
        assert play_logo_video(plain_video, fps=1000) is True

    def test_quit_during_playback_returns_false(
        self, plain_video: Path, dummy_env: None
    ) -> None:
        pygame.event.post(pygame.event.Event(pygame.QUIT))
        assert play_logo_video(plain_video, fps=1000) is False

    def test_missing_file_returns_true(self, tmp_path: Path, dummy_env: None) -> None:
        """文件缺失 → 记日志跳过（返回 True），绝不阻断启动。"""
        assert play_logo_video(tmp_path / "missing.webm") is True
