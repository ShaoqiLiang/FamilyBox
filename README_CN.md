# FamilyBox

FC/NES（红白机）模拟器。第一阶段目标：完整运行 **《超级马力欧兄弟》**（1985），含图形、音频和手柄输入。

仿真**核心用 C 实现**（CPU / PPU / APU / 总线 / Mapper）。Python + pygame 只做界面：窗口、输入、呈现、音频排队。

> [English](README.md)

## 功能特性

- **MOS 6502 CPU** — 13 种寻址模式、官方指令、NMI/RESET
- **PPU** — 背景 + 精灵（8x8 / 8x16）、滚动、精灵 0 碰撞、VBlank NMI
- **APU** — 2 脉冲 + 1 三角 + 1 噪声；NES 混音公式；约 44100 Hz 采样
- **卡带** — iNES 解析，Mapper 0（NROM）
- **输入** — 键盘映射 NES 手柄

## 环境要求

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)
- C 编译器（gcc / MinGW）

## 编译 C 核心

```bash
# Windows (MinGW)
familybox\build.bat

# Linux / macOS
chmod +x familybox/build.sh
./familybox/build.sh
```

生成 `familybox/familybox_core.dll`（Windows）或 `.so` / `.dylib`。

## 安装

```bash
git clone https://github.com/ShaoqiLiang/FamilyBox.git
cd FamilyBox
uv sync
familybox\build.bat   # 或 ./familybox/build.sh
```

你还需要一个 `.nes` ROM 文件（如 `super-mario-bros.nes`）。

## 使用方法

```bash
# 运行模拟器
uv run python main.py path/to/rom.nes

# 无头模式
uv run python main.py path/to/rom.nes --headless

# 日志级别
uv run python main.py path/to/rom.nes --log-level DEBUG
```

### 键盘映射

| 按键         | NES 按钮 |
|--------------|----------|
| Z            | A        |
| X            | B        |
| 右 Shift     | Select   |
| 回车         | Start    |
| 方向键       | 十字键   |

## 项目结构

```
FamilyBox/
├── main.py                  # 入口
├── familybox/
│   ├── main.py              # CLI
│   ├── nes.py               # pygame 壳
│   ├── core_api.py          # ctypes 绑定
│   ├── familybox_core.dll
│   ├── build.bat / build.sh
│   ├── include/
│   │   ├── familybox.h      # 对外 C API
│   │   └── nes_internal.h
│   ├── nes.c
│   ├── cpu/cpu.c
│   ├── ppu/ppu.c
│   ├── apu/apu.c
│   └── bus/bus.c
├── tests/
├── rom/
└── doc/
```

## 架构

```
Python (pygame)                 C 核心
┌────────────────────┐         ┌─────────────────────────┐
│ 窗口 / 事件        │ ──────► │ nes_set_buttons         │
│ nes_run_frame()    │ ◄────── │ CPU+PPU+APU 跑完整一帧  │
│ blit + 音频 queue  │         │ RGB + PCM               │
└────────────────────┘         └─────────────────────────┘
```

## 许可证

见 [LICENSE](LICENSE)。
