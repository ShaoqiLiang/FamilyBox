"""Tests for the Bus module (CPUBus and PPUBus)."""

from unittest.mock import MagicMock


from familybox.bus.cpu_bus import CPUBus
from familybox.bus.ppu_bus import PPUBus
from familybox.types import Mirroring


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_ppu() -> MagicMock:
    ppu = MagicMock()
    ppu.read_register.return_value = 0
    ppu.write_register.return_value = None
    return ppu


def _make_mock_apu() -> MagicMock:
    apu = MagicMock()
    apu.write_register.return_value = None
    return apu


def _make_mock_mapper() -> MagicMock:
    mapper = MagicMock()
    mapper.cpu_read.return_value = 0
    mapper.cpu_write.return_value = None
    mapper.ppu_read.return_value = 0
    mapper.ppu_write.return_value = None
    return mapper


def _make_mock_controller() -> MagicMock:
    controller = MagicMock()
    controller.read.return_value = 0
    controller.write.return_value = None
    return controller


def _make_cpu_bus() -> tuple[CPUBus, MagicMock, MagicMock, MagicMock, MagicMock]:
    ppu = _make_mock_ppu()
    apu = _make_mock_apu()
    mapper = _make_mock_mapper()
    controller = _make_mock_controller()
    bus = CPUBus(ppu, apu, mapper, controller)
    return bus, ppu, apu, mapper, controller


# ===========================================================================
# CPUBus tests
# ===========================================================================


class TestCPUBusRAM:
    """T-BUS-02, T-BUS-06: RAM read/write with mirroring."""

    def test_ram_read_write(self) -> None:
        bus, *_ = _make_cpu_bus()
        bus.write(0x0000, 0x42)
        assert bus.read(0x0000) == 0x42

    def test_ram_full_range(self) -> None:
        bus, *_ = _make_cpu_bus()
        bus.write(0x07FF, 0xAB)
        assert bus.read(0x07FF) == 0xAB

    def test_ram_mirror_0800(self) -> None:
        """$0800 mirrors $0000."""
        bus, *_ = _make_cpu_bus()
        bus.write(0x0000, 0x11)
        assert bus.read(0x0800) == 0x11

    def test_ram_mirror_1000(self) -> None:
        """$1000 mirrors $0000."""
        bus, *_ = _make_cpu_bus()
        bus.write(0x0000, 0x22)
        assert bus.read(0x1000) == 0x22

    def test_ram_mirror_1800(self) -> None:
        """$1800 mirrors $0000."""
        bus, *_ = _make_cpu_bus()
        bus.write(0x0000, 0x33)
        assert bus.read(0x1800) == 0x33

    def test_ram_mirror_1fff(self) -> None:
        """$1FFF mirrors $07FF."""
        bus, *_ = _make_cpu_bus()
        bus.write(0x07FF, 0x44)
        assert bus.read(0x1FFF) == 0x44

    def test_ram_write_through_mirror(self) -> None:
        """Writing to mirror address updates the original."""
        bus, *_ = _make_cpu_bus()
        bus.write(0x0800, 0x55)
        assert bus.read(0x0000) == 0x55

    def test_ram_default_zero(self) -> None:
        bus, *_ = _make_cpu_bus()
        assert bus.read(0x0100) == 0


