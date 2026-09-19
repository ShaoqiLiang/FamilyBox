# FamilyBox

FC/NES（红白机）模拟器 —— **C++20 仿真核心**通过冻结、带版本握手的 C ABI 对外暴露，由 **Python / pygame-ce 桌面外壳**驱动（Windows）。

目标：在真实的主机时序（NTSC 和 PAL）下完整运行 **《超级马力欧兄弟》**（1985），含图形、音频和手柄输入。

> [English](README.md)

## 亮点

- C++20 实现的真实 6502 / PPU / APU 仿真 —— NTSC 60.0988 fps、PAL 50.007 fps（音频时钟节拍，非墙钟 tick）
- 连续音频：160 ms 分块 × 单槽队列 —— 20 秒拷机**丢样 0、欠载 0**（验收线 < 0.1%）
- 原生 Win32 菜单栏，支持**运行时载入 ROM**（无需重启）；不带 ROM 参数启动则打开卡带加载界面
- 中英双语界面
- 稳定 C ABI（`nes_abi_version` 握手、只增不改）—— 外壳与核心独立演进
- 质量门禁开发：blargg CPU 测试 ROM、金帧 / 调色板 / 音准基线、mypy 严格模式 + ruff、clang-format

## 功能特性

### 仿真核心（C++20 → `familybox_core.dll`）

- **MOS 6502 CPU** — 官方指令集、13 种寻址模式、NMI / RESET / IRQ
- **PPU** — 背景 + 精灵（8×8 / 8×16）、滚动、精灵 0 碰撞、VBlank NMI
- **APU** — 2 脉冲 + 1 三角 + 1 噪声声道；NES 混音公式；约 44.1 kHz PCM
- **卡带** — iNES 解析，**Mapper 0（NROM）** + 工作 RAM（`$6000–$7FFF`）
- **区域感知时序** — APU/定时器周期随所选区域变化（`--region ntsc|pal`）
- 经 ABI 暴露调试面 — PC/寄存器访问、PPU 状态/控制/掩码、调色板与 OAM 转储

> **兼容性说明**：目前仅支持 Mapper 0（NROM）游戏（《超级马力欧兄弟》等）。

### 桌面外壳（Python 3.14 + pygame-ce）

- 窗口化模拟器：原生 Win32 菜单栏、应用内载入 ROM
- 中英双语界面（内置本地化）
- 零拷贝视频路径 —— `nes_video()` 共享帧缓冲，无额外拷贝
- 无头模式供测试；`[FB]/[PY]` 调试日志与逐写入 C 跟踪模式

## 快速开始（Windows）

环境要求：Python 3.14+、[uv](https://docs.astral.sh/uv/)、MinGW-w64 `gcc` + CMake。

```bat
git clone https://github.com/ShaoqiLiang/FamilyBox.git
cd FamilyBox
uv sync
scripts\build.bat      :: 编译 C 核心 -> src\window\familybox_core.dll
run.bat                :: 重新编译并启动（默认 ROM：rom\super-mario-bros-ntsc.nes）
```

其他运行方式：

```bat
run.bat release path\to\rom.nes   :: 自定义 ROM（路径不能含 ! 或 '）
run.bat headless                  :: 无窗口（测试用）
run.bat debug                     :: 调试日志（[FB]/[PY]）
```

PAL 卡带（欧版 ROM，312 行 / 50.007 fps / 1.66 MHz CPU）：

```bat
set "PYTHONPATH=src" && uv run python -m window.main path\to\rom.nes --region pal
```

判断 ROM 区域请看哈希值，不要看文件名。

### 键盘映射

| 按键              | NES 按钮   |
|-------------------|------------|
| 方向键 / WASD     | 十字键     |
| Space / Z / N / J | A（跳跃）  |
| M / K             | B（奔跑）  |
| Enter / Tab       | Start      |

## 项目结构

```
src/core/     C++20 仿真核心（nes / cpu / ppu / apu / bus）→ familybox_core.dll
src/window/   Python 外壳：ctypes 绑定、会话层（音频泵 + 节拍）、
              pygame 前端、原生菜单栏、本地化、CLI
src/images/   品牌素材
tests/        pytest 测试套件 —— blargg CPU ROM、金帧 / 调色板 / 音准基线
scripts/      build.bat（CMake + MinGW）、build.sh、打包辅助
```

### 架构

```
Python 外壳 (src/window)                C 核心 (src/core)
┌────────────────────────┐    C ABI   ┌─────────────────────────┐
│ pygame 前端 (L5)       │ ─────────► │ nes_set_buttons         │
│ 会话层：节拍、音频     │            │ nes_run_frame（跑一帧） │
│ ctypes 绑定 (L3)       │ ◄───────── │ nes_video（零拷贝）     │
└────────────────────────┘            └─────────────────────────┘
       一帧 = RGB 256×240 + PCM @ ~44.1 kHz，由音频时钟节拍
```

## 许可证

基于 [GNU AGPL-3.0](LICENSE) 分发。
