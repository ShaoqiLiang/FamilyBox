"""6502 instruction implementations and opcode table builder.

Contains the complete instruction set for the NES 6502 CPU, including
all official opcodes and NOP fallbacks for illegal opcodes.
"""

#  *
#  * @Author: ShaoqiLiang
#  * @Date: 2026-05-16 22:07:49
#  * @LastEditors: ShaoqiLiang
#  *

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from familybox.cpu.cpu import CPU


def build_opcode_table(
    cpu: CPU,
) -> dict[int, tuple[Callable[[int], int], Callable[[], int]]]:
    """Build the 256-entry opcode lookup table.

    Each entry maps an opcode byte to ``(instruction, addressing)``
    where *instruction* takes the effective address and returns the
    cycle count, and *addressing* computes the effective address.

    Args:
        cpu: The CPU instance whose bus and registers are used.

    Returns:
        A dict of 256 opcode entries.
    """
    from familybox.cpu.addressing import AddressingModes as AM
    from familybox.cpu.cpu import (
        B_FLAG,
        C_FLAG,
        D_FLAG,
        I_FLAG,
        N_FLAG,
        V_FLAG,
        Z_FLAG,
    )

    # ------------------------------------------------------------------
    # Addressing mode closures (bind the CPU instance)
    # ------------------------------------------------------------------

    def imp() -> int:
        return AM.implied(cpu)

    def acc() -> int:
        return AM.accumulator(cpu)

    def imm() -> int:
        return AM.immediate(cpu)

    def zp() -> int:
        return AM.zero_page(cpu)

    def zpx() -> int:
        return AM.zero_page_x(cpu)

    def zpy() -> int:
        return AM.zero_page_y(cpu)

    def abs_() -> int:
        return AM.absolute(cpu)

    def abx() -> int:
        return AM.absolute_x(cpu)

    def aby() -> int:
        return AM.absolute_y(cpu)

    def ind() -> int:
        return AM.indirect(cpu)

    def izx() -> int:
        return AM.indexed_indirect(cpu)

    def izy() -> int:
        return AM.indirect_indexed(cpu)

    def rel() -> int:
        return AM.relative(cpu)

    # ------------------------------------------------------------------
    # Instruction wrappers
    # ------------------------------------------------------------------

    def _fixed(do: Callable[[int], None], cycles: int) -> Callable[[int], int]:
        """Wrap an instruction with a fixed cycle count."""

        def ins(addr: int) -> int:
            do(addr)
            return cycles

        return ins

    def _read(do: Callable[[int], None], base: int) -> Callable[[int], int]:
        """Wrap a read instruction with optional page-crossing penalty."""

        def ins(addr: int) -> int:
            do(addr)
            return base + (1 if cpu._page_crossed else 0)

        return ins

    # ------------------------------------------------------------------
    # Instruction implementations (closures over *cpu*)
    # ------------------------------------------------------------------

    # -- Data transfer -------------------------------------------------

    def do_lda(addr: int) -> None:
        cpu._regs.a = cpu._bus.read(addr)
        cpu._set_zn(cpu._regs.a)

    def do_ldx(addr: int) -> None:
        cpu._regs.x = cpu._bus.read(addr)
        cpu._set_zn(cpu._regs.x)

    def do_ldy(addr: int) -> None:
        cpu._regs.y = cpu._bus.read(addr)
        cpu._set_zn(cpu._regs.y)

    def do_sta(addr: int) -> None:
        cpu._bus.write(addr, cpu._regs.a)

    def do_stx(addr: int) -> None:
        cpu._bus.write(addr, cpu._regs.x)

    def do_sty(addr: int) -> None:
        cpu._bus.write(addr, cpu._regs.y)

    def do_tax(addr: int) -> None:
        cpu._regs.x = cpu._regs.a
        cpu._set_zn(cpu._regs.x)

    def do_tay(addr: int) -> None:
        cpu._regs.y = cpu._regs.a
        cpu._set_zn(cpu._regs.y)

    def do_txa(addr: int) -> None:
        cpu._regs.a = cpu._regs.x
        cpu._set_zn(cpu._regs.a)

    def do_tya(addr: int) -> None:
        cpu._regs.a = cpu._regs.y
        cpu._set_zn(cpu._regs.a)

    def do_tsx(addr: int) -> None:
        cpu._regs.x = cpu._regs.sp
        cpu._set_zn(cpu._regs.x)

    def do_txs(addr: int) -> None:
        cpu._regs.sp = cpu._regs.x

    # -- Arithmetic ----------------------------------------------------

    def do_adc(addr: int) -> None:
        val = cpu._bus.read(addr)
        c = cpu._regs.p & C_FLAG
        result = cpu._regs.a + val + c
        cpu._regs.p &= ~(C_FLAG | Z_FLAG | V_FLAG | N_FLAG)
        if result > 0xFF:
            cpu._regs.p |= C_FLAG
        if (cpu._regs.a ^ result) & (val ^ result) & 0x80:
            cpu._regs.p |= V_FLAG
        cpu._regs.a = result & 0xFF
        if cpu._regs.a == 0:
            cpu._regs.p |= Z_FLAG
        if cpu._regs.a & 0x80:
            cpu._regs.p |= N_FLAG

    def do_sbc(addr: int) -> None:
        val = cpu._bus.read(addr)
        c = cpu._regs.p & C_FLAG
        result = cpu._regs.a - val - (1 - c)
        cpu._regs.p &= ~(C_FLAG | Z_FLAG | V_FLAG | N_FLAG)
        if result >= 0:
            cpu._regs.p |= C_FLAG
        if (cpu._regs.a ^ val) & (cpu._regs.a ^ result) & 0x80:
            cpu._regs.p |= V_FLAG
        cpu._regs.a = result & 0xFF
        if cpu._regs.a == 0:
            cpu._regs.p |= Z_FLAG
        if cpu._regs.a & 0x80:
            cpu._regs.p |= N_FLAG

    def do_inc(addr: int) -> None:
        val = (cpu._bus.read(addr) + 1) & 0xFF
        cpu._bus.write(addr, val)
        cpu._set_zn(val)

    def do_dec(addr: int) -> None:
        val = (cpu._bus.read(addr) - 1) & 0xFF
        cpu._bus.write(addr, val)
        cpu._set_zn(val)

    def do_inx(addr: int) -> None:
        cpu._regs.x = (cpu._regs.x + 1) & 0xFF
        cpu._set_zn(cpu._regs.x)

    def do_dex(addr: int) -> None:
        cpu._regs.x = (cpu._regs.x - 1) & 0xFF
        cpu._set_zn(cpu._regs.x)

    def do_iny(addr: int) -> None:
        cpu._regs.y = (cpu._regs.y + 1) & 0xFF
        cpu._set_zn(cpu._regs.y)

    def do_dey(addr: int) -> None:
        cpu._regs.y = (cpu._regs.y - 1) & 0xFF
        cpu._set_zn(cpu._regs.y)

    # -- Logic ---------------------------------------------------------

    def do_and(addr: int) -> None:
        cpu._regs.a &= cpu._bus.read(addr)
        cpu._set_zn(cpu._regs.a)

    def do_ora(addr: int) -> None:
        cpu._regs.a |= cpu._bus.read(addr)
        cpu._set_zn(cpu._regs.a)

    def do_eor(addr: int) -> None:
        cpu._regs.a ^= cpu._bus.read(addr)
        cpu._set_zn(cpu._regs.a)

    def do_bit(addr: int) -> None:
        val = cpu._bus.read(addr)
        cpu._regs.p &= ~(Z_FLAG | V_FLAG | N_FLAG)
        if (cpu._regs.a & val) == 0:
            cpu._regs.p |= Z_FLAG
        if val & V_FLAG:
            cpu._regs.p |= V_FLAG
        if val & N_FLAG:
            cpu._regs.p |= N_FLAG

    # -- Compare -------------------------------------------------------

    def do_cmp(addr: int) -> None:
        val = cpu._bus.read(addr)
        result = cpu._regs.a - val
        cpu._regs.p &= ~(C_FLAG | Z_FLAG | N_FLAG)
        if cpu._regs.a >= val:
            cpu._regs.p |= C_FLAG
        if (result & 0xFF) == 0:
            cpu._regs.p |= Z_FLAG
        if result & 0x80:
            cpu._regs.p |= N_FLAG

    def do_cpx(addr: int) -> None:
        val = cpu._bus.read(addr)
        result = cpu._regs.x - val
        cpu._regs.p &= ~(C_FLAG | Z_FLAG | N_FLAG)
        if cpu._regs.x >= val:
            cpu._regs.p |= C_FLAG
        if (result & 0xFF) == 0:
            cpu._regs.p |= Z_FLAG
        if result & 0x80:
            cpu._regs.p |= N_FLAG

    def do_cpy(addr: int) -> None:
        val = cpu._bus.read(addr)
        result = cpu._regs.y - val
        cpu._regs.p &= ~(C_FLAG | Z_FLAG | N_FLAG)
        if cpu._regs.y >= val:
            cpu._regs.p |= C_FLAG
        if (result & 0xFF) == 0:
            cpu._regs.p |= Z_FLAG
        if result & 0x80:
            cpu._regs.p |= N_FLAG

    # -- Shift / Rotate -----------------------------------------------

    def do_asl_a(addr: int) -> None:
        old = cpu._regs.a
        cpu._regs.p = (cpu._regs.p & ~C_FLAG) | ((old >> 7) & C_FLAG)
        cpu._regs.a = (old << 1) & 0xFF
        cpu._set_zn(cpu._regs.a)

    def do_asl_m(addr: int) -> None:
        old = cpu._bus.read(addr)
        cpu._regs.p = (cpu._regs.p & ~C_FLAG) | ((old >> 7) & C_FLAG)
        val = (old << 1) & 0xFF
        cpu._bus.write(addr, val)
        cpu._set_zn(val)

    def do_lsr_a(addr: int) -> None:
        old = cpu._regs.a
        cpu._regs.p = (cpu._regs.p & ~C_FLAG) | (old & C_FLAG)
        cpu._regs.a = old >> 1
        cpu._set_zn(cpu._regs.a)

    def do_lsr_m(addr: int) -> None:
        old = cpu._bus.read(addr)
        cpu._regs.p = (cpu._regs.p & ~C_FLAG) | (old & C_FLAG)
        val = old >> 1
        cpu._bus.write(addr, val)
        cpu._set_zn(val)

    def do_rol_a(addr: int) -> None:
        old = cpu._regs.a
        carry_in = cpu._regs.p & C_FLAG
        cpu._regs.p = (cpu._regs.p & ~C_FLAG) | ((old >> 7) & C_FLAG)
        cpu._regs.a = ((old << 1) | carry_in) & 0xFF
        cpu._set_zn(cpu._regs.a)

    def do_rol_m(addr: int) -> None:
        old = cpu._bus.read(addr)
        carry_in = cpu._regs.p & C_FLAG
        cpu._regs.p = (cpu._regs.p & ~C_FLAG) | ((old >> 7) & C_FLAG)
        val = ((old << 1) | carry_in) & 0xFF
        cpu._bus.write(addr, val)
        cpu._set_zn(val)

    def do_ror_a(addr: int) -> None:
        old = cpu._regs.a
        carry_in = cpu._regs.p & C_FLAG
        cpu._regs.p = (cpu._regs.p & ~C_FLAG) | (old & C_FLAG)
        cpu._regs.a = (old >> 1) | (carry_in << 7)
        cpu._set_zn(cpu._regs.a)

    def do_ror_m(addr: int) -> None:
        old = cpu._bus.read(addr)
        carry_in = cpu._regs.p & C_FLAG
        cpu._regs.p = (cpu._regs.p & ~C_FLAG) | (old & C_FLAG)
        val = (old >> 1) | (carry_in << 7)
        cpu._bus.write(addr, val)
        cpu._set_zn(val)

    # -- Branches ------------------------------------------------------

    def _branch(condition: bool, addr: int) -> int:
        if not condition:
            return 2
        crossed = (cpu._regs.pc & 0xFF00) != (addr & 0xFF00)
        cpu._regs.pc = addr
        return 4 if crossed else 3

    def do_beq(addr: int) -> int:
        return _branch(bool(cpu._regs.p & Z_FLAG), addr)

    def do_bne(addr: int) -> int:
        return _branch(not (cpu._regs.p & Z_FLAG), addr)

    def do_bcs(addr: int) -> int:
        return _branch(bool(cpu._regs.p & C_FLAG), addr)

    def do_bcc(addr: int) -> int:
        return _branch(not (cpu._regs.p & C_FLAG), addr)

    def do_bmi(addr: int) -> int:
        return _branch(bool(cpu._regs.p & N_FLAG), addr)

    def do_bpl(addr: int) -> int:
        return _branch(not (cpu._regs.p & N_FLAG), addr)

    def do_bvs(addr: int) -> int:
        return _branch(bool(cpu._regs.p & V_FLAG), addr)

    def do_bvc(addr: int) -> int:
        return _branch(not (cpu._regs.p & V_FLAG), addr)

    # -- Jump / Subroutine --------------------------------------------

    def do_jmp(addr: int) -> None:
        cpu._regs.pc = addr

    def do_jsr(addr: int) -> None:
        cpu._push_word((cpu._regs.pc - 1) & 0xFFFF)
        cpu._regs.pc = addr

    def do_rts(addr: int) -> None:
        cpu._regs.pc = (cpu._pull_word() + 1) & 0xFFFF

    def do_rti(addr: int) -> None:
        cpu._regs.p = (cpu._pull() | 0x20) & ~B_FLAG
        cpu._regs.pc = cpu._pull_word()

    # -- Stack ---------------------------------------------------------

    def do_pha(addr: int) -> None:
        cpu._push(cpu._regs.a)

    def do_php(addr: int) -> None:
        cpu._push(cpu._regs.p | B_FLAG | 0x20)

    def do_pla(addr: int) -> None:
        cpu._regs.a = cpu._pull()
        cpu._set_zn(cpu._regs.a)

    def do_plp(addr: int) -> None:
        cpu._regs.p = (cpu._pull() | 0x20) & ~B_FLAG

    # -- Flag set / clear ----------------------------------------------

    def do_clc(addr: int) -> None:
        cpu._regs.p &= ~C_FLAG

    def do_sec(addr: int) -> None:
        cpu._regs.p |= C_FLAG

    def do_cli(addr: int) -> None:
        cpu._regs.p &= ~I_FLAG

    def do_sei(addr: int) -> None:
        cpu._regs.p |= I_FLAG

    def do_clv(addr: int) -> None:
        cpu._regs.p &= ~V_FLAG

    def do_cld(addr: int) -> None:
        cpu._regs.p &= ~D_FLAG

    def do_sed(addr: int) -> None:
        cpu._regs.p |= D_FLAG

    # -- BRK / NOP -----------------------------------------------------

    def do_brk(addr: int) -> None:
        cpu._regs.pc = (cpu._regs.pc + 1) & 0xFFFF  # skip padding byte
        cpu._push_word(cpu._regs.pc)
        cpu._push(cpu._regs.p | B_FLAG | 0x20)
        cpu._regs.p |= I_FLAG
        lo = cpu._bus.read(0xFFFE)
        hi = cpu._bus.read(0xFFFF)
        cpu._regs.pc = (hi << 8) | lo

    def do_nop(addr: int) -> None:
        pass

    # ------------------------------------------------------------------
    # Opcode table (256 entries)
    # ------------------------------------------------------------------

    t: dict[int, tuple[Callable[[int], int], Callable[[], int]]] = {}

    # Fill illegal opcodes with NOP (2 cycles, implied) first.
    for i in range(256):
        t[i] = (_fixed(do_nop, 2), imp)

    # -- 0x00-0x0F -----------------------------------------------------
    t[0x00] = (_fixed(do_brk, 7), imp)
    t[0x01] = (_fixed(do_ora, 6), izx)
    t[0x05] = (_fixed(do_ora, 3), zp)
    t[0x06] = (_fixed(do_asl_m, 5), zp)
    t[0x08] = (_fixed(do_php, 3), imp)
    t[0x09] = (_fixed(do_ora, 2), imm)
    t[0x0A] = (_fixed(do_asl_a, 2), acc)
    t[0x0D] = (_fixed(do_ora, 4), abs_)
    t[0x0E] = (_fixed(do_asl_m, 6), abs_)

    # -- 0x10-0x1F -----------------------------------------------------
    t[0x10] = (do_bpl, rel)
    t[0x11] = (_read(do_ora, 5), izy)
    t[0x15] = (_fixed(do_ora, 4), zpx)
    t[0x16] = (_fixed(do_asl_m, 6), zpx)
    t[0x18] = (_fixed(do_clc, 2), imp)
    t[0x19] = (_read(do_ora, 4), aby)
    t[0x1D] = (_read(do_ora, 4), abx)
    t[0x1E] = (_fixed(do_asl_m, 7), abx)

    # -- 0x20-0x2F -----------------------------------------------------
    t[0x20] = (_fixed(do_jsr, 6), abs_)
    t[0x21] = (_fixed(do_and, 6), izx)
    t[0x24] = (_fixed(do_bit, 3), zp)
    t[0x25] = (_fixed(do_and, 3), zp)
    t[0x26] = (_fixed(do_rol_m, 5), zp)
    t[0x28] = (_fixed(do_plp, 4), imp)
    t[0x29] = (_fixed(do_and, 2), imm)
    t[0x2A] = (_fixed(do_rol_a, 2), acc)
    t[0x2C] = (_fixed(do_bit, 4), abs_)
    t[0x2D] = (_fixed(do_and, 4), abs_)
    t[0x2E] = (_fixed(do_rol_m, 6), abs_)

    # -- 0x30-0x3F -----------------------------------------------------
    t[0x30] = (do_bmi, rel)
    t[0x31] = (_read(do_and, 5), izy)
    t[0x35] = (_fixed(do_and, 4), zpx)
    t[0x36] = (_fixed(do_rol_m, 6), zpx)
    t[0x38] = (_fixed(do_sec, 2), imp)
    t[0x39] = (_read(do_and, 4), aby)
    t[0x3D] = (_read(do_and, 4), abx)
    t[0x3E] = (_fixed(do_rol_m, 7), abx)

    # -- 0x40-0x4F -----------------------------------------------------
    t[0x40] = (_fixed(do_rti, 6), imp)
    t[0x41] = (_fixed(do_eor, 6), izx)
    t[0x45] = (_fixed(do_eor, 3), zp)
    t[0x46] = (_fixed(do_lsr_m, 5), zp)
    t[0x48] = (_fixed(do_pha, 3), imp)
    t[0x49] = (_fixed(do_eor, 2), imm)
    t[0x4A] = (_fixed(do_lsr_a, 2), acc)
    t[0x4C] = (_fixed(do_jmp, 3), abs_)
    t[0x4D] = (_fixed(do_eor, 4), abs_)
    t[0x4E] = (_fixed(do_lsr_m, 6), abs_)

    # -- 0x50-0x5F -----------------------------------------------------
    t[0x50] = (do_bvc, rel)
    t[0x51] = (_read(do_eor, 5), izy)
    t[0x55] = (_fixed(do_eor, 4), zpx)
    t[0x56] = (_fixed(do_lsr_m, 6), zpx)
    t[0x58] = (_fixed(do_cli, 2), imp)
    t[0x59] = (_read(do_eor, 4), aby)
    t[0x5D] = (_read(do_eor, 4), abx)
    t[0x5E] = (_fixed(do_lsr_m, 7), abx)

    # -- 0x60-0x6F -----------------------------------------------------
    t[0x60] = (_fixed(do_rts, 6), imp)
    t[0x61] = (_fixed(do_adc, 6), izx)
    t[0x65] = (_fixed(do_adc, 3), zp)
    t[0x66] = (_fixed(do_ror_m, 5), zp)
    t[0x68] = (_fixed(do_pla, 4), imp)
    t[0x69] = (_fixed(do_adc, 2), imm)
    t[0x6A] = (_fixed(do_ror_a, 2), acc)
    t[0x6C] = (_fixed(do_jmp, 5), ind)
    t[0x6D] = (_fixed(do_adc, 4), abs_)
    t[0x6E] = (_fixed(do_ror_m, 6), abs_)

    # -- 0x70-0x7F -----------------------------------------------------
    t[0x70] = (do_bvs, rel)
    t[0x71] = (_read(do_adc, 5), izy)
    t[0x75] = (_fixed(do_adc, 4), zpx)
    t[0x76] = (_fixed(do_ror_m, 6), zpx)
    t[0x78] = (_fixed(do_sei, 2), imp)
    t[0x79] = (_read(do_adc, 4), aby)
    t[0x7D] = (_read(do_adc, 4), abx)
    t[0x7E] = (_fixed(do_ror_m, 7), abx)

    # -- 0x80-0x8F -----------------------------------------------------
    t[0x81] = (_fixed(do_sta, 6), izx)
    t[0x84] = (_fixed(do_sty, 3), zp)
    t[0x85] = (_fixed(do_sta, 3), zp)
    t[0x86] = (_fixed(do_stx, 3), zp)
    t[0x88] = (_fixed(do_dey, 2), imp)
    t[0x8A] = (_fixed(do_txa, 2), imp)
    t[0x8C] = (_fixed(do_sty, 4), abs_)
    t[0x8D] = (_fixed(do_sta, 4), abs_)
    t[0x8E] = (_fixed(do_stx, 4), abs_)

    # -- 0x90-0x9F -----------------------------------------------------
    t[0x90] = (do_bcc, rel)
    t[0x91] = (_fixed(do_sta, 6), izy)
    t[0x94] = (_fixed(do_sty, 4), zpx)
    t[0x95] = (_fixed(do_sta, 4), zpx)
    t[0x96] = (_fixed(do_stx, 4), zpy)
    t[0x98] = (_fixed(do_tya, 2), imp)
    t[0x99] = (_fixed(do_sta, 5), aby)
    t[0x9A] = (_fixed(do_txs, 2), imp)
    t[0x9D] = (_fixed(do_sta, 5), abx)

    # -- 0xA0-0xAF -----------------------------------------------------
    t[0xA0] = (_fixed(do_ldy, 2), imm)
    t[0xA1] = (_fixed(do_lda, 6), izx)
    t[0xA2] = (_fixed(do_ldx, 2), imm)
    t[0xA4] = (_fixed(do_ldy, 3), zp)
    t[0xA5] = (_fixed(do_lda, 3), zp)
    t[0xA6] = (_fixed(do_ldx, 3), zp)
    t[0xA8] = (_fixed(do_tay, 2), imp)
    t[0xA9] = (_fixed(do_lda, 2), imm)
    t[0xAA] = (_fixed(do_tax, 2), imp)
    t[0xAC] = (_fixed(do_ldy, 4), abs_)
    t[0xAD] = (_fixed(do_lda, 4), abs_)
    t[0xAE] = (_fixed(do_ldx, 4), abs_)

    # -- 0xB0-0xBF -----------------------------------------------------
    t[0xB0] = (do_bcs, rel)
    t[0xB1] = (_read(do_lda, 5), izy)
    t[0xB4] = (_fixed(do_ldy, 4), zpx)
    t[0xB5] = (_fixed(do_lda, 4), zpx)
    t[0xB6] = (_fixed(do_ldx, 4), zpy)
    t[0xB8] = (_fixed(do_clv, 2), imp)
    t[0xB9] = (_read(do_lda, 4), aby)
    t[0xBA] = (_fixed(do_tsx, 2), imp)
    t[0xBC] = (_read(do_ldy, 4), abx)
    t[0xBD] = (_read(do_lda, 4), abx)
    t[0xBE] = (_read(do_ldx, 4), aby)

    # -- 0xC0-0xCF -----------------------------------------------------
    t[0xC0] = (_fixed(do_cpy, 2), imm)
    t[0xC1] = (_fixed(do_cmp, 6), izx)
    t[0xC4] = (_fixed(do_cpy, 3), zp)
    t[0xC5] = (_fixed(do_cmp, 3), zp)
    t[0xC6] = (_fixed(do_dec, 5), zp)
    t[0xC8] = (_fixed(do_iny, 2), imp)
    t[0xC9] = (_fixed(do_cmp, 2), imm)
    t[0xCA] = (_fixed(do_dex, 2), imp)
    t[0xCC] = (_fixed(do_cpy, 4), abs_)
    t[0xCD] = (_fixed(do_cmp, 4), abs_)
    t[0xCE] = (_fixed(do_dec, 6), abs_)

    # -- 0xD0-0xDF -----------------------------------------------------
    t[0xD0] = (do_bne, rel)
    t[0xD1] = (_read(do_cmp, 5), izy)
    t[0xD5] = (_fixed(do_cmp, 4), zpx)
    t[0xD6] = (_fixed(do_dec, 6), zpx)
    t[0xD8] = (_fixed(do_cld, 2), imp)
    t[0xD9] = (_read(do_cmp, 4), aby)
    t[0xDD] = (_read(do_cmp, 4), abx)
    t[0xDE] = (_fixed(do_dec, 7), abx)

    # -- 0xE0-0xEF -----------------------------------------------------
    t[0xE0] = (_fixed(do_cpx, 2), imm)
    t[0xE1] = (_fixed(do_sbc, 6), izx)
    t[0xE4] = (_fixed(do_cpx, 3), zp)
    t[0xE5] = (_fixed(do_sbc, 3), zp)
    t[0xE6] = (_fixed(do_inc, 5), zp)
    t[0xE8] = (_fixed(do_inx, 2), imp)
    t[0xE9] = (_fixed(do_sbc, 2), imm)
    t[0xEA] = (_fixed(do_nop, 2), imp)
    t[0xEC] = (_fixed(do_cpx, 4), abs_)
    t[0xED] = (_fixed(do_sbc, 4), abs_)
    t[0xEE] = (_fixed(do_inc, 6), abs_)

    # -- 0xF0-0xFF -----------------------------------------------------
    t[0xF0] = (do_beq, rel)
    t[0xF1] = (_read(do_sbc, 5), izy)
    t[0xF5] = (_fixed(do_sbc, 4), zpx)
    t[0xF6] = (_fixed(do_inc, 6), zpx)
    t[0xF8] = (_fixed(do_sed, 2), imp)
    t[0xF9] = (_read(do_sbc, 4), aby)
    t[0xFD] = (_read(do_sbc, 4), abx)
    t[0xFE] = (_fixed(do_inc, 7), abx)

    return t
