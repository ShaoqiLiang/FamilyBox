# FamilyBox

A pure Python FC/NES (Famicom / Nintendo Entertainment System) emulator. Its first-stage goal is to fully run **Super Mario Bros.** (1985), including graphics rendering, audio playback, and controller input.

> [中文说明](README_CN.md)

## Features

- **MOS 6502 CPU** — all 13 addressing modes, 151 official opcodes, NMI/IRQ/RESET interrupts
- **PPU** — background and sprite rendering (8x8 / 8x16), scrolling, sprite 0 hit, VBlank NMI, optional C extension renderer
- **APU** — 2 pulse channels, 1 triangle, 1 noise; NES mixing formula; 44100 Hz output
- **Cartridge** — iNES ROM parser, Mapper 0 (NROM) with PRG/CHR support
- **Input** — standard NES controller emulation via keyboard

## Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) package manager

## Installation

```bash
git clone https://github.com/ShaoqiLiang/FamilyBox.git
cd FamilyBox
uv sync
```

You will also need a `.nes` ROM file (e.g. `super-mario-bros.nes`).

## Usage

```bash
# Run the emulator
uv run python main.py path/to/rom.nes

# Run in headless mode (no window, for testing)
uv run python main.py path/to/rom.nes --headless

# Set log level
uv run python main.py path/to/rom.nes --log-level DEBUG
```

### Keyboard Controls

| Key           | NES Button |
|---------------|------------|
| Z             | A          |
| X             | B          |
| Right Shift   | Select     |
| Enter         | Start      |
| Arrow Keys    | D-Pad      |

## Project Structure

```
FamilyBox/
├── main.py                  # Entry point
├── familybox/
│   ├── main.py              # CLI (argparse)
│   ├── nes.py               # System coordinator
│   ├── types.py             # Shared types & protocols
│   ├── cpu/
│   │   ├── cpu.py           # 6502 CPU core
│   │   ├── opcodes.py       # Opcode table
│   │   └── addressing.py    # Addressing modes
│   ├── ppu/
│   │   ├── ppu.py           # PPU core
│   │   ├── renderer.py      # Pure Python renderer
│   │   └── renderer_fast.py # Optional C renderer (ctypes)
│   ├── apu/
│   │   ├── apu.py           # APU core & mixer
│   │   ├── pulse.py         # Pulse channel
│   │   ├── triangle.py      # Triangle channel
│   │   └── noise.py         # Noise channel
│   ├── bus/
│   │   ├── cpu_bus.py       # CPU address bus
│   │   └── ppu_bus.py       # PPU address bus
│   ├── cartridge/
│   │   ├── rom.py           # iNES parser
│   │   └── mapper.py        # Mapper 0 (NROM)
│   └── input/
│       └── controller.py    # NES controller
└── tests/                   # 376 tests (pytest)
```

## Development

```bash
# Run tests
uv run pytest -v

# Type checking
uv run mypy . --strict

# Lint
uv run ruff check .

# Format
uv run ruff format .
```

## Dependencies

| Package     | Purpose              |
|-------------|----------------------|
| pygame-ce   | Display & audio      |
| pytest      | Testing              |
| mypy        | Type checking        |
| ruff        | Linting & formatting |