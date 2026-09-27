# FamilyBox

FC/NES (Famicom / Nintendo Entertainment System) emulator — a **C++20 emulation core** behind a frozen, version-handshaked C ABI, driven by a **Python / pygame-ce desktop shell** for Windows.

Goal: run **Super Mario Bros. (1985)** with authentic graphics, audio and controller input, on real console timing (NTSC & PAL).

> [中文说明](README_CN.md)

## Highlights

- Authentic 6502 / PPU / APU emulation in C++20 — NTSC 60.0988 fps, PAL 50.007 fps (audio-clock pacing, not wall-clock ticks)
- Continuous audio: 160 ms blocks through a one-deep queue — **0 lost samples / 0 underruns in a 20 s soak** (acceptance line < 0.1%)
- Native Win32 menu bar with **runtime ROM loading** (no restart); launch with no ROM argument to open the cartridge-loader UI
- Bilingual UI (中文 / English)
- Stable C ABI (`nes_abi_version` handshake, add-only) — shell and core evolve independently
- Quality-gated development: blargg CPU test ROMs, golden frame / palette / audio-pitch baselines, mypy strict + ruff, clang-format

## Features

### Emulation core (C++20 → `familybox_core.dll`)

- **MOS 6502 CPU** — official opcodes, 13 addressing modes, NMI / RESET / IRQ
- **PPU** — background + sprites (8×8 / 8×16), scrolling, sprite-0 hit, VBlank NMI
- **APU** — 2 pulse + 1 triangle + 1 noise channels; NES output mix; ~44.1 kHz PCM
- **Cartridge** — iNES parser, **Mapper 0 (NROM)** + work RAM (`$6000–$7FFF`)
- **Region-aware timing** — APU/timer periods follow the selected region (`--region ntsc|pal`)
- Debug surface over the ABI — PC/register access, PPU status/ctrl/mask, palette & OAM dumps

> **Compatibility**: Mapper 0 (NROM) titles only (Super Mario Bros. and friends).

### Desktop shell (Python 3.14 + pygame-ce)

- Windowed emulator with native Win32 menu bar and in-app ROM loading
- 中英双语界面（built-in localization）
- Zero-copy video path — `nes_video()` shares the frame buffer, no extra copy
- Headless mode for CI-style testing; `[FB]/[PY]` debug logs and per-write C trace mode

## Quick start (Windows)

Requirements: Python 3.14+, [uv](https://docs.astral.sh/uv/), MinGW-w64 `gcc` + CMake.

```bat
git clone https://github.com/ShaoqiLiang/FamilyBox.git
cd FamilyBox
uv sync
scripts\build.bat      :: build the C core -> src\window\familybox_core.dll
run.bat                :: rebuild + launch (default ROM: rom\super-mario-bros-ntsc.nes)
```

More ways to run:

```bat
run.bat release path\to\rom.nes   :: custom ROM (path must not contain ! or ')
run.bat headless                  :: no window (for testing)
run.bat debug                     :: debug logs ([FB]/[PY])
```

PAL cartridges (European ROMs, 312 lines / 50.007 fps / 1.66 MHz CPU):

```bat
set "PYTHONPATH=src" && uv run python -m window.main path\to\rom.nes --region pal
```

Identify a ROM's region by its hash, not its filename.

### Keyboard controls

| Key               | NES button |
|-------------------|------------|
| Arrow keys / WASD | D-pad      |
| Space / Z / N / J | A (jump)   |
| M / K             | B (run)    |
| Enter / Tab       | Start      |

## Project layout

```
src/core/     emulation core in C++20 (nes / cpu / ppu / apu / bus) → familybox_core.dll
src/window/   Python shell: ctypes binding, session (audio pump + pacing),
              pygame frontend, native menu bar, localization, CLI
src/images/   branding assets
tests/        pytest suite — blargg CPU ROMs, golden frame / palette / pitch baselines
scripts/      build.bat (CMake + MinGW), build.sh, packaging helpers
```

### Architecture

```
Python shell (src/window)                C core (src/core)
┌────────────────────────┐    C ABI   ┌─────────────────────────┐
│ pygame frontend (L5)   │ ─────────► │ nes_set_buttons         │
│ session: pacing, audio │            │ nes_run_frame (1 frame) │
│ ctypes binding (L3)    │ ◄───────── │ nes_video (zero-copy)   │
└────────────────────────┘            └─────────────────────────┘
       one frame = RGB 256×240 + PCM @ ~44.1 kHz, paced by the audio clock
```

## Release integrity

Release artifacts are signed with a long-lived RSA release key: `scripts/sign_release.py`
produces a hash manifest (`<artifact>.sha256`) plus an RSA-PSS/SHA-256 signature
(`<artifact>.sha256.sig`) shipped alongside the download. Verify what you downloaded:

```bat
uv run python scripts\verify_release.py <downloaded file-or-dir>
```

The verifier prints the public-key fingerprint, which must match:

```
SHA256:D8AC:78BF:A2EE:4FBA:80A2:66A9:2BE3:CBFE:C8A7:24AC:D96D:68C7:4D93:6FE5:DA2B:DD5C
```

Public key: [`keys/release_public.pem`](keys/release_public.pem) (committed). The private
key never leaves the maintainer's machine. This manifest signature proves origin and
integrity independent of Windows Authenticode — the MSI itself ships unsigned.

## License

Distributed under the [GNU AGPL-3.0](LICENSE).
