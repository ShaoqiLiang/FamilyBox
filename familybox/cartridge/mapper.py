"""Mapper implementations for NES cartridges."""

from familybox.types import Mirroring

#  *
#  * @Author: ShaoqiLiang
#  * @Date: 2026-05-16 22:07:49
#  * @LastEditors: ShaoqiLiang
#  *

class Mapper0:
    """Mapper 0 (NROM) implementation.

    The simplest mapper with direct mapping:
    - 16KB or 32KB PRG ROM -> CPU $8000-$FFFF
    - 8KB CHR ROM -> PPU $0000-$1FFF
    """

    def __init__(self, prg_rom: bytes, chr_rom: bytes, mirroring: Mirroring) -> None:
        self._prg_rom: bytes = prg_rom
        self._prg_rom_len: int = len(prg_rom)
        self._chr_rom: bytearray = bytearray(chr_rom)  # writable for CHR RAM
        self._mirroring: Mirroring = mirroring

    def cpu_read(self, addr: int) -> int:
        """Read data from CPU address space.

        Args:
            addr: 16-bit CPU address ($8000-$FFFF).

        Returns:
            8-bit data value.

        Raises:
            ValueError: If address is outside the valid range.
        """
        if 0x8000 <= addr <= 0xFFFF:
            index = (addr - 0x8000) % self._prg_rom_len
            return self._prg_rom[index]
        return 0  # open bus

    def cpu_write(self, addr: int, value: int) -> None:
        """Write data to CPU address space (no-op for NROM).

        Args:
            addr: 16-bit CPU address.
            value: 8-bit data value.
        """
        pass  # NROM has no writable CPU address space

    def ppu_read(self, addr: int) -> int:
        """Read data from PPU address space.

        Args:
            addr: 13-bit PPU address ($0000-$1FFF).

        Returns:
            8-bit data value.

        Raises:
            ValueError: If address is outside the valid range.
        """
        if 0x0000 <= addr <= 0x1FFF:
            return self._chr_rom[addr]
        return 0  # open bus

    def ppu_write(self, addr: int, value: int) -> None:
        """Write data to PPU address space (CHR RAM support).

        Args:
            addr: 13-bit PPU address ($0000-$1FFF).
            value: 8-bit data value.
        """
        if 0x0000 <= addr <= 0x1FFF:
            self._chr_rom[addr] = value
