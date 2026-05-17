"""MOS 6502 addressing modes implementation.

Each addressing mode returns the effective address (int) for the operand.
"""

#  *
#  * @Author: ShaoqiLiang
#  * @Date: 2026-05-16 22:07:49
#  * @LastEditors: ShaoqiLiang
#  *

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from familybox.cpu.cpu import CPU


class AddressingModes:
    """Collection of 6502 addressing mode methods.

    These are intended to be bound to a CPU instance.
    """

    # T-CPU-07: Implied and Accumulator
    @staticmethod
    def implied(cpu: CPU) -> int:
        """Implied addressing — no operand."""
        return 0

    @staticmethod
    def accumulator(cpu: CPU) -> int:
        """Accumulator addressing — operand is the accumulator itself.

        Returns -1 as a sentinel so instruction functions can distinguish
        accumulator mode from a valid memory address 0x0000.
        """
        return -1

    # T-CPU-08: Immediate
    @staticmethod
    def immediate(cpu: CPU) -> int:
        """Immediate addressing — operand is the next byte at PC."""
        addr = cpu._regs.pc
        cpu._regs.pc = (cpu._regs.pc + 1) & 0xFFFF
        return addr

    # T-CPU-09: Zero Page, Zero Page X, Zero Page Y
    @staticmethod
    def zero_page(cpu: CPU) -> int:
        """Zero Page addressing — operand address in first 256 bytes."""
        addr = cpu._bus.read(cpu._regs.pc)
        cpu._regs.pc = (cpu._regs.pc + 1) & 0xFFFF
        return addr & 0xFF

    @staticmethod
    def zero_page_x(cpu: CPU) -> int:
        """Zero Page,X addressing — (zero page addr + X) & 0xFF."""
        base = cpu._bus.read(cpu._regs.pc)
        cpu._regs.pc = (cpu._regs.pc + 1) & 0xFFFF
        return (base + cpu._regs.x) & 0xFF

    @staticmethod
    def zero_page_y(cpu: CPU) -> int:
        """Zero Page,Y addressing — (zero page addr + Y) & 0xFF."""
        base = cpu._bus.read(cpu._regs.pc)
        cpu._regs.pc = (cpu._regs.pc + 1) & 0xFFFF
        return (base + cpu._regs.y) & 0xFF

    # T-CPU-10: Absolute, Absolute X, Absolute Y
    @staticmethod
    def absolute(cpu: CPU) -> int:
        """Absolute addressing — 16-bit address from next two bytes."""
        lo = cpu._bus.read(cpu._regs.pc)
        hi = cpu._bus.read((cpu._regs.pc + 1) & 0xFFFF)
        cpu._regs.pc = (cpu._regs.pc + 2) & 0xFFFF
        return (hi << 8) | lo

    @staticmethod
    def absolute_x(cpu: CPU) -> int:
        """Absolute,X addressing — 16-bit address + X.  Returns (addr, page_crossed)."""
        lo = cpu._bus.read(cpu._regs.pc)
        hi = cpu._bus.read((cpu._regs.pc + 1) & 0xFFFF)
        cpu._regs.pc = (cpu._regs.pc + 2) & 0xFFFF
        base = (hi << 8) | lo
        addr = (base + cpu._regs.x) & 0xFFFF
        # Store page-cross info on CPU for cycle adjustment
        cpu._page_crossed = (base & 0xFF00) != (addr & 0xFF00)
        return addr

    @staticmethod
    def absolute_y(cpu: CPU) -> int:
        """Absolute,Y addressing — 16-bit address + Y.  Returns addr, sets page_crossed."""
        lo = cpu._bus.read(cpu._regs.pc)
        hi = cpu._bus.read((cpu._regs.pc + 1) & 0xFFFF)
        cpu._regs.pc = (cpu._regs.pc + 2) & 0xFFFF
        base = (hi << 8) | lo
        addr = (base + cpu._regs.y) & 0xFFFF
        cpu._page_crossed = (base & 0xFF00) != (addr & 0xFF00)
        return addr

    # T-CPU-11: Indirect (with JMP page-crossing bug)
    @staticmethod
    def indirect(cpu: CPU) -> int:
        """Indirect addressing — read 16-bit ptr, then read 16-bit value at ptr.

        Implements the famous 6502 page-crossing bug: if the low byte of the
        pointer is 0xFF the high byte is fetched from the same page rather than
        the next page.
        """
        lo = cpu._bus.read(cpu._regs.pc)
        hi = cpu._bus.read((cpu._regs.pc + 1) & 0xFFFF)
        cpu._regs.pc = (cpu._regs.pc + 2) & 0xFFFF
        ptr = (hi << 8) | lo

        # Page-crossing bug
        if lo == 0xFF:
            addr_lo = cpu._bus.read(ptr)
            addr_hi = cpu._bus.read(ptr & 0xFF00)  # same page
        else:
            addr_lo = cpu._bus.read(ptr)
            addr_hi = cpu._bus.read(ptr + 1)

        return (addr_hi << 8) | addr_lo

    # T-CPU-12: Indexed Indirect (X,Indirect) and Indirect Indexed (Indirect,Y)
    @staticmethod
    def indexed_indirect(cpu: CPU) -> int:
        """Indexed Indirect (X,Indirect) addressing.

        Read zero page address, add X (wrapping in zero page), read 16-bit
        value at that address.
        """
        base = cpu._bus.read(cpu._regs.pc)
        cpu._regs.pc = (cpu._regs.pc + 1) & 0xFFFF
        ptr = (base + cpu._regs.x) & 0xFF
        lo = cpu._bus.read(ptr)
        hi = cpu._bus.read((ptr + 1) & 0xFF)
        return (hi << 8) | lo

    @staticmethod
    def indirect_indexed(cpu: CPU) -> int:
        """Indirect Indexed (Indirect,Y) addressing.

        Read zero page address, read 16-bit value there, add Y.  Sets
        page_crossed flag.
        """
        zp = cpu._bus.read(cpu._regs.pc)
        cpu._regs.pc = (cpu._regs.pc + 1) & 0xFFFF
        lo = cpu._bus.read(zp & 0xFF)
        hi = cpu._bus.read((zp + 1) & 0xFF)
        base = (hi << 8) | lo
        addr = (base + cpu._regs.y) & 0xFFFF
        cpu._page_crossed = (base & 0xFF00) != (addr & 0xFF00)
        return addr

    # T-CPU-13: Relative (branch offset)
    @staticmethod
    def relative(cpu: CPU) -> int:
        """Relative addressing — signed 8-bit offset from current PC."""
        offset = cpu._bus.read(cpu._regs.pc)
        cpu._regs.pc = (cpu._regs.pc + 1) & 0xFFFF
        if offset & 0x80:
            offset -= 0x100
        return (cpu._regs.pc + offset) & 0xFFFF
