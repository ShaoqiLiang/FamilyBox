"""PPU address bus implementation."""

from familybox.types import MapperInterface, Mirroring

#  *
#  * @Author: ShaoqiLiang
#  * @Date: 2026-05-16 22:07:49
#  * @LastEditors: ShaoqiLiang
#  *

class PPUBus:
    """PPU address bus.

    Address space layout:
    $0000-$1FFF  Pattern Table (Mapper)
    $2000-$2FFF  Nametable
    $3000-$3EFF  Nametable mirror
    $3F00-$3FFF  Palette RAM
    """

    def __init__(self, mapper: MapperInterface, mirroring: Mirroring) -> None:
        self._mapper = mapper
        self._mirroring = mirroring
        self._nametable: bytearray = bytearray(2048)  # 2KB VRAM
        self._palette: bytearray = bytearray(32)  # palette RAM

    def read(self, addr: int) -> int:
        """Read a byte from the PPU address space.

        Args:
            addr: 14-bit PPU address ($0000-$3FFF).

        Returns:
            8-bit data value.
        """
        addr &= 0x3FFF
        if addr < 0x2000:
            return self._mapper.ppu_read(addr)
        elif addr < 0x3F00:
            return self._nametable[self._mirror_nametable(addr)]
        else:
            return self._palette[self._mirror_palette(addr)]

    def write(self, addr: int, value: int) -> None:
        """Write a byte to the PPU address space.

        Args:
            addr: 14-bit PPU address ($0000-$3FFF).
            value: 8-bit data value.
        """
        addr &= 0x3FFF
        value &= 0xFF
        if addr < 0x2000:
            self._mapper.ppu_write(addr, value)
        elif addr < 0x3F00:
            self._nametable[self._mirror_nametable(addr)] = value
        else:
            self._palette[self._mirror_palette(addr)] = value

    def _mirror_nametable(self, addr: int) -> int:
        """Map a nametable address to VRAM index based on mirroring mode.

        Args:
            addr: PPU address in the nametable range ($2000-$3EFF).

        Returns:
            Index into the 2KB nametable VRAM.
        """
        addr = (addr - 0x2000) % 0x1000
        if self._mirroring == Mirroring.VERTICAL:
            # $2000=$2400 (NT A/B), $2800=$2C00 (NT C/D)
            return (addr % 0x400) | ((addr // 0x800) * 0x400)
        elif self._mirroring == Mirroring.HORIZONTAL:
            # $2000=$2800 (NT A/C), $2400=$2C00 (NT B/D)
            table = addr // 0x400
            offset = addr % 0x400
            return (table // 2) * 0x400 + offset
        return addr

    def _mirror_palette(self, addr: int) -> int:
        """Map a palette address to palette RAM index.

        Handles the transparency mirror: addresses where index % 4 == 0
        all map to the universal background colour (index 0).

        Args:
            addr: PPU address in the palette range ($3F00-$3FFF).

        Returns:
            Index into the 32-byte palette RAM.
        """
        addr = (addr - 0x3F00) % 0x20
        if addr % 4 == 0:
            addr = 0
        return addr
