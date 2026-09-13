"""原生 Win32 菜单栏（L5 前端配套，方案 A）。

设计要点（doc/plans/2026-09-13T15-55-39.md 已批准）：
- ctypes 直挂 `CreateMenu/AppendMenuW/SetMenu` 到 pygame 窗口 HWND；
- 子类化 WndProc（SetWindowLongPtrW + CallWindowProcW 转发）拦截
  `WM_COMMAND`，把菜单点击 post 成 pygame 自定义事件 `FB_MENU`；
- 事件载荷 `{"action": Action, "region"/"scale"/"lang": 值}`，由前端分发到
  与快捷键相同的动作函数；
- 仅 Windows 生效；非 Windows 平台 attach() 记录并跳过（测试也不依赖真窗口）。
"""

from __future__ import annotations

import ctypes
import logging
from ctypes import wintypes
from enum import IntEnum
from typing import Any, Callable

import pygame

from window.localization import tr

log = logging.getLogger(__name__)

WM_COMMAND = 0x0111
GWLP_WNDPROC = -4
MF_STRING = 0x0
MF_GRAYED = 0x1
MF_CHECKED = 0x8
MF_POPUP = 0x10
MF_SEPARATOR = 0x800


class Action(IntEnum):
    OPEN = 100
    EXIT = 101
    PAUSE = 110
    RESET = 111
    TIMING_NTSC = 120
    TIMING_PAL = 121
    LANG_ZH = 130
    LANG_EN = 131
    MUTE = 140
    FULLSCREEN = 141
    SCALE_1 = 150
    SCALE_2 = 151
    SCALE_3 = 152
    SCALE_4 = 153
    KEYS_HELP = 160
    ABOUT = 161


# 构建 spec：(kind, ident, text_key, flags)
# kind: "item" | "popup" | "sep"；popup 的 ident 是嵌套 spec 列表；
# 语言在 build 时经 tr() 解析。
def _menu_spec(lang: str, state: dict[str, Any]) -> list[tuple]:
    def chk(cond: bool) -> int:
        return MF_CHECKED if cond else 0

    return [
        (
            "popup",
            [
                ("item", Action.OPEN, "file.open", 0),
                ("sep", None, None, 0),
                ("item", 0, "file.recent", MF_GRAYED),  # 第二批：最近打开
                ("sep", None, None, 0),
                ("item", Action.EXIT, "file.exit", 0),
            ],
            "menu.file",
            0,
        ),
        (
            "popup",
            [
                ("item", Action.PAUSE, "emu.pause", 0),
                ("item", Action.RESET, "emu.reset", 0),
                ("sep", None, None, 0),
                (
                    "popup",
                    [
                        (
                            "item",
                            Action.TIMING_NTSC,
                            "emu.timing.ntsc",
                            chk(state.get("region") == "ntsc"),
                        ),
                        (
                            "item",
                            Action.TIMING_PAL,
                            "emu.timing.pal",
                            chk(state.get("region") == "pal"),
                        ),
                    ],
                    "emu.timing",
                    0,
                ),
            ],
            "menu.emu",
            0,
        ),
        (
            "popup",
            [
                (
                    "popup",
                    [
                        (
                            "item",
                            Action.LANG_ZH,
                            "lang.zh",
                            chk(state.get("lang") == "zh"),
                        ),
                        (
                            "item",
                            Action.LANG_EN,
                            "lang.en",
                            chk(state.get("lang") == "en"),
                        ),
                    ],
                    "set.language",
                    0,
                ),
                ("sep", None, None, 0),
                ("item", Action.MUTE, "set.mute", chk(bool(state.get("muted")))),
                (
                    "item",
                    Action.FULLSCREEN,
                    "set.fullscreen",
                    chk(bool(state.get("fullscreen"))),
                ),
                ("sep", None, None, 0),
                (
                    "popup",
                    [
                        (
                            "item",
                            Action.SCALE_1,
                            "scale.1",
                            chk(state.get("scale") == 1),
                        ),
                        (
                            "item",
                            Action.SCALE_2,
                            "scale.2",
                            chk(state.get("scale") == 2),
                        ),
                        (
                            "item",
                            Action.SCALE_3,
                            "scale.3",
                            chk(state.get("scale") == 3),
                        ),
                        (
                            "item",
                            Action.SCALE_4,
                            "scale.4",
                            chk(state.get("scale") == 4),
                        ),
                    ],
                    "set.scale",
                    0,
                ),
                ("sep", None, None, 0),
                ("item", 0, "set.keys", MF_GRAYED),  # M5：按键设置对话框
            ],
            "menu.settings",
            0,
        ),
        (
            "popup",
            [
                ("item", Action.KEYS_HELP, "help.keys", 0),
                ("item", Action.ABOUT, "help.about", 0),
            ],
            "menu.help",
            0,
        ),
    ]


