"""UI 字符串表（zh/en 双语）。

约定：
- 语言名（"中文"/"English"）以各自语言显示，永不翻译；
- 文案键全部 ASCII 常量，取值可含中英双语文案；
- 新增界面文案必须同时补两种语言，缺语言时回退中文。
"""

from __future__ import annotations

STRINGS: dict[str, dict[str, str]] = {
    "zh": {
        # 菜单栏
        "menu.file": "文件(&F)",
        "menu.emu": "模拟(&E)",
        "menu.settings": "设置(&S)",
        "menu.help": "帮助(&H)",
        "file.open": "打开卡带...(&O)",
        "file.recent": "最近打开",
        "file.exit": "退出(&X)",
        "emu.pause": "暂停 / 恢复",
        "emu.reset": "软复位",
        "emu.timing": "时序标准",
        "emu.timing.ntsc": "NTSC（默认，60.1fps）",
        "emu.timing.pal": "PAL（欧洲卡带，50.0fps）",
        "set.language": "语言/Language",
        "set.mute": "静音",
        "set.fullscreen": "全屏",
        "set.scale": "窗口缩放",
        "lang.zh": "中文",
        "lang.en": "English",
        "scale.1": "1×",
        "scale.2": "2×",
        "scale.3": "3×",
        "scale.4": "4×",
        "set.keys": "按键设置...",
        "help.keys": "按键说明...",
        "help.about": "关于 FamilyBox...",
        # 对话框
        "dlg.keys.title": "按键说明",
        "dlg.keys.body": (
            "方向键 / WASD：移动\n"
            "Z / J / N / 空格：跳跃 (A)\n"
            "M / K：加速跑 (B)\n"
            "Enter / Tab：开始\n"
            "右Shift：选择\n"
            "O：打开卡带\n"
            "P：暂停 / 恢复\n"
            "R：软复位\n"
            "F9：静音    F11：全屏\n"
            "ESC：退出全屏/最大化"
        ),
        "dlg.about.title": "关于 FamilyBox",
        "dlg.about.body": (
            "FamilyBox v0.1.0\n"
            "FC/NES 模拟器（C++20 核心 + Python 界面）\n"
            "作者：ShaoqiLiang\n"
            "\n"
            "请使用自备的合法卡带转储文件。"
        ),
        "dlg.loadfail.title": "载入失败",
        "dlg.loadfail.body": "无法载入该文件（可能是不支持的 mapper 或损坏的文件）：\n{path}",
        # 对话框（英文菜单时也用英文文案键）
        "dlg.keys.title.en": "Controls",
        "dlg.about.title.en": "About FamilyBox",
        # OSD
        "osd.loaded": "已载入 {name}",
        "osd.loadfail": "载入失败（不支持的卡带）：{name}",
        "osd.paused": "暂停",
        "osd.resumed": "继续",
        "osd.reset": "已软复位",
        "osd.muted": "已静音",
        "osd.unmuted": "取消静音",
        "osd.fullscreen": "全屏",
        "osd.windowed": "窗口化",
        "osd.scale": "缩放 {n}x",
        "osd.region": "时序：{name}",
        "osd.lang": "语言已切换为中文",
        "osd.no_dialog": "此平台暂无文件选择框，请用命令行传入 ROM",
        # 区域名（OSD 用）
        "region.ntsc": "NTSC",
        "region.pal": "PAL",
        # 引导屏
        "loader.title": "FamilyBox — 请载入 NES 卡带",
        "loader.hint": "按 O 选择 .nes 文件，或直接把文件拖进窗口",
    },
    "en": {
        "menu.file": "&File",
        "menu.emu": "&Emulation",
        "menu.settings": "&Settings",
        "menu.help": "&Help",
        "file.open": "&Open Cartridge...\tCtrl+O",
        "file.recent": "Recent",
        "file.exit": "E&xit",
        "emu.pause": "Pause / Resume",
        "emu.reset": "Soft Reset",
        "emu.timing": "Timing",
        "emu.timing.ntsc": "NTSC (default, 60.1 fps)",
        "emu.timing.pal": "PAL (European, 50.0 fps)",
        "set.language": "Language / 语言",
        "set.mute": "Mute",
        "set.fullscreen": "Fullscreen",
        "set.scale": "Window Scale",
        "lang.zh": "中文",
        "lang.en": "English",
        "scale.1": "1×",
        "scale.2": "2×",
        "scale.3": "3×",
        "scale.4": "4×",
        "set.keys": "Key Mapping...",
        "help.keys": "&Controls...",
        "help.about": "&About FamilyBox...",
        "dlg.keys.title": "Controls",
        "dlg.keys.body": (
            "Arrows / WASD: move\n"
            "Z / J / N / Space: jump (A)\n"
            "M / K: run (B)\n"
            "Enter / Tab: Start\n"
            "Right Shift: Select\n"
            "O: open cartridge\n"
            "P: pause / resume\n"
            "R: soft reset\n"
            "F9: mute    F11: fullscreen\n"
            "ESC: leave fullscreen/maximized"
        ),
        "dlg.about.title": "About FamilyBox",
        "dlg.about.body": (
            "FamilyBox v0.1.0\n"
            "FC/NES emulator (C++20 core + Python UI)\n"
            "Author: ShaoqiLiang\n"
            "\n"
            "Please use your own legally dumped cartridges.\n"
            "For learning and personal use only."
        ),
        "dlg.loadfail.title": "Load Failed",
        "dlg.loadfail.body": "Cannot load this file (unsupported mapper or corrupt):\n{path}",
        "osd.loaded": "Loaded {name}",
        "osd.loadfail": "Load failed (unsupported cartridge): {name}",
        "osd.paused": "Paused",
        "osd.resumed": "Resumed",
        "osd.reset": "Soft reset",
        "osd.muted": "Muted",
        "osd.unmuted": "Unmuted",
        "osd.fullscreen": "Fullscreen",
        "osd.windowed": "Windowed",
        "osd.scale": "Scale {n}x",
        "osd.region": "Timing: {name}",
        "osd.lang": "Language switched to English",
        "osd.no_dialog": "No file dialog on this platform; pass the ROM via command line",
        "region.ntsc": "NTSC",
        "region.pal": "PAL",
        "loader.title": "FamilyBox — load a NES cartridge",
        "loader.hint": "Press O to pick a .nes file, or drop one into the window",
    },
}

DEFAULT_LANG = "zh"


def tr(lang: str, key: str, **fmt: object) -> str:
    """查文案；缺语言回退中文，缺键回退键名。"""
    text = STRINGS.get(lang, STRINGS[DEFAULT_LANG]).get(key)
    if text is None:
        text = STRINGS[DEFAULT_LANG].get(key, key)
    return text.format(**fmt) if fmt else text