class TestCPUBusPPU:
    """T-BUS-03, T-BUS-07: PPU register routing."""

    def test_read_ppu_register(self) -> None:
        bus, ppu, *_ = _make_cpu_bus()
        ppu.read_register.return_value = 0x80
        result = bus.read(0x2002)
        ppu.read_register.assert_called_once_with(0x2002)
        assert result == 0x80

    def test_write_ppu_register(self) -> None:
        bus, ppu, *_ = _make_cpu_bus()
        bus.write(0x2000, 0x80)
        ppu.write_register.assert_called_once_with(0x2000, 0x80)

    def test_ppu_mirror_2008(self) -> None:
        """$2008 mirrors $2000."""
        bus, ppu, *_ = _make_cpu_bus()
        bus.read(0x2008)
        ppu.read_register.assert_called_once_with(0x2000)

    def test_ppu_mirror_3FFF(self) -> None:
        """$3FFF mirrors $2007."""
        bus, ppu, *_ = _make_cpu_bus()
        bus.read(0x3FFF)
        ppu.read_register.assert_called_once_with(0x2007)

    def test_ppu_write_mirror(self) -> None:
        """Writing $2008 routes to $2000."""
        bus, ppu, *_ = _make_cpu_bus()
        bus.write(0x2008, 0x01)
        ppu.write_register.assert_called_once_with(0x2000, 0x01)


class TestCPUBusController:
    """T-BUS-04: Controller read/write."""

    def test_read_controller_1(self) -> None:
        bus, _, _, _, controller = _make_cpu_bus()
        controller.read.return_value = 1
        assert bus.read(0x4016) == 1
        controller.read.assert_called_once()

    def test_read_controller_2(self) -> None:
        """$4017 (controller 2) returns 0 (not supported)."""
        bus, *_ = _make_cpu_bus()
        assert bus.read(0x4017) == 0

    def test_write_controller(self) -> None:
        bus, _, _, _, controller = _make_cpu_bus()
        bus.write(0x4016, 0x01)
        controller.write.assert_called_once_with(0x01)


class TestCPUBusAPU:
    """T-BUS-10: APU register write routing."""

    def test_write_apu_register(self) -> None:
        bus, _, apu, *_ = _make_cpu_bus()
        bus.write(0x4000, 0x10)
        apu.write_register.assert_called_once_with(0x4000, 0x10)

    def test_write_apu_4017(self) -> None:
        """$4017 is within APU range."""
        bus, _, apu, *_ = _make_cpu_bus()
        bus.write(0x4017, 0x20)
        apu.write_register.assert_called_once_with(0x4017, 0x20)

    def test_read_apu_returns_zero(self) -> None:
        """APU registers ($4000-$4017) are write-only; reads return 0."""
        bus, *_ = _make_cpu_bus()
        assert bus.read(0x4000) == 0

    def test_write_apu_4015(self) -> None:
        bus, _, apu, *_ = _make_cpu_bus()
        bus.write(0x4015, 0x0F)
        apu.write_register.assert_called_once_with(0x4015, 0x0F)


class TestCPUBusMapper:
    """T-BUS-05, T-BUS-11: Mapper region routing."""

    def test_read_mapper(self) -> None:
        bus, _, _, mapper, _ = _make_cpu_bus()
        mapper.cpu_read.return_value = 0xEA
        assert bus.read(0x8000) == 0xEA
        mapper.cpu_read.assert_called_once_with(0x8000)

    def test_write_mapper(self) -> None:
        bus, _, _, mapper, _ = _make_cpu_bus()
        bus.write(0x8000, 0x42)
        mapper.cpu_write.assert_called_once_with(0x8000, 0x42)

    def test_read_mapper_4020(self) -> None:
        """$4020 is the start of the mapper region."""
        bus, _, _, mapper, _ = _make_cpu_bus()
        bus.read(0x4020)
        mapper.cpu_read.assert_called_once_with(0x4020)

    def test_read_mapper_FFFF(self) -> None:
        bus, _, _, mapper, _ = _make_cpu_bus()
        bus.read(0xFFFF)
        mapper.cpu_read.assert_called_once_with(0xFFFF)


