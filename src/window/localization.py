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
        "help.verify": "完整性验证...(&V)",
        "help.update": "检查更新...(&U)",
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
        "dlg.ok": "确定",
        "dlg.copy": "复制",
        "dlg.cancel": "取消",
        "dlg.about.body": (
            "FamilyBox v{ver}\n"
            "FC/NES 模拟器（C++20 核心 + Python 界面）\n"
            "作者：ShaoqiLiang\n"
            "GitHub：https://github.com/ShaoqiLiang/FamilyBox\n"
            "构建日期：{build}\n"
            "构建 Commit：{commit}\n"
            "\n"
            "请使用自备的合法卡带转储文件。"
        ),
        "build.commit.dev": "开发模式（源码）",
        "dlg.verify.title": "完整性验证",
        "dlg.verify.progress": "正在验证完整性…",
        "dlg.verify.ok": (
            "验证通过：{n} 个文件与构建清单一致。\n"
            "签名密钥指纹：\n{fp}\n"
            "\n"
            "请与 README 公布的指纹核对一致。"
        ),
        "dlg.verify.fail": (
            "验证未通过（{n} 处）：\n{problems}\n"
            "\n"
            "签名密钥指纹：{fp}\n"
            "若非你本人操作，请从官方 GitHub 重新下载。"
        ),
        "dlg.verify.unsigned": "当前为开发/未打包版本，无嵌入完整性清单。",
        "dlg.update.title": "检查更新",
        "dlg.update.latest": "已是最新版本（{cur}）。",
        "dlg.update.found": "发现新版本：{latest}（当前 {cur}）。\n是否打开发布页下载？",
        "dlg.update.error": "检查更新失败：\n{err}",
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
        "help.verify": "&Verify Integrity...",
        "help.update": "&Check for Updates...",
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
        "dlg.ok": "OK",
        "dlg.copy": "Copy",
        "dlg.cancel": "Cancel",
        "dlg.about.body": (
            "FamilyBox v{ver}\n"
            "FC/NES emulator (C++20 core + Python UI)\n"
            "Author: ShaoqiLiang\n"
            "GitHub: https://github.com/ShaoqiLiang/FamilyBox\n"
            "Build date: {build}\n"
            "Build commit: {commit}\n"
            "\n"
            "Please use your own legally dumped cartridges.\n"
            "For learning and personal use only."
        ),
        "build.commit.dev": "development (source)",
        "dlg.verify.title": "Integrity Verification",
        "dlg.verify.progress": "Verifying integrity…",
        "dlg.verify.ok": (
            "Verification passed: {n} files match the build manifest.\n"
            "Signing key fingerprint:\n{fp}\n"
            "\n"
            "Please compare it with the fingerprint published in the README."
        ),
        "dlg.verify.fail": (
            "Verification FAILED ({n} issue(s)):\n{problems}\n"
            "\n"
            "Signing key fingerprint: {fp}\n"
            "If this wasn't you, re-download from the official GitHub releases."
        ),
        "dlg.verify.unsigned": "Development/unpackaged build — no embedded integrity manifest.",
        "dlg.update.title": "Check for Updates",
        "dlg.update.latest": "Already up to date ({cur}).",
        "dlg.update.found": "New version available: {latest} (current {cur}).\nOpen the releases page to download?",
        "dlg.update.error": "Update check failed:\n{err}",
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
