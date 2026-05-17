"""CPU address bus implementation."""

#  *
#  * @Author: ShaoqiLiang
#  * @Date: 2026-05-16 22:07:49
#  * @LastEditors: ShaoqiLiang
#  *

from familybox.types import (
    APUInterface,
    ControllerInterface,
    MapperInterface,
    PPUBusInterface,
)


class CPUBus:
    """CPU address bus.

    Address space layout:
    $0000-$07FF  2KB internal RAM
    $0800-$1FFF  RAM mirrors
    $2000-$2007  PPU registers
    $2008-$3FFF  PPU register mirrors
    $4000-$4017  APU and I/O registers
    $4020-$FFFF  Mapper region
    """

    def __init__(
        self,
        ppu: PPUBusInterface,
        apu: APUInterface,
        mapper: MapperInterface,
        controller: ControllerInterface,
    ) -> None:
        self._ram: bytearray = bytearray(2048)
        self._ppu = ppu
        self._apu = apu
        self._mapper = mapper
        self._controller = controller

    def read(self, addr: int) -> int:
        """Read a byte from the CPU address space."""
        addr &= 0xFFFF
        # Fast path: ROM reads (92% of all reads)
        if addr >= 0x8000:
            return self._mapper.cpu_read(addr)
        if addr < 0x2000:
            return self._ram[addr & 0x7FF]
        if addr < 0x4000:
            return self._ppu.read_register(0x2000 + (addr & 0x07))
        if addr == 0x4016:
            return self._controller.read()
        if addr == 0x4017:
            return 0
        if addr < 0x4020:
            return 0
        return self._mapper.cpu_read(addr)

    def write(self, addr: int, value: int) -> None:
        """Write a byte to the CPU address space.

        Args:
            addr: 16-bit CPU address.
            value: 8-bit data value.
        """
        addr &= 0xFFFF
        value &= 0xFF
        if addr < 0x2000:
            self._ram[addr & 0x7FF] = value
        elif addr < 0x4000:
            self._ppu.write_register(0x2000 + (addr & 0x07), value)
        elif addr == 0x4014:
            self._oam_dma(value)
        elif addr == 0x4016:
            self._controller.write(value)
        elif addr < 0x4018:
            self._apu.write_register(addr, value)
        else:
            self._mapper.cpu_write(addr, value)

    def _oam_dma(self, page: int) -> None:
        """Execute OAM DMA transfer.

        Copies 256 bytes from the specified page into PPU OAMDATA register.

        Args:
            page: High byte of the source address ($00-$FF).
        """
        base_addr = page << 8
        for i in range(256):
            value = self.read(base_addr + i)
            self._ppu.write_register(0x2004, value)