class TestCPUBusOamDma:
    """T-BUS-08, T-BUS-12: OAM DMA."""

    def test_oam_dma(self) -> None:
        bus, ppu, _, _, _ = _make_cpu_bus()
        # Write known values to RAM at page $02
        for i in range(256):
            bus.write(0x0200 + i, i & 0xFF)

        bus.write(0x4014, 0x02)  # DMA from page $0200

        assert ppu.write_register.call_count == 256

        # Verify each byte was written to OAMDATA ($2004)
        for call in ppu.write_register.call_args_list:
            assert call[0][0] == 0x2004

    def test_oam_dma_value_masking(self) -> None:
        bus, ppu, _, _, _ = _make_cpu_bus()
        bus.write(0x4014, 0x00)
        assert ppu.write_register.call_count == 256


class TestCPUBusAddrMasking:
    """Address and value masking."""

    def test_addr_masked_to_16bit(self) -> None:
        """Addresses above $FFFF wrap."""
        bus, _, _, mapper, _ = _make_cpu_bus()
        bus.read(0x1_8000)  # should wrap to $8000
        mapper.cpu_read.assert_called_once_with(0x8000)

    def test_write_value_masked_to_8bit(self) -> None:
        bus, *_ = _make_cpu_bus()
        bus.write(0x0000, 0x1FF)
        assert bus.read(0x0000) == 0xFF


# ===========================================================================
# PPUBus tests
# ===========================================================================


def _make_ppu_bus(
    mirroring: Mirroring = Mirroring.VERTICAL,
) -> tuple[PPUBus, MagicMock]:
    mapper = _make_mock_mapper()
    bus = PPUBus(mapper, mirroring)
    return bus, mapper


class TestPPUBusPatternTable:
    """T-BUS-15: Pattern Table routing ($0000-$1FFF)."""

    def test_read_pattern_table(self) -> None:
        bus, mapper = _make_ppu_bus()
        mapper.ppu_read.return_value = 0x42
        assert bus.read(0x0000) == 0x42
        mapper.ppu_read.assert_called_once_with(0x0000)

    def test_write_pattern_table(self) -> None:
        bus, mapper = _make_ppu_bus()
        bus.write(0x1000, 0x55)
        mapper.ppu_write.assert_called_once_with(0x1000, 0x55)

    def test_read_pattern_table_end(self) -> None:
        bus, mapper = _make_ppu_bus()
        bus.read(0x1FFF)
        mapper.ppu_read.assert_called_once_with(0x1FFF)


class TestPPUBusNametable:
    """T-BUS-16: Nametable read/write ($2000-$2FFF)."""

    def test_nametable_read_write(self) -> None:
        bus, _ = _make_ppu_bus()
        bus.write(0x2000, 0xAA)
        assert bus.read(0x2000) == 0xAA

    def test_nametable_2FFF(self) -> None:
        bus, _ = _make_ppu_bus()
        bus.write(0x2FFF, 0xBB)
        assert bus.read(0x2FFF) == 0xBB


class TestPPUBusNametableMirror:
    """T-BUS-19: Nametable mirroring."""

    def test_vertical_mirror(self) -> None:
        """Vertical mirroring: $2000 == $2400, $2800 == $2C00."""
        bus, _ = _make_ppu_bus(Mirroring.VERTICAL)
        bus.write(0x2000, 0x11)
        assert bus.read(0x2400) == 0x11

        bus.write(0x2800, 0x22)
        assert bus.read(0x2C00) == 0x22

    def test_vertical_mirror_independent(self) -> None:
        """In vertical mode, $2000 and $2800 are independent."""
        bus, _ = _make_ppu_bus(Mirroring.VERTICAL)
        bus.write(0x2000, 0x11)
        bus.write(0x2800, 0x22)
        assert bus.read(0x2000) == 0x11
        assert bus.read(0x2800) == 0x22

    def test_horizontal_mirror(self) -> None:
        """Horizontal mirroring: $2000 == $2400, $2800 == $2C00."""
        bus, _ = _make_ppu_bus(Mirroring.HORIZONTAL)
        bus.write(0x2000, 0x33)
        assert bus.read(0x2400) == 0x33

        bus.write(0x2800, 0x44)
        assert bus.read(0x2C00) == 0x44

    def test_horizontal_mirror_independent(self) -> None:
        """In horizontal mode, $2000 and $2800 are independent."""
        bus, _ = _make_ppu_bus(Mirroring.HORIZONTAL)
        bus.write(0x2000, 0x33)
        bus.write(0x2800, 0x44)
        assert bus.read(0x2000) == 0x33
        assert bus.read(0x2800) == 0x44

    def test_nametable_mirror_3000(self) -> None:
        """$3000-$3EFF mirrors $2000-$2EFF."""
        bus, _ = _make_ppu_bus(Mirroring.VERTICAL)
        bus.write(0x2000, 0x55)
        assert bus.read(0x3000) == 0x55

    def test_nametable_offset_within_table(self) -> None:
        """Offsets within a nametable are preserved."""
        bus, _ = _make_ppu_bus(Mirroring.VERTICAL)
        bus.write(0x2010, 0x77)
        assert bus.read(0x2010) == 0x77
        assert bus.read(0x2410) == 0x77  # $2400 mirrors $2000 in vertical


