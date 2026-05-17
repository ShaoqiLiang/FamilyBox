"""Shared type definitions for all modules."""

#  *
#  * @Author: ShaoqiLiang
#  * @Date: 2026-05-16 22:07:49
#  * @LastEditors: ShaoqiLiang
#  *

from dataclasses import dataclass
from enum import IntEnum
from typing import Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# T-TYPES-01: Mirroring modes
# ---------------------------------------------------------------------------


class Mirroring(IntEnum):
    """iNES mirroring modes."""

    HORIZONTAL = 0
    VERTICAL = 1
    FOUR_SCREEN = 8


# ---------------------------------------------------------------------------
# T-TYPES-02: iNES header
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class iNESHeader:
    """Parsed iNES file header (16 bytes)."""

    prg_rom_size: int
    chr_rom_size: int
    mapper_number: int
    mirroring: Mirroring
    has_battery_ram: bool
    has_trainer: bool


# ---------------------------------------------------------------------------
# T-TYPES-03: NES controller buttons
# ---------------------------------------------------------------------------


class NESButton(IntEnum):
    """NES controller button indices (bit positions in the shift register)."""

    A = 0
    B = 1
    SELECT = 2
    START = 3
    UP = 4
    DOWN = 5
    LEFT = 6
    RIGHT = 7


# ---------------------------------------------------------------------------
# T-TYPES-04: NES colour palette
# ---------------------------------------------------------------------------

NES_PALETTE: list[tuple[int, int, int]] = [
    (84, 84, 84),
    (0, 30, 116),
    (8, 16, 144),
    (48, 0, 136),
    (68, 0, 100),
    (92, 0, 48),
    (84, 4, 0),
    (60, 24, 0),
    (32, 42, 0),
    (8, 58, 0),
    (0, 64, 0),
    (0, 60, 0),
    (0, 50, 60),
    (0, 0, 0),
    (0, 0, 0),
    (0, 0, 0),
    (152, 150, 152),
    (8, 76, 196),
    (48, 50, 236),
    (92, 30, 228),
    (136, 20, 176),
    (160, 20, 100),
    (152, 34, 32),
    (120, 60, 0),
    (84, 90, 0),
    (40, 114, 0),
    (8, 124, 0),
    (0, 118, 40),
    (0, 102, 120),
    (0, 0, 0),
    (0, 0, 0),
    (0, 0, 0),
    (236, 238, 236),
    (76, 154, 236),
    (120, 124, 236),
    (176, 98, 236),
    (228, 84, 236),
    (236, 88, 180),
    (236, 106, 100),
    (212, 136, 32),
    (160, 170, 0),
    (116, 196, 0),
    (76, 208, 32),
    (56, 204, 108),
    (56, 180, 204),
    (60, 60, 60),
    (0, 0, 0),
    (0, 0, 0),
    (236, 238, 236),
    (168, 204, 236),
    (188, 188, 236),
    (212, 178, 236),
    (236, 174, 236),
    (236, 174, 212),
    (236, 180, 176),
    (228, 196, 144),
    (204, 210, 120),
    (180, 222, 120),
    (168, 226, 144),
    (152, 226, 180),
    (160, 214, 228),
    (160, 162, 160),
    (0, 0, 0),
    (0, 0, 0),
]


# ---------------------------------------------------------------------------
# T-TYPES-05: Protocol interfaces
# ---------------------------------------------------------------------------


@runtime_checkable
class CPUBusInterface(Protocol):
    """CPU address bus interface."""

    def read(self, addr: int) -> int: ...
    def write(self, addr: int, value: int) -> None: ...


@runtime_checkable
class PPUBusInterface(Protocol):
    """PPU address bus interface."""

    def read(self, addr: int) -> int: ...
    def write(self, addr: int, value: int) -> None: ...
    def read_register(self, addr: int) -> int: ...
    def write_register(self, addr: int, value: int) -> None: ...


@runtime_checkable
class MapperInterface(Protocol):
    """Cartridge mapper interface."""

    def cpu_read(self, addr: int) -> int: ...
    def cpu_write(self, addr: int, value: int) -> None: ...
    def ppu_read(self, addr: int) -> int: ...
    def ppu_write(self, addr: int, value: int) -> None: ...


@runtime_checkable
class ControllerInterface(Protocol):
    """NES controller interface."""

    def read(self) -> int: ...
    def write(self, value: int) -> None: ...
    def set_button(self, button: NESButton, pressed: bool) -> None: ...


@runtime_checkable
class APUInterface(Protocol):
    """APU interface."""

    def write_register(self, addr: int, value: int) -> None: ...
    def tick(self) -> float: ...
    def get_sample_buffer(self) -> list[float]: ...
    def reset(self) -> None: ...
