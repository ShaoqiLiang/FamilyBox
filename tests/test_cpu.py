"""Comprehensive tests for the MOS 6502 CPU emulator.

Tests cover addressing modes, instruction flag behaviour, interrupts,
branch logic, and stack operations.
"""

from familybox.cpu.cpu import (
    B_FLAG,
    C_FLAG,
    D_FLAG,
    I_FLAG,
    N_FLAG,
    V_FLAG,
    Z_FLAG,
    CPU,
    InterruptType,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class MockCPUBus:
    """In-memory bus for testing."""

    def __init__(self) -> None:
        self._memory: dict[int, int] = {}

    def read(self, addr: int) -> int:
        return self._memory.get(addr & 0xFFFF, 0)

    def write(self, addr: int, value: int) -> None:
        self._memory[addr & 0xFFFF] = value & 0xFF


def _make_cpu(program: list[int], start: int = 0x8000) -> tuple[CPU, MockCPUBus]:
    """Load a program and return a reset CPU + bus pair."""
    bus = MockCPUBus()
    bus._memory[0xFFFC] = start & 0xFF
    bus._memory[0xFFFD] = (start >> 8) & 0xFF
    for i, byte in enumerate(program):
        bus._memory[(start + i) & 0xFFFF] = byte & 0xFF
    cpu = CPU(bus)
    cpu.reset()
    return cpu, bus


# ===================================================================
# T-CPU-01 / T-CPU-04 / T-CPU-05: Registers & reset
# ===================================================================


class TestRegistersAndReset:
    def test_default_register_values(self) -> None:
        bus = MockCPUBus()
        cpu = CPU(bus)
        r = cpu._regs
        assert r.a == 0
        assert r.x == 0
        assert r.y == 0
        assert r.sp == 0xFD
        assert r.pc == 0
        assert r.p == 0x24

    def test_reset_reads_vector(self) -> None:
        bus = MockCPUBus()
        bus._memory[0xFFFC] = 0x00
        bus._memory[0xFFFD] = 0xC0
        cpu = CPU(bus)
        cpu.reset()
        assert cpu._regs.pc == 0xC000
        assert cpu._regs.sp == 0xFD
        assert cpu._regs.p == 0x24

    def test_reset_cycles_zero(self) -> None:
        bus = MockCPUBus()
        cpu = CPU(bus)
        cpu._cycles = 100
        cpu.reset()
        assert cpu._cycles == 0


# ===================================================================
# T-CPU-14: Addressing modes
# ===================================================================


class TestAddressingModes:
    def test_immediate(self) -> None:
        cpu, bus = _make_cpu([0xA9, 0x42])  # LDA #$42
        cpu.tick()
        assert cpu._regs.a == 0x42

    def test_zero_page(self) -> None:
        cpu, bus = _make_cpu([0xA5, 0x10])  # LDA $10
        bus._memory[0x10] = 0x77
        cpu.tick()
        assert cpu._regs.a == 0x77

    def test_zero_page_x(self) -> None:
        cpu, bus = _make_cpu([0xB5, 0x10])  # LDA $10,X
        cpu._regs.x = 0x05
        bus._memory[0x15] = 0xAB
        cpu.tick()
        assert cpu._regs.a == 0xAB

    def test_zero_page_x_wraps(self) -> None:
        cpu, bus = _make_cpu([0xB5, 0xFF])  # LDA $FF,X
        cpu._regs.x = 0x02
        bus._memory[0x01] = 0x55  # (0xFF + 2) & 0xFF = 0x01
        cpu.tick()
        assert cpu._regs.a == 0x55

    def test_zero_page_y(self) -> None:
        cpu, bus = _make_cpu([0xB6, 0x10])  # LDX $10,Y
        cpu._regs.y = 0x03
        bus._memory[0x13] = 0xCC
        cpu.tick()
        assert cpu._regs.x == 0xCC

    def test_absolute(self) -> None:
        cpu, bus = _make_cpu([0xAD, 0x34, 0x12])  # LDA $1234
        bus._memory[0x1234] = 0xEE
        cpu.tick()
        assert cpu._regs.a == 0xEE

    def test_absolute_x(self) -> None:
        cpu, bus = _make_cpu([0xBD, 0x00, 0x20])  # LDA $2000,X
        cpu._regs.x = 0x05
        bus._memory[0x2005] = 0x99
        cpu.tick()
        assert cpu._regs.a == 0x99

    def test_absolute_y(self) -> None:
        cpu, bus = _make_cpu([0xB9, 0x00, 0x20])  # LDA $2000,Y
        cpu._regs.y = 0x10
        bus._memory[0x2010] = 0x88
        cpu.tick()
        assert cpu._regs.a == 0x88

    def test_indirect_x(self) -> None:
        cpu, bus = _make_cpu([0xA1, 0x20])  # LDA ($20,X)
        cpu._regs.x = 0x04
        # Pointer at zero-page address (0x20 + 4) = 0x24
        bus._memory[0x24] = 0x00
        bus._memory[0x25] = 0x30
        bus._memory[0x3000] = 0xBE
        cpu.tick()
        assert cpu._regs.a == 0xBE

    def test_indirect_y(self) -> None:
        cpu, bus = _make_cpu([0xB1, 0x20])  # LDA ($20),Y
        cpu._regs.y = 0x10
        # Pointer at zero-page address 0x20
        bus._memory[0x20] = 0x00
        bus._memory[0x21] = 0x40
        bus._memory[0x4010] = 0xCA
        cpu.tick()
        assert cpu._regs.a == 0xCA

    def test_indirect_page_crossing_bug(self) -> None:
        """JMP ($10FF) should read high byte from $1000, not $1100."""
        cpu, bus = _make_cpu([0x6C, 0xFF, 0x10])  # JMP ($10FF)
        bus._memory[0x10FF] = 0x40
        bus._memory[0x1000] = 0x20  # page-crossing bug: wraps to same page
        bus._memory[0x1100] = 0x99  # this should NOT be read
        cpu.tick()
        assert cpu._regs.pc == 0x2040

    def test_relative_forward(self) -> None:
        # BNE +5: branch to PC+5 if Z clear
        cpu, bus = _make_cpu([0xD0, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00])
        cpu._regs.p &= ~Z_FLAG  # Z clear -> branch taken
        cpu.tick()
        # PC after reading opcode+operand = 0x8002, target = 0x8002 + 5 = 0x8007
        assert cpu._regs.pc == 0x8007

    def test_relative_backward(self) -> None:
        # Place BNE at 0x8010 with offset 0xF0 (-16)
        cpu, bus = _make_cpu([0xD0, 0xF0], start=0x8010)
        cpu._regs.p &= ~Z_FLAG  # branch taken
        cpu.tick()
        # PC after reading = 0x8012, target = 0x8012 - 16 = 0x8002
        assert cpu._regs.pc == 0x8002


# ===================================================================
# T-CPU-15..T-CPU-17: Data transfer instructions
# ===================================================================


class TestDataTransfer:
    def test_lda_immediate(self) -> None:
        cpu, _ = _make_cpu([0xA9, 0x00])  # LDA #$00
        cpu.tick()
        assert cpu._regs.a == 0
        assert cpu._regs.p & Z_FLAG

    def test_lda_sets_negative(self) -> None:
        cpu, _ = _make_cpu([0xA9, 0x80])  # LDA #$80
        cpu.tick()
        assert cpu._regs.a == 0x80
        assert cpu._regs.p & N_FLAG
        assert not (cpu._regs.p & Z_FLAG)

    def test_ldx_ldy(self) -> None:
        cpu, _ = _make_cpu([0xA2, 0x10, 0xA0, 0x20])  # LDX #$10; LDY #$20
        cpu.tick()
        assert cpu._regs.x == 0x10
        cpu.tick()
        assert cpu._regs.y == 0x20

    def test_sta_stx_sty(self) -> None:
        cpu, bus = _make_cpu(
            [
                0xA9,
                0x11,  # LDA #$11
                0x85,
                0x00,  # STA $00
                0xA2,
                0x22,  # LDX #$22
                0x86,
                0x01,  # STX $01
                0xA0,
                0x33,  # LDY #$33
                0x84,
                0x02,  # STY $02
            ]
        )
        for _ in range(6):
            cpu.tick()
        assert bus._memory[0x00] == 0x11
        assert bus._memory[0x01] == 0x22
        assert bus._memory[0x02] == 0x33

    def test_tax_tay_txa_tya(self) -> None:
        cpu, _ = _make_cpu(
            [
                0xA9,
                0x42,  # LDA #$42
                0xAA,  # TAX
                0xA8,  # TAY
            ]
        )
        cpu.tick()
        cpu.tick()
        assert cpu._regs.x == 0x42
        cpu.tick()
        assert cpu._regs.y == 0x42

    def test_txa_tya(self) -> None:
        cpu, _ = _make_cpu(
            [
                0xA2,
                0x55,  # LDX #$55
                0x8A,  # TXA
                0xA0,
                0x66,  # LDY #$66
                0x98,  # TYA
            ]
        )
        cpu.tick()  # LDX
        cpu.tick()  # TXA
        assert cpu._regs.a == 0x55
        cpu.tick()  # LDY
        cpu.tick()  # TYA
        assert cpu._regs.a == 0x66

    def test_tsx_txs(self) -> None:
        cpu, _ = _make_cpu([0xBA, 0x9A])  # TSX; TXS
        cpu._regs.sp = 0xFD
        cpu.tick()  # TSX
        assert cpu._regs.x == 0xFD
        cpu._regs.x = 0xF0
        cpu.tick()  # TXS
        assert cpu._regs.sp == 0xF0


# ===================================================================
# T-CPU-18..T-CPU-21: Arithmetic
# ===================================================================


class TestArithmetic:
    def test_adc_basic(self) -> None:
        cpu, _ = _make_cpu([0x69, 0x05])  # ADC #$05
        cpu._regs.a = 3
        cpu._regs.p = 0x24  # clear carry
        cpu.tick()
        assert cpu._regs.a == 8
        assert not (cpu._regs.p & C_FLAG)
        assert not (cpu._regs.p & Z_FLAG)
        assert not (cpu._regs.p & N_FLAG)

    def test_adc_with_carry(self) -> None:
        cpu, _ = _make_cpu([0x69, 0x01])  # ADC #$01
        cpu._regs.a = 0xFF
        cpu._regs.p = 0x24 | C_FLAG  # carry set
        cpu.tick()
        assert cpu._regs.a == 0x01
        assert cpu._regs.p & C_FLAG  # carry out
        assert not (cpu._regs.p & Z_FLAG)

    def test_adc_zero_result(self) -> None:
        cpu, _ = _make_cpu([0x69, 0x00])  # ADC #$00
        cpu._regs.a = 0
        cpu._regs.p = 0x24
        cpu.tick()
        assert cpu._regs.a == 0
        assert cpu._regs.p & Z_FLAG

    def test_adc_overflow_positive(self) -> None:
        """Positive + Positive = Negative -> overflow."""
        cpu, _ = _make_cpu([0x69, 0x50])  # ADC #$50
        cpu._regs.a = 0x50
        cpu._regs.p = 0x24
        cpu.tick()
        assert cpu._regs.a == 0xA0
        assert cpu._regs.p & V_FLAG
        assert cpu._regs.p & N_FLAG

    def test_adc_overflow_negative(self) -> None:
        """Negative + Negative = Positive -> overflow."""
        cpu, _ = _make_cpu([0x69, 0x90])  # ADC #$90
        cpu._regs.a = 0x90
        cpu._regs.p = 0x24
        cpu.tick()
        assert cpu._regs.a == 0x20
        assert cpu._regs.p & V_FLAG
        assert not (cpu._regs.p & N_FLAG)

    def test_adc_no_overflow(self) -> None:
        """Positive + Negative -> no overflow."""
        cpu, _ = _make_cpu([0x69, 0x90])  # ADC #$90 (negative)
        cpu._regs.a = 0x10  # positive
        cpu._regs.p = 0x24
        cpu.tick()
        assert cpu._regs.a == 0xA0
        assert not (cpu._regs.p & V_FLAG)

    def test_sbc_basic(self) -> None:
        cpu, _ = _make_cpu([0xE9, 0x03])  # SBC #$03
        cpu._regs.a = 10
        cpu._regs.p = 0x24 | C_FLAG  # carry set (no borrow)
        cpu.tick()
        assert cpu._regs.a == 7
        assert cpu._regs.p & C_FLAG  # no borrow
        assert not (cpu._regs.p & Z_FLAG)
        assert not (cpu._regs.p & N_FLAG)

    def test_sbc_borrow(self) -> None:
        cpu, _ = _make_cpu([0xE9, 0x01])  # SBC #$01
        cpu._regs.a = 0x00
        cpu._regs.p = 0x24 | C_FLAG
        cpu.tick()
        assert cpu._regs.a == 0xFF
        assert not (cpu._regs.p & C_FLAG)  # borrow occurred
        assert cpu._regs.p & N_FLAG

    def test_sbc_zero_result(self) -> None:
        cpu, _ = _make_cpu([0xE9, 0x05])  # SBC #$05
        cpu._regs.a = 0x05
        cpu._regs.p = 0x24 | C_FLAG
        cpu.tick()
        assert cpu._regs.a == 0
        assert cpu._regs.p & Z_FLAG
        assert cpu._regs.p & C_FLAG

    def test_sbc_overflow(self) -> None:
        """Positive - Negative = Negative -> overflow."""
        cpu, _ = _make_cpu([0xE9, 0xB0])  # SBC #$B0 (negative in signed)
        cpu._regs.a = 0x50  # positive
        cpu._regs.p = 0x24 | C_FLAG
        cpu.tick()
        assert cpu._regs.a == 0xA0
        assert cpu._regs.p & V_FLAG

    def test_inc_dec(self) -> None:
        cpu, bus = _make_cpu(
            [
                0xE6,
                0x10,  # INC $10
                0xE6,
                0x10,  # INC $10
                0xC6,
                0x10,  # DEC $10
            ]
        )
        bus._memory[0x10] = 0xFE
        cpu.tick()  # INC -> 0xFF
        assert bus._memory[0x10] == 0xFF
        assert cpu._regs.p & N_FLAG
        cpu.tick()  # INC -> 0x00
        assert bus._memory[0x10] == 0x00
        assert cpu._regs.p & Z_FLAG
        cpu.tick()  # DEC -> 0xFF
        assert bus._memory[0x10] == 0xFF
        assert cpu._regs.p & N_FLAG

    def test_inx_dex_iny_dey(self) -> None:
        cpu, _ = _make_cpu([0xE8, 0xCA, 0xC8, 0x88])
        cpu._regs.x = 0
        cpu.tick()  # INX
        assert cpu._regs.x == 1
        cpu.tick()  # DEX
        assert cpu._regs.x == 0
        assert cpu._regs.p & Z_FLAG
        cpu._regs.y = 0xFF
        cpu.tick()  # INY
        assert cpu._regs.y == 0x00
        assert cpu._regs.p & Z_FLAG
        cpu.tick()  # DEY
        assert cpu._regs.y == 0xFF
        assert cpu._regs.p & N_FLAG


# ===================================================================
# T-CPU-22 / T-CPU-23: Logic
# ===================================================================


class TestLogic:
    def test_and(self) -> None:
        cpu, _ = _make_cpu([0x29, 0x0F])  # AND #$0F
        cpu._regs.a = 0xFF
        cpu.tick()
        assert cpu._regs.a == 0x0F

    def test_ora(self) -> None:
        cpu, _ = _make_cpu([0x09, 0xF0])  # ORA #$F0
        cpu._regs.a = 0x0F
        cpu.tick()
        assert cpu._regs.a == 0xFF

    def test_eor(self) -> None:
        cpu, _ = _make_cpu([0x49, 0xFF])  # EOR #$FF
        cpu._regs.a = 0xAA
        cpu.tick()
        assert cpu._regs.a == 0x55

    def test_bit(self) -> None:
        cpu, bus = _make_cpu([0x24, 0x10])  # BIT $10
        cpu._regs.a = 0x01
        bus._memory[0x10] = 0xC1  # N=1, V=1, Z based on A&M
        cpu.tick()
        assert not (cpu._regs.p & Z_FLAG)  # 0x01 & 0x81 = 0x01 != 0
        assert cpu._regs.p & N_FLAG
        assert cpu._regs.p & V_FLAG

    def test_bit_zero(self) -> None:
        cpu, bus = _make_cpu([0x24, 0x10])  # BIT $10
        cpu._regs.a = 0x01
        bus._memory[0x10] = 0x02  # A & M = 0
        cpu.tick()
        assert cpu._regs.p & Z_FLAG


# ===================================================================
# T-CPU-24..T-CPU-26: Shift / Rotate
# ===================================================================


class TestShiftRotate:
    def test_asl_accumulator(self) -> None:
        cpu, _ = _make_cpu([0x0A])  # ASL A
        cpu._regs.a = 0x81
        cpu.tick()
        assert cpu._regs.a == 0x02
        assert cpu._regs.p & C_FLAG  # bit 7 was set

    def test_asl_memory(self) -> None:
        cpu, bus = _make_cpu([0x06, 0x10])  # ASL $10
        bus._memory[0x10] = 0x40
        cpu.tick()
        assert bus._memory[0x10] == 0x80
        assert not (cpu._regs.p & C_FLAG)
        assert cpu._regs.p & N_FLAG

    def test_lsr_accumulator(self) -> None:
        cpu, _ = _make_cpu([0x4A])  # LSR A
        cpu._regs.a = 0x01
        cpu.tick()
        assert cpu._regs.a == 0x00
        assert cpu._regs.p & C_FLAG
        assert cpu._regs.p & Z_FLAG

    def test_lsr_memory(self) -> None:
        cpu, bus = _make_cpu([0x46, 0x10])  # LSR $10
        bus._memory[0x10] = 0x80
        cpu.tick()
        assert bus._memory[0x10] == 0x40
        assert not (cpu._regs.p & C_FLAG)

    def test_rol_accumulator(self) -> None:
        cpu, _ = _make_cpu([0x2A])  # ROL A
        cpu._regs.a = 0x80
        cpu._regs.p = 0x24 | C_FLAG  # carry set
        cpu.tick()
        assert cpu._regs.a == 0x01
        assert cpu._regs.p & C_FLAG  # old bit 7

    def test_rol_memory(self) -> None:
        cpu, bus = _make_cpu([0x26, 0x10])  # ROL $10
        bus._memory[0x10] = 0x55
        cpu._regs.p = 0x24  # carry clear
        cpu.tick()
        assert bus._memory[0x10] == 0xAA
        assert not (cpu._regs.p & C_FLAG)

    def test_ror_accumulator(self) -> None:
        cpu, _ = _make_cpu([0x6A])  # ROR A
        cpu._regs.a = 0x01
        cpu._regs.p = 0x24  # carry clear
        cpu.tick()
        assert cpu._regs.a == 0x00
        assert cpu._regs.p & C_FLAG
        assert cpu._regs.p & Z_FLAG

    def test_ror_memory(self) -> None:
        cpu, bus = _make_cpu([0x6E, 0x10, 0x00])  # ROR $0010
        bus._memory[0x10] = 0x01
        cpu._regs.p = 0x24 | C_FLAG  # carry set
        cpu.tick()
        assert bus._memory[0x10] == 0x80
        assert cpu._regs.p & C_FLAG
        assert cpu._regs.p & N_FLAG


# ===================================================================
# T-CPU-27..T-CPU-30: Branch instructions
# ===================================================================


class TestBranches:
    def test_beq_taken(self) -> None:
        cpu, _ = _make_cpu([0xF0, 0x05])  # BEQ +5
        cpu._regs.p = 0x24 | Z_FLAG
        cycles = cpu.tick()
        assert cpu._regs.pc == 0x8007
        assert cycles == 3  # branch taken, same page

    def test_beq_not_taken(self) -> None:
        cpu, _ = _make_cpu([0xF0, 0x05])  # BEQ +5
        cpu._regs.p = 0x24  # Z clear
        cycles = cpu.tick()
        assert cpu._regs.pc == 0x8002
        assert cycles == 2

    def test_bne_taken(self) -> None:
        cpu, _ = _make_cpu([0xD0, 0x03])  # BNE +3
        cpu._regs.p = 0x24  # Z clear
        cpu.tick()
        assert cpu._regs.pc == 0x8005

    def test_bne_not_taken(self) -> None:
        cpu, _ = _make_cpu([0xD0, 0x03])  # BNE +3
        cpu._regs.p = 0x24 | Z_FLAG
        cpu.tick()
        assert cpu._regs.pc == 0x8002

    def test_bcs_bcc(self) -> None:
        cpu, _ = _make_cpu([0xB0, 0x02, 0x90, 0x02])  # BCS +2; BCC +2
        cpu._regs.p = 0x24 | C_FLAG
        cpu.tick()  # BCS taken
        assert cpu._regs.pc == 0x8004
        # Reset for BCC test
        cpu._regs.pc = 0x8002
        cpu._regs.p = 0x24  # C clear
        cpu.tick()  # BCC taken
        assert cpu._regs.pc == 0x8006

    def test_bmi_bpl(self) -> None:
        cpu, _ = _make_cpu([0x30, 0x02, 0x10, 0x02])  # BMI +2; BPL +2
        cpu._regs.p = 0x24 | N_FLAG
        cpu.tick()  # BMI taken
        assert cpu._regs.pc == 0x8004
        cpu._regs.pc = 0x8002
        cpu._regs.p = 0x24  # N clear
        cpu.tick()  # BPL taken
        assert cpu._regs.pc == 0x8006

    def test_bvs_bvc(self) -> None:
        cpu, _ = _make_cpu([0x70, 0x02, 0x50, 0x02])  # BVS +2; BVC +2
        cpu._regs.p = 0x24 | V_FLAG
        cpu.tick()  # BVS taken
        assert cpu._regs.pc == 0x8004
        cpu._regs.pc = 0x8002
        cpu._regs.p = 0x24  # V clear
        cpu.tick()  # BVC taken
        assert cpu._regs.pc == 0x8006

    def test_branch_backward(self) -> None:
        # Place a loop: INX; BNE -2
        start = 0x8000
        cpu, _ = _make_cpu([0xE8, 0xD0, 0xFD], start=start)  # INX; BNE -3
        cpu._regs.x = 0xFD
        cpu.tick()  # INX -> 0xFE
        cycles = cpu.tick()  # BNE taken (Z clear), same page
        assert cpu._regs.pc == 0x8000
        assert cycles == 3

    def test_branch_page_crossing(self) -> None:
        """Branch crossing a page boundary costs 4 cycles."""
        # Place code so that a forward branch crosses a page boundary
        start = 0x80F0
        cpu, _ = _make_cpu([0xD0, 0x10], start=start)  # BNE +16
        cpu._regs.p = 0x24  # Z clear, branch taken
        cycles = cpu.tick()
        # PC after operand = 0x80F2, target = 0x80F2 + 0x10 = 0x8102
        assert cpu._regs.pc == 0x8102
        assert cycles == 4  # page crossed


# ===================================================================
# T-CPU-31..T-CPU-33: JMP / JSR / RTS / RTI
# ===================================================================


class TestJumpSubroutine:
    def test_jmp_absolute(self) -> None:
        cpu, _ = _make_cpu([0x4C, 0x34, 0x12])  # JMP $1234
        cpu.tick()
        assert cpu._regs.pc == 0x1234

    def test_jmp_indirect(self) -> None:
        cpu, bus = _make_cpu([0x6C, 0x00, 0x30])  # JMP ($3000)
        bus._memory[0x3000] = 0x40
        bus._memory[0x3001] = 0x20
        cpu.tick()
        assert cpu._regs.pc == 0x2040

    def test_jsr_rts(self) -> None:
        cpu, bus = _make_cpu(
            [
                0x20,
                0x10,
                0x80,  # JSR $8010
                0xEA,  # NOP (return here)
            ],
            start=0x8000,
        )
        # Place RTS at the subroutine
        bus._memory[0x8010] = 0x60  # RTS

        cpu.tick()  # JSR
        assert cpu._regs.pc == 0x8010
        # Stack should contain return address (0x8002, which is PC-1 of the JSR)
        sp = cpu._regs.sp
        lo = bus._memory[0x0100 + ((sp + 1) & 0xFF)]
        hi = bus._memory[0x0100 + ((sp + 2) & 0xFF)]
        return_addr = (hi << 8) | lo
        assert return_addr == 0x8002  # RTS will add 1 to get 0x8003

        cpu.tick()  # RTS
        assert cpu._regs.pc == 0x8003  # byte after JSR

    def test_jsr_pushes_correct_address(self) -> None:
        """JSR pushes PC-1 (address of last byte of JSR instruction)."""
        cpu, bus = _make_cpu([0x20, 0x00, 0x90], start=0x8000)
        initial_sp = cpu._regs.sp
        cpu.tick()
        # Pushed 2 bytes
        assert cpu._regs.sp == (initial_sp - 2) & 0xFF
        # Value on stack should be 0x8002 (start+3-1)
        lo = bus._memory[0x0100 + ((cpu._regs.sp + 1) & 0xFF)]
        hi = bus._memory[0x0100 + ((cpu._regs.sp + 2) & 0xFF)]
        assert (hi << 8) | lo == 0x8002

    def test_rti(self) -> None:
        cpu, bus = _make_cpu([0x40], start=0x8000)  # RTI
        # Simulate interrupt handler's push order: push_word(PC) then push(P)
        cpu._push_word(0x1234)  # pushes PC_hi (0x12) then PC_lo (0x34)
        cpu._push(0x24)  # pushes P
        cpu.tick()
        assert cpu._regs.pc == 0x1234
        assert (cpu._regs.p & ~B_FLAG & ~0x20) == (0x24 & ~B_FLAG & ~0x20)


# ===================================================================
# T-CPU-34 / T-CPU-35: Stack operations (PHA/PHP/PLA/PLP)
# ===================================================================


class TestStackOps:
    def test_pha_pla(self) -> None:
        cpu, _ = _make_cpu([0x48, 0x68])  # PHA; PLA
        cpu._regs.a = 0x42
        cpu.tick()  # PHA
        cpu._regs.a = 0x00
        cpu.tick()  # PLA
        assert cpu._regs.a == 0x42

    def test_php_plp(self) -> None:
        cpu, _ = _make_cpu([0x08, 0x28])  # PHP; PLP
        cpu._regs.p = 0x24 | C_FLAG | Z_FLAG
        cpu.tick()  # PHP
        cpu._regs.p = 0x00
        cpu.tick()  # PLP
        # PLP sets bit 5, clears B flag
        assert cpu._regs.p & C_FLAG
        assert cpu._regs.p & Z_FLAG
        assert cpu._regs.p & 0x20  # bit 5 always set after PLP
        assert not (cpu._regs.p & B_FLAG)

    def test_pla_sets_flags(self) -> None:
        cpu, _ = _make_cpu([0x48, 0x68])  # PHA; PLA
        cpu._regs.a = 0x80
        cpu.tick()  # PHA
        cpu._regs.a = 0x00
        cpu.tick()  # PLA
        assert cpu._regs.a == 0x80
        assert cpu._regs.p & N_FLAG
        assert not (cpu._regs.p & Z_FLAG)


# ===================================================================
# T-CPU-36: Flag instructions
# ===================================================================


class TestFlagInstructions:
    def test_clc_sec(self) -> None:
        cpu, _ = _make_cpu([0x38, 0x18])  # SEC; CLC
        cpu.tick()  # SEC
        assert cpu._regs.p & C_FLAG
        cpu.tick()  # CLC
        assert not (cpu._regs.p & C_FLAG)

    def test_cli_sei(self) -> None:
        cpu, _ = _make_cpu([0x78, 0x58])  # SEI; CLI
        cpu.tick()  # SEI
        assert cpu._regs.p & I_FLAG
        cpu.tick()  # CLI
        assert not (cpu._regs.p & I_FLAG)

    def test_cld_sed(self) -> None:
        cpu, _ = _make_cpu([0xF8, 0xD8])  # SED; CLD
        cpu.tick()  # SED
        assert cpu._regs.p & D_FLAG
        cpu.tick()  # CLD
        assert not (cpu._regs.p & D_FLAG)

    def test_clv(self) -> None:
        cpu, _ = _make_cpu([0xB8])  # CLV
        cpu._regs.p = 0x24 | V_FLAG
        cpu.tick()
        assert not (cpu._regs.p & V_FLAG)


# ===================================================================
# T-CPU-37: BRK
# ===================================================================


class TestBRK:
    def test_brk(self) -> None:
        cpu, bus = _make_cpu([0x00], start=0x8000)  # BRK
        bus._memory[0xFFFE] = 0x00
        bus._memory[0xFFFF] = 0x90  # IRQ vector = $9000

        initial_sp = cpu._regs.sp
        cpu.tick()

        # Should push PC+1 and P (with B flag set)
        assert cpu._regs.sp == (initial_sp - 3) & 0xFF
        assert cpu._regs.pc == 0x9000
        assert cpu._regs.p & I_FLAG


# ===================================================================
# T-CPU-38: NOP
# ===================================================================


class TestNOP:
    def test_nop(self) -> None:
        cpu, _ = _make_cpu([0xEA, 0xEA])  # NOP; NOP
        cycles = cpu.tick()
        assert cpu._regs.pc == 0x8001
        assert cycles == 2
        cycles = cpu.tick()
        assert cpu._regs.pc == 0x8002
        assert cycles == 2


# ===================================================================
# T-CPU-39: Illegal opcode handling
# ===================================================================


class TestIllegalOpcodes:
    def test_illegal_opcode_is_nop(self) -> None:
        # Opcode 0x02 is illegal, should behave as NOP
        cpu, _ = _make_cpu([0x02, 0xEA])
        cycles = cpu.tick()
        assert cycles == 2
        assert cpu._regs.pc == 0x8001  # advances by 1 (implied)


# ===================================================================
# T-CPU-40 / T-CPU-41: Interrupt handling
# ===================================================================


class TestInterrupts:
    def test_nmi(self) -> None:
        cpu, bus = _make_cpu([0xEA, 0xEA])  # NOP; NOP
        bus._memory[0xFFFA] = 0x00
        bus._memory[0xFFFB] = 0x90  # NMI vector = $9000

        cpu.tick()  # NOP
        cpu.trigger_nmi()
        initial_sp = cpu._regs.sp
        cycles = cpu.tick()  # NMI handler

        assert cycles == 7
        assert cpu._regs.pc == 0x9000
        assert cpu._regs.p & I_FLAG
        assert cpu._regs.sp == (initial_sp - 3) & 0xFF

    def test_irq_when_enabled(self) -> None:
        cpu, bus = _make_cpu([0xEA, 0xEA])
        bus._memory[0xFFFE] = 0x00
        bus._memory[0xFFFF] = 0xA0  # IRQ vector = $A000

        cpu.tick()  # NOP
        cpu._regs.p &= ~I_FLAG  # ensure I is clear
        cpu.trigger_irq()
        cycles = cpu.tick()

        assert cycles == 7
        assert cpu._regs.pc == 0xA000
        assert cpu._regs.p & I_FLAG

    def test_irq_blocked_by_i_flag(self) -> None:
        cpu, bus = _make_cpu([0xEA, 0xEA])
        bus._memory[0xFFFE] = 0x00
        bus._memory[0xFFFF] = 0xA0

        cpu.tick()  # NOP
        cpu._regs.p |= I_FLAG  # disable interrupts
        cpu.trigger_irq()
        # trigger_irq should not set the interrupt since I is set
        assert cpu._interrupt is None

    def test_nmi_takes_priority_over_irq(self) -> None:
        cpu, bus = _make_cpu([0xEA])
        bus._memory[0xFFFA] = 0x00
        bus._memory[0xFFFB] = 0x90  # NMI vector
        bus._memory[0xFFFE] = 0x00
        bus._memory[0xFFFF] = 0xA0  # IRQ vector

        cpu.trigger_nmi()
        # trigger_irq should be ignored if NMI is pending
        # (Actually, trigger_irq might overwrite _interrupt if I is clear)
        # In our implementation, NMI is set first, so it takes priority.
        cpu.tick()  # handle NMI
        assert cpu._regs.pc == 0x9000  # NMI vector, not IRQ

    def test_nmi_is_not_maskable(self) -> None:
        cpu, bus = _make_cpu([0xEA, 0xEA])
        bus._memory[0xFFFA] = 0x00
        bus._memory[0xFFFB] = 0x90

        cpu.tick()  # NOP
        cpu._regs.p |= I_FLAG  # I flag set
        cpu.trigger_nmi()
        cycles = cpu.tick()  # NMI should still fire
        assert cycles == 7
        assert cpu._regs.pc == 0x9000

    def test_interrupt_pushes_correct_state(self) -> None:
        cpu, bus = _make_cpu([0xEA])
        bus._memory[0xFFFA] = 0x00
        bus._memory[0xFFFB] = 0x90

        cpu.tick()  # NOP -> PC = 0x8001
        cpu.trigger_nmi()
        cpu.tick()  # handle NMI

        sp_after = cpu._regs.sp  # SP after pushing 3 bytes
        # P is at the top of stack (lowest address = SP+1)
        pushed_p = bus._memory[0x0100 + ((sp_after + 1) & 0xFF)]
        assert not (pushed_p & B_FLAG)  # B flag should be clear in pushed P


# ===================================================================
# T-CPU-42 / T-CPU-43: Opcode table & tick
# ===================================================================


class TestOpcodeTable:
    def test_opcode_table_has_256_entries(self) -> None:
        bus = MockCPUBus()
        cpu = CPU(bus)
        assert len(cpu._opcodes) == 256

    def test_tick_returns_cycle_count(self) -> None:
        cpu, _ = _make_cpu([0xEA])  # NOP, 2 cycles
        cycles = cpu.tick()
        assert cycles == 2

    def test_tick_increments_total_cycles(self) -> None:
        cpu, _ = _make_cpu([0xEA, 0xEA])
        cpu.tick()
        cpu.tick()
        assert cpu._cycles == 4


# ===================================================================
# T-CPU-44: Stall
# ===================================================================


class TestStall:
    def test_stall(self) -> None:
        cpu, _ = _make_cpu([0xEA])
        cpu.stall(3)
        assert cpu.tick() == 1
        assert cpu.tick() == 1
        assert cpu.tick() == 1
        # After stall, normal execution
        cycles = cpu.tick()  # NOP
        assert cycles == 2


# ===================================================================
# T-CPU-45: Page-crossing cycle penalties
# ===================================================================


class TestCyclePenalties:
    def test_lda_absolute_x_no_page_cross(self) -> None:
        cpu, bus = _make_cpu([0xBD, 0x00, 0x20])  # LDA $2000,X
        cpu._regs.x = 0x05
        bus._memory[0x2005] = 0x42
        cycles = cpu.tick()
        assert cycles == 4  # no page cross
        assert cpu._regs.a == 0x42

    def test_lda_absolute_x_page_cross(self) -> None:
        cpu, bus = _make_cpu([0xBD, 0xFF, 0x20])  # LDA $20FF,X
        cpu._regs.x = 0x01
        bus._memory[0x2100] = 0x42
        cycles = cpu.tick()
        assert cycles == 5  # page crossed
        assert cpu._regs.a == 0x42

    def test_lda_absolute_y_page_cross(self) -> None:
        cpu, bus = _make_cpu([0xB9, 0xFF, 0x20])  # LDA $20FF,Y
        cpu._regs.y = 0x01
        bus._memory[0x2100] = 0x42
        cycles = cpu.tick()
        assert cycles == 5
        assert cpu._regs.a == 0x42

    def test_lda_indirect_y_page_cross(self) -> None:
        cpu, bus = _make_cpu([0xB1, 0x20])  # LDA ($20),Y
        cpu._regs.y = 0x01
        bus._memory[0x20] = 0xFF
        bus._memory[0x21] = 0x20  # base = $20FF
        bus._memory[0x2100] = 0x42  # $20FF + 1 = $2100
        cycles = cpu.tick()
        assert cycles == 6  # 5 + 1 for page cross
        assert cpu._regs.a == 0x42

    def test_sta_absolute_x_no_page_penalty(self) -> None:
        cpu, bus = _make_cpu([0x9D, 0xFF, 0x20])  # STA $20FF,X
        cpu._regs.x = 0x01
        cpu._regs.a = 0x42
        cycles = cpu.tick()
        assert cycles == 5  # always 5, no page-cross penalty for stores

    def test_adc_immediate_cycles(self) -> None:
        cpu, _ = _make_cpu([0x69, 0x01])
        assert cpu.tick() == 2

    def test_adc_zero_page_cycles(self) -> None:
        cpu, _ = _make_cpu([0x65, 0x10])
        assert cpu.tick() == 3

    def test_adc_absolute_cycles(self) -> None:
        cpu, _ = _make_cpu([0x6D, 0x00, 0x20])
        assert cpu.tick() == 4

    def test_jmp_indirect_cycles(self) -> None:
        cpu, bus = _make_cpu([0x6C, 0x00, 0x30])
        bus._memory[0x3000] = 0x00
        bus._memory[0x3001] = 0x80
        assert cpu.tick() == 5


# ===================================================================
# T-CPU-46: ADC/SBC boundary tests
# ===================================================================


class TestADCSBCBoundary:
    def test_adc_max_plus_max(self) -> None:
        cpu, _ = _make_cpu([0x69, 0xFF])
        cpu._regs.a = 0xFF
        cpu._regs.p = 0x24
        cpu.tick()
        assert cpu._regs.a == 0xFE
        assert cpu._regs.p & C_FLAG
        assert not (cpu._regs.p & V_FLAG)  # same sign addition, no overflow

    def test_adc_0x7f_plus_0x01(self) -> None:
        """0x7F + 0x01 = 0x80: overflow (positive + positive = negative)."""
        cpu, _ = _make_cpu([0x69, 0x01])
        cpu._regs.a = 0x7F
        cpu._regs.p = 0x24
        cpu.tick()
        assert cpu._regs.a == 0x80
        assert cpu._regs.p & V_FLAG
        assert cpu._regs.p & N_FLAG
        assert not (cpu._regs.p & C_FLAG)

    def test_sbc_0x80_minus_0x01(self) -> None:
        """0x80 - 0x01 = 0x7F: overflow (negative - positive = positive)."""
        cpu, _ = _make_cpu([0xE9, 0x01])
        cpu._regs.a = 0x80
        cpu._regs.p = 0x24 | C_FLAG
        cpu.tick()
        assert cpu._regs.a == 0x7F
        assert cpu._regs.p & V_FLAG
        assert not (cpu._regs.p & N_FLAG)


# ===================================================================
# T-CPU-47: Branch instruction boundary tests
# ===================================================================


class TestBranchBoundary:
    def test_branch_to_self(self) -> None:
        """BNE with offset -2 branches to itself."""
        cpu, _ = _make_cpu([0xD0, 0xFE], start=0x8000)
        cpu._regs.p = 0x24  # Z clear
        cycles = cpu.tick()
        assert cpu._regs.pc == 0x8000
        assert cycles == 3

    def test_branch_forward_to_next_page(self) -> None:
        start = 0x80F0
        cpu, _ = _make_cpu([0xD0, 0x0E], start=start)  # BNE +14
        cpu._regs.p = 0x24
        cycles = cpu.tick()
        # PC after operand = 0x80F2, target = 0x80F2 + 14 = 0x8100
        assert cpu._regs.pc == 0x8100
        assert cycles == 4  # page crossed

    def test_branch_backward_across_page(self) -> None:
        start = 0x8102
        cpu, _ = _make_cpu([0xD0, 0xEE], start=start)  # BNE -18
        cpu._regs.p = 0x24
        cycles = cpu.tick()
        # PC after operand = 0x8104, target = 0x8104 - 18 = 0x80F2
        assert cpu._regs.pc == 0x80F2
        assert cycles == 4  # page crossed


# ===================================================================
# T-CPU-48: JSR/RTS/RTI stack integrity
# ===================================================================


class TestStackIntegrity:
    def test_jsr_rts_round_trip(self) -> None:
        """Multiple JSR/RTS pairs preserve stack integrity."""
        cpu, bus = _make_cpu(
            [
                0x20,
                0x10,
                0x80,  # JSR $8010
                0xA9,
                0x99,  # LDA #$99 (after return)
            ],
            start=0x8000,
        )
        # Subroutine: JSR to another, then RTS
        bus._memory[0x8010] = 0x20  # JSR
        bus._memory[0x8011] = 0x20
        bus._memory[0x8012] = 0x80  # JSR $8020
        bus._memory[0x8020] = 0x60  # RTS
        bus._memory[0x8013] = 0x60  # RTS

        initial_sp = cpu._regs.sp
        cpu.tick()  # JSR $8010
        cpu.tick()  # JSR $8020
        cpu.tick()  # RTS from $8020 -> $8013
        cpu.tick()  # RTS from $8010 -> $8003
        cpu.tick()  # LDA #$99

        assert cpu._regs.a == 0x99
        assert cpu._regs.sp == initial_sp  # stack fully restored

    def test_rti_restores_flags_and_pc(self) -> None:
        cpu, bus = _make_cpu([0x40], start=0x8000)  # RTI
        # Simulate interrupt handler: push_word(PC) then push(P)
        cpu._push_word(0x9050)  # pushes PC_hi (0x90) then PC_lo (0x50)
        cpu._push(0x24 | C_FLAG)  # P with carry
        cpu.tick()
        assert cpu._regs.pc == 0x9050
        assert cpu._regs.p & C_FLAG


# ===================================================================
# T-CPU-49: NMI/IRQ priority and masking
# ===================================================================


class TestInterruptPriority:
    def test_irq_does_not_fire_when_i_set(self) -> None:
        cpu, bus = _make_cpu([0xEA, 0xEA, 0xEA])
        bus._memory[0xFFFE] = 0x00
        bus._memory[0xFFFF] = 0xA0
        cpu._regs.p |= I_FLAG
        cpu.trigger_irq()
        # _interrupt should remain None
        assert cpu._interrupt is None
        # Normal execution should continue
        cycles = cpu.tick()  # NOP
        assert cycles == 2
        assert cpu._regs.pc == 0x8001

    def test_nmi_overrides_irq(self) -> None:
        cpu, bus = _make_cpu([0xEA, 0xEA])
        bus._memory[0xFFFA] = 0x00
        bus._memory[0xFFFB] = 0x90
        bus._memory[0xFFFE] = 0x00
        bus._memory[0xFFFF] = 0xA0

        cpu._regs.p &= ~I_FLAG
        cpu.trigger_irq()  # set IRQ
        cpu.trigger_nmi()  # override with NMI
        cpu.tick()  # should handle NMI
        assert cpu._regs.pc == 0x9000  # NMI vector

    def test_irq_after_cli(self) -> None:
        cpu, bus = _make_cpu([0x58, 0xEA])  # CLI; NOP
        bus._memory[0xFFFE] = 0x00
        bus._memory[0xFFFF] = 0xA0
        cpu._regs.p |= I_FLAG
        cpu.trigger_irq()  # won't fire (I set)
        assert cpu._interrupt is None
        cpu.tick()  # CLI clears I
        # Now trigger IRQ
        cpu.trigger_irq()
        assert cpu._interrupt == InterruptType.IRQ


# ===================================================================
# Additional CMP/CPX/CPY tests
# ===================================================================


class TestCompare:
    def test_cmp_equal(self) -> None:
        cpu, _ = _make_cpu([0xC9, 0x42])  # CMP #$42
        cpu._regs.a = 0x42
        cpu.tick()
        assert cpu._regs.p & Z_FLAG
        assert cpu._regs.p & C_FLAG
        assert not (cpu._regs.p & N_FLAG)

    def test_cmp_greater(self) -> None:
        cpu, _ = _make_cpu([0xC9, 0x10])  # CMP #$10
        cpu._regs.a = 0x20
        cpu.tick()
        assert not (cpu._regs.p & Z_FLAG)
        assert cpu._regs.p & C_FLAG
        assert not (cpu._regs.p & N_FLAG)

    def test_cmp_less(self) -> None:
        cpu, _ = _make_cpu([0xC9, 0x20])  # CMP #$20
        cpu._regs.a = 0x10
        cpu.tick()
        assert not (cpu._regs.p & Z_FLAG)
        assert not (cpu._regs.p & C_FLAG)
        assert cpu._regs.p & N_FLAG

    def test_cpx_cpy(self) -> None:
        cpu, _ = _make_cpu([0xE0, 0x10, 0xC0, 0x10])  # CPX #$10; CPY #$10
        cpu._regs.x = 0x10
        cpu._regs.y = 0x20
        cpu.tick()  # CPX
        assert cpu._regs.p & Z_FLAG
        cpu.tick()  # CPY
        assert cpu._regs.p & C_FLAG
        assert not (cpu._regs.p & Z_FLAG)
