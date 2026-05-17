"""MOS 6502 CPU core implementation.

Provides registers, interrupt handling, stack operations, and the main
execution loop for the NES CPU.
"""

#  *
#  * @Author: ShaoqiLiang
#  * @Date: 2026-05-16 22:07:49
#  * @LastEditors: ShaoqiLiang
#  *

from dataclasses import dataclass
from enum import IntEnum
from typing import Callable

from familybox.types import CPUBusInterface


# ---------------------------------------------------------------------------
# T-CPU-01: Registers and flag constants
# ---------------------------------------------------------------------------

C_FLAG: int = 0x01  # Carry
Z_FLAG: int = 0x02  # Zero
I_FLAG: int = 0x04  # Interrupt disable
D_FLAG: int = 0x08  # Decimal mode (unused on NES)
B_FLAG: int = 0x10  # Break
V_FLAG: int = 0x40  # Overflow
N_FLAG: int = 0x80  # Negative


@dataclass(slots=True)
class Registers:
    """6502 register set."""

    a: int = 0
    x: int = 0
    y: int = 0
    sp: int = 0xFD
    pc: int = 0
    p: int = 0x24


# ---------------------------------------------------------------------------
# T-CPU-02: Interrupt type
# ---------------------------------------------------------------------------


class InterruptType(IntEnum):
    """Hardware interrupt types."""

    NMI = 0
    IRQ = 1
    RESET = 2


# ---------------------------------------------------------------------------
# Instruction / addressing-mode callable aliases
# ---------------------------------------------------------------------------
# Instruction: takes effective addr, returns cycle count.
# Addressing:  takes no args, returns effective addr.

InstructionFunc = Callable[[int], int]
AddressingFunc = Callable[[], int]


# ---------------------------------------------------------------------------
# T-CPU-04 / T-CPU-05: CPU class
# ---------------------------------------------------------------------------


class CPU:
    """MOS 6502 CPU emulator."""

    def __init__(self, bus: CPUBusInterface) -> None:
        self._bus: CPUBusInterface = bus
        self._regs: Registers = Registers()
        self._cycles: int = 0
        self._interrupt: int | None = None  # InterruptType value or None
        self._stall_cycles: int = 0
        self._page_crossed: bool = False

        self._opcodes: dict[int, tuple[InstructionFunc, AddressingFunc]] = {}
        self._build_opcode_table()

    # ------------------------------------------------------------------
    # T-CPU-05: Reset
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset CPU: read reset vector, init SP and P."""
        lo = self._bus.read(0xFFFC)
        hi = self._bus.read(0xFFFD)
        self._regs.pc = (hi << 8) | lo
        self._regs.sp = 0xFD
        self._regs.p = 0x24
        self._cycles = 0

    # ------------------------------------------------------------------
    # T-CPU-43: Tick — fetch / decode / execute
    # ------------------------------------------------------------------

    def tick(self) -> int:
        """Execute one instruction and return the number of cycles consumed."""
        if self._stall_cycles > 0:
            self._stall_cycles -= 1
            return 1

        if self._interrupt is not None:
            self._handle_interrupt()
            return 7

        opcode = self._bus.read(self._regs.pc)
        self._regs.pc = (self._regs.pc + 1) & 0xFFFF

        instruction, addressing = self._opcodes[opcode]
        self._page_crossed = False
        addr = addressing()
        cycles = instruction(addr)
        self._cycles += cycles
        return cycles

    # ------------------------------------------------------------------
    # T-CPU-41: Public interrupt triggers
    # ------------------------------------------------------------------

    def trigger_nmi(self) -> None:
        """Trigger a Non-Maskable Interrupt."""
        self._interrupt = InterruptType.NMI

    def trigger_irq(self) -> None:
        """Trigger an IRQ if the I flag is clear."""
        if not (self._regs.p & I_FLAG):
            self._interrupt = InterruptType.IRQ

    # ------------------------------------------------------------------
    # T-CPU-44: Stall (for OAM DMA)
    # ------------------------------------------------------------------

    def stall(self, cycles: int) -> None:
        """Add stall cycles (e.g. during OAM DMA)."""
        self._stall_cycles += cycles

    # ------------------------------------------------------------------
    # T-CPU-06: Stack helpers
    # ------------------------------------------------------------------

    def _push(self, value: int) -> None:
        self._bus.write(0x100 + self._regs.sp, value & 0xFF)
        self._regs.sp = (self._regs.sp - 1) & 0xFF

    def _push_word(self, value: int) -> None:
        self._push((value >> 8) & 0xFF)
        self._push(value & 0xFF)

    def _pull(self) -> int:
        self._regs.sp = (self._regs.sp + 1) & 0xFF
        return self._bus.read(0x100 + self._regs.sp)

    def _pull_word(self) -> int:
        lo = self._pull()
        hi = self._pull()
        return (hi << 8) | lo

    # ------------------------------------------------------------------
    # T-CPU-40: Interrupt handling
    # ------------------------------------------------------------------

    def _handle_interrupt(self) -> None:
        self._push_word(self._regs.pc)
        self._push(self._regs.p & ~B_FLAG)
        self._regs.p |= I_FLAG

        if self._interrupt == InterruptType.NMI:
            vector = 0xFFFA
        else:
            vector = 0xFFFE

        lo = self._bus.read(vector)
        hi = self._bus.read(vector + 1)
        self._regs.pc = (hi << 8) | lo
        self._interrupt = None

    # ------------------------------------------------------------------
    # Flag helpers (used by instructions in opcodes.py)
    # ------------------------------------------------------------------

    def _set_flag(self, flag: int, condition: bool) -> None:
        if condition:
            self._regs.p |= flag
        else:
            self._regs.p &= ~flag

    def _set_zn(self, value: int) -> None:
        v = value & 0xFF
        self._regs.p = self._regs.p & ~(Z_FLAG | N_FLAG)
        if v == 0:
            self._regs.p |= Z_FLAG
        if v & 0x80:
            self._regs.p |= N_FLAG

    # ------------------------------------------------------------------
    # T-CPU-42: Build opcode table
    # ------------------------------------------------------------------

    def _build_opcode_table(self) -> None:
        from familybox.cpu.opcodes import build_opcode_table

        self._opcodes = build_opcode_table(self)
