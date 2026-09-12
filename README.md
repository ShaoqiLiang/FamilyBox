# FamilyBox

FC/NES (Famicom / Nintendo Entertainment System) emulator. First-stage goal: run **Super Mario Bros.** (1985) with graphics, audio, and controller input.

The emulation **core is written in C** (CPU / PPU / APU / bus / mapper). Python + pygame is only a thin front-end (window, input, present, audio queue).

> [中文说明](README_CN.md)

## Features

- **MOS 6502 CPU** — 13 addressing modes, official opcodes, NMI/RESET
- **PPU** — background + sprites (8x8 / 8x16), scrolling, sprite 0 hit, VBlank NMI
- **APU** — 2 pulse, 1 triangle, 1 noise; NES mix formula; ~44100 Hz samples
- **Cartridge** — iNES parser, Mapper 0 (NROM)
- **Input** — NES controller via keyboard

## Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)
- A C compiler (`gcc` / MinGW) to build the core library

## Build the C core

```bash
# Windows (MinGW + CMake)
familybox\build.bat

# Linux / macOS
chmod +x familybox/build.sh
./familybox/build.sh
```

Or manually:

```bash
cmake -S . -B build -G "MinGW Makefiles" -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=gcc
cmake --build build
```

This produces `familybox/familybox_core.dll` (Windows) or `.so` / `.dylib`.
See [doc/build.md](doc/build.md) for CMake target layout.

## Installation

```bash
git clone https://github.com/ShaoqiLiang/FamilyBox.git
cd FamilyBox
uv sync
familybox\build.bat   # or ./familybox/build.sh
```

You will also need a `.nes` ROM file (e.g. `super-mario-bros.nes`).

## Usage

```bash
# Run the emulator
uv run python main.py path/to/rom.nes

# Headless (no window)
uv run python main.py path/to/rom.nes --headless

# Log level
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
│   ├── main.py              # CLI
│   ├── nes.py               # pygame shell
│   ├── core_api.py          # ctypes binding
│   ├── familybox_core.dll   # built library
│   ├── build.bat / build.sh
│   ├── include/
│   │   ├── familybox.h      # Public C API
│   │   └── nes_internal.h   # Internal types
│   ├── nes.c                # Frame orchestration + API
│   ├── cpu/cpu.c            # 6502 CPU
│   ├── ppu/ppu.c            # PPU + renderer
│   ├── apu/apu.c            # APU + sample output
│   └── bus/bus.c            # CPU/PPU bus, OAM DMA
├── tests/
├── rom/
└── doc/
```

## Architecture

```
Python (pygame)                 C core (libfamilybox)
┌────────────────────┐         ┌─────────────────────────┐
│ window / events    │ ──────► │ nes_set_buttons         │
│ nes_run_frame()    │ ◄────── │ CPU+PPU+APU one frame   │
│ blit + audio queue │         │ rgb 256×240×3 + PCM     │
└────────────────────┘         └─────────────────────────┘
```

## License

See [LICENSE](LICENSE).