class MenuBar:
    """挂接到 pygame 窗口 HWND 的原生菜单；语言/状态变化时 rebuild()。"""

    def __init__(self) -> None:
        self._user32: Any = None
        self._old_proc: int | None = None
        self._proc_ref: Any = None  # 防 GC
        self._hmenu: int | None = None
        self._active = False

    @property
    def active(self) -> bool:
        return self._active

    def _api(self) -> Any:
        if self._user32 is None:
            u = ctypes.windll.user32
            u.SetMenu.argtypes = [wintypes.HWND, wintypes.HMENU]
            u.CreateMenu.restype = wintypes.HMENU
            u.CreatePopupMenu.restype = wintypes.HMENU
            u.AppendMenuW.argtypes = [
                wintypes.HMENU,
                wintypes.UINT,
                ctypes.c_size_t,
                wintypes.LPCWSTR,
            ]
            u.SetWindowLongPtrW.restype = ctypes.c_longlong
            u.SetWindowLongPtrW.argtypes = [
                wintypes.HWND,
                ctypes.c_int,
                self._proc_type(),
            ]
            u.CallWindowProcW.restype = ctypes.c_longlong
            u.CallWindowProcW.argtypes = [
                ctypes.c_longlong,
                wintypes.HWND,
                ctypes.c_uint,
                ctypes.c_size_t,
                ctypes.c_ssize_t,
            ]
            u.GetWindowLongPtrW.restype = ctypes.c_longlong
            u.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
            self._user32 = u
        return self._user32

    def _proc_type(self) -> Any:
        return ctypes.WINFUNCTYPE(
            ctypes.c_longlong,
            wintypes.HWND,
            ctypes.c_uint,
            ctypes.c_size_t,
            ctypes.c_ssize_t,
        )

    def attach(
        self,
        hwnd: int,
        lang: str,
        state: dict[str, Any],
        on_action: Callable[[Action, dict[str, Any]], None],
        event_type: int,
    ) -> bool:
        """构建菜单并子类化窗口过程。失败返回 False（可回退无菜单模式）。"""
        self._on_action = on_action
        self._event_type = event_type
        if sys_platform() != "win32" or not hwnd:
            log.info("menu bar unavailable on this platform")
            return False
        self._on_action = on_action
        u = self._api()
        self._hmenu = self._build_hmenu(lang, state)
        if not u.SetMenu(hwnd, self._hmenu):
            log.warning("SetMenu failed")
            return False

        def proc(h: int, msg: int, wp: int, lp: int) -> int:
            if msg == WM_COMMAND and ((wp >> 16) & 0xFFFF) == 0:
                menu_id = wp & 0xFFFF
                try:
                    action = Action(menu_id)
                except ValueError:
                    action = None
                if action is not None:
                    extra: dict[str, Any] = {}
                    if action in (Action.TIMING_NTSC, Action.TIMING_PAL):
                        extra["region"] = (
                            "ntsc" if action == Action.TIMING_NTSC else "pal"
                        )
                    if action in (
                        Action.SCALE_1,
                        Action.SCALE_2,
                        Action.SCALE_3,
                        Action.SCALE_4,
                    ):
                        extra["scale"] = int(action) - int(Action.SCALE_1) + 1
                    if action == Action.LANG_ZH:
                        extra["lang"] = "zh"
                    if action == Action.LANG_EN:
                        extra["lang"] = "en"
                    pygame.event.post(
                        pygame.event.Event(
                            self._event_type, action=int(action), **extra
                        )
                    )
            assert self._old_proc is not None
            return int(u.CallWindowProcW(self._old_proc, h, msg, wp, lp))

        self._proc_ref = self._proc_type()(proc)
        self._old_proc = int(u.SetWindowLongPtrW(hwnd, GWLP_WNDPROC, self._proc_ref))
        self._active = True
        return True

    def rebuild(self, hwnd: int, lang: str, state: dict[str, Any]) -> None:
        """语言/状态变化后重建菜单（不重复子类化）。"""
        if not self._active:
            self.attach(hwnd, lang, state, self._on_action, self._event_type)
            return
        u = self._api()
        self._hmenu = self._build_hmenu(lang, state)
        u.SetMenu(hwnd, self._hmenu)

    def _build_hmenu(self, lang: str, state: dict[str, Any]) -> int:
        u = self._api()
        bar = u.CreateMenu()

        def fill(hmenu: int, spec: list[tuple]) -> None:
            for kind, ident, text_key, extra in spec:
                if kind == "sep":
                    u.AppendMenuW(hmenu, MF_SEPARATOR, 0, "")
                    continue
                text = tr(lang, text_key)
                if kind == "popup":
                    sub = u.CreatePopupMenu()
                    fill(sub, ident)
                    u.AppendMenuW(hmenu, MF_POPUP | MF_STRING, sub, text)
                else:
                    u.AppendMenuW(hmenu, MF_STRING | extra, int(ident), text)

        fill(bar, _menu_spec(lang, state))
        return bar

    def detach(self, hwnd: int) -> None:
        """窗口销毁前恢复原窗口过程。"""
        if self._active and self._old_proc is not None and hwnd:
            self._api().SetWindowLongPtrW(hwnd, GWLP_WNDPROC, self._old_proc)
        self._active = False


def sys_platform() -> str:
    import sys

    return sys.platform
