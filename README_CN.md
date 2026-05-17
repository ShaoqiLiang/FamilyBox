# FamilyBox

一个纯 Python 实现的 FC/NES（红白机 / Nintendo Entertainment System）模拟器。第一阶段目标是完整运行 **《超级马力欧兄弟》**（1985），包括图形渲染、音频播放和手柄输入。

> [English](README.md)

## 功能特性

- **MOS 6502 CPU** — 全部 13 种寻址模式、151 条官方指令、NMI/IRQ/RESET 中断
- **PPU（图像处理单元）** — 背景和精灵渲染（8x8 / 8x16）、滚动、精灵 0 碰撞检测、VBlank NMI，可选 C 扩展渲染器
- **APU（音频处理单元）** — 2 个脉冲通道、1 个三角波通道、1 个噪声通道；NES 混音公式；44100 Hz 输出
- **卡带** — iNES ROM 解析器，Mapper 0（NROM）支持 PRG/CHR
- **输入** — 标准 NES 手柄模拟，键盘映射

## 环境要求

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) 包管理器

## 安装

```bash
git clone https://github.com/ShaoqiLiang/FamilyBox.git
cd FamilyBox
uv sync
```

你还需要一个 `.nes` ROM 文件（如 `super-mario-bros.nes`）。

## 使用方法

```bash
# 运行模拟器
uv run python main.py path/to/rom.nes

# 无头模式运行（无窗口，用于测试）
uv run python main.py path/to/rom.nes --headless

# 设置日志级别
uv run python main.py path/to/rom.nes --log-level DEBUG
```

### 键盘映射

| 按键         | NES 按钮 |
|-------------|----------|
| Z           | A        |
| X           | B        |
| Right Shift | Select   |
| Enter       | Start    |
| 方向键       | 十字键    |

## 项目结构

```
FamilyBox/
├── main.py                  # 入口文件
├── familybox/
│   ├── main.py              # 命令行解析（argparse）
│   ├── nes.py               # 系统协调器
│   ├── types.py             # 共享类型与协议定义
│   ├── cpu/
│   │   ├── cpu.py           # 6502 CPU 核心
│   │   ├── opcodes.py       # 指令表
│   │   └── addressing.py    # 寻址模式
│   ├── ppu/
│   │   ├── ppu.py           # PPU 核心
│   │   ├── renderer.py      # 纯 Python 渲染器
│   │   └── renderer_fast.py # 可选 C 渲染器（ctypes）
│   ├── apu/
│   │   ├── apu.py           # APU 核心与混音器
│   │   ├── pulse.py         # 脉冲通道
│   │   ├── triangle.py      # 三角波通道
│   │   └── noise.py         # 噪声通道
│   ├── bus/
│   │   ├── cpu_bus.py       # CPU 地址总线
│   │   └── ppu_bus.py       # PPU 地址总线
│   ├── cartridge/
│   │   ├── rom.py           # iNES 解析器
│   │   └── mapper.py        # Mapper 0（NROM）
│   └── input/
│       └── controller.py    # NES 手柄
└── tests/                   # 376 个测试（pytest）
```

## 开发

```bash
# 运行测试
uv run pytest -v

# 类型检查
uv run mypy . --strict

# 代码检查
uv run ruff check .

# 代码格式化
uv run ruff format .
```

## 依赖

| 包          | 用途           |
|-------------|---------------|
| pygame-ce   | 显示与音频      |
| pytest      | 测试框架        |
| mypy        | 类型检查        |
| ruff        | 代码检查与格式化  |