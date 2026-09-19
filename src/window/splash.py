"""启动 logo 动画（A1）：播放明文 logo.webm（PyAV 纯内存解码，无 numpy）。

每次启动都播（约 2.1s @30fps）；任意按键 / 鼠标点击跳过；播放中收到
QUIT 返回 False（调用方据此退出）。解码依赖 PyAV（自带 FFmpeg 动态库），
av.open(BytesIO) 全程内存、零临时文件；帧转换走 swscale + 缓冲协议
（to_rgb + memoryview(plane)），不引入 numpy；文件缺失/打不开返回 True，
由调用方静默继续。
"""

from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path

import pygame

log = logging.getLogger(__name__)


def play_logo_video(path: Path, screen: pygame.Surface, fps: int = 30) -> bool:
    """在 screen 上播放 logo 视频；返回 False 表示用户要求退出。

    文件缺失/无法解码 → 记日志并返回 True（跳过，不阻断启动）。
    """
    import av

    try:
        container = av.open(BytesIO(path.read_bytes()))
        assert isinstance(container, av.container.InputContainer)
    except (OSError, av.FFmpegError) as e:
        log.warning("splash: cannot open %s: %s", path.name, e)
        return True
    try:
        clock = pygame.time.Clock()
        w, h = screen.get_size()
        screen.fill((0, 0, 0))
        for frame in container.decode(video=0):
            plane = frame.to_rgb().planes[0]
            raw = bytes(memoryview(plane))
            w3 = plane.width * 3
            if plane.line_size != w3:  # swscale 行尾对齐填充 → 去 stride
                raw = b"".join(
                    raw[y * plane.line_size : y * plane.line_size + w3]
                    for y in range(plane.height)
                )
            surf = pygame.image.frombuffer(raw, (plane.width, plane.height), "RGB")
            screen.blit(pygame.transform.scale(surf, (w, h)), (0, 0))
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return False
                if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    return True
            clock.tick(fps)
        return True
    finally:
        container.close()
