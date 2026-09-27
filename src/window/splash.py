"""启动 logo 动画(A1):独立无边框窗播放明文 logo.webm(PyAV 纯内存解码)。

PyCharm 式时序:先弹无边框动画窗(800×600,屏幕居中),播完/跳过后由调用方
重建 display 创建主窗口;任意按键 / 鼠标点击跳过;播放中收到 QUIT 返回
False(调用方据此退出)。解码依赖 PyAV(自带 FFmpeg 动态库);文件缺失/
打不开返回 True 由调用方静默继续。
"""

from __future__ import annotations

import logging
from pathlib import Path

import pygame

log = logging.getLogger(__name__)

_SPLASH_SIZE = (800, 600)


def play_logo_video(
    path: Path, fps: int = 30, size: tuple[int, int] = _SPLASH_SIZE
) -> bool:
    """新建无边框窗播放 logo 动画;返回 False 表示用户要求退出。

    文件缺失/无法解码 → 记日志并返回 True(跳过,不阻断启动)。
    调用方在返回后需重建 display(NOFRAME 动画窗 → 主窗样式)。
    """
    import av

    try:
        container = av.open(str(path))
    except (OSError, av.FFmpegError) as e:
        log.warning("splash: cannot open %s: %s", path.name, e)
        return True
    if not container.streams.video:
        log.warning("splash: no video stream in %s", path.name)
        container.close()
        return True
    screen = pygame.display.set_mode(size, pygame.NOFRAME)
    try:
        clock = pygame.time.Clock()
        screen.fill((0, 0, 0))
        pygame.display.flip()
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
            screen.blit(pygame.transform.scale(surf, size), (0, 0))
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