class TestPPUBusPalette:
    """T-BUS-17, T-BUS-20: Palette RAM and transparency mirror."""

    def test_palette_read_write(self) -> None:
        bus, _ = _make_ppu_bus()
        bus.write(0x3F00, 0x10)
        assert bus.read(0x3F00) == 0x10

    def test_palette_non_transparent(self) -> None:
        """Addresses not divisible by 4 are independent entries."""
        bus, _ = _make_ppu_bus()
        bus.write(0x3F01, 0x20)
        bus.write(0x3F02, 0x30)
        bus.write(0x3F03, 0x40)
        assert bus.read(0x3F01) == 0x20
        assert bus.read(0x3F02) == 0x30
        assert bus.read(0x3F03) == 0x40

    def test_palette_transparency_mirror(self) -> None:
        """All palette entries at offset % 4 == 0 mirror the background colour."""
        bus, _ = _make_ppu_bus()
        bus.write(0x3F00, 0x10)
        # $3F04, $3F08, $3F0C, ... all mirror $3F00
        assert bus.read(0x3F04) == 0x10
        assert bus.read(0x3F08) == 0x10
        assert bus.read(0x3F0C) == 0x10

    def test_palette_spr_transparency_mirror(self) -> None:
        """Sprite palette transparency entries mirror the bg palette entry."""
        bus, _ = _make_ppu_bus()
        bus.write(0x3F00, 0x10)
        # $3F10 mirrors $3F00
        assert bus.read(0x3F10) == 0x10
        # $3F14 mirrors $3F00
        assert bus.read(0x3F14) == 0x10

    def test_palette_full_range(self) -> None:
        """Palette RAM covers $3F00-$3FFF."""
        bus, _ = _make_ppu_bus()
        bus.write(0x3FFF, 0x55)
        # $3FFF -> (0x3FFF - 0x3F00) % 0x20 = 0x1F, 0x1F % 4 = 3 -> index 0x1F
        assert bus.read(0x3FFF) == 0x55

    def test_palette_write_transparency_mirror(self) -> None:
        """Writing to a transparency-mirrored address updates index 0."""
        bus, _ = _make_ppu_bus()
        bus.write(0x3F04, 0x66)
        assert bus.read(0x3F00) == 0x66


class TestPPUBusAddrMasking:
    """PPU address masking."""

    def test_addr_masked_to_14bit(self) -> None:
        """Addresses above $3FFF wrap."""
        bus, mapper = _make_ppu_bus()
        bus.read(0x7FFF)  # wraps to $3FFF -> palette range
        # $3FFF is in palette range, not mapper
        # So ppu_read should NOT be called
        mapper.ppu_read.assert_not_called()

    def test_write_value_masked_to_8bit(self) -> None:
        bus, _ = _make_ppu_bus()
        bus.write(0x2000, 0x1FF)
        assert bus.read(0x2000) == 0xFF
