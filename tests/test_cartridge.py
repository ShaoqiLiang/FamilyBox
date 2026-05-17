"""Tests for the cartridge module."""

import pytest

from familybox.cartridge.mapper import Mapper0
from familybox.cartridge.rom import ROMLoader
from familybox.types import MapperInterface, Mirroring


# ---------------------------------------------------------------------------
# Mapper0 tests
# ---------------------------------------------------------------------------


class TestMapper0:
    """Tests for Mapper0 (NROM) implementation."""

    def _make_mapper(
        self,
        prg_size: int = 32768,
        chr_size: int = 8192,
        mirroring: Mirroring = Mirroring.HORIZONTAL,
    ) -> Mapper0:
        """Create a Mapper0 with deterministic data."""
        prg_rom = bytes(range(256)) * (prg_size // 256)
        chr_rom = bytes(range(256)) * (chr_size // 256)
        return Mapper0(prg_rom, chr_rom, mirroring)

    # -- cpu_read ----------------------------------------------------------

    def test_cpu_read_first_byte(self) -> None:
        mapper = self._make_mapper()
        assert mapper.cpu_read(0x8000) == 0

    def test_cpu_read_last_byte_32kb(self) -> None:
        mapper = self._make_mapper(prg_size=32768)
        # Last byte of 32KB PRG ROM at address $FFFF
        assert mapper.cpu_read(0xFFFF) == (0xFFFF - 0x8000) % 256

    def test_cpu_read_mid_range(self) -> None:
        mapper = self._make_mapper()
        addr = 0x9000
        expected = (addr - 0x8000) % 256
        assert mapper.cpu_read(addr) == expected

    def test_cpu_read_16kb_mirror(self) -> None:
        """16KB PRG ROM should mirror into $C000-$FFFF."""
        mapper = self._make_mapper(prg_size=16384)
        # Read from $C000 should return same as $8000
        assert mapper.cpu_read(0xC000) == mapper.cpu_read(0x8000)
        # Read from $FFFF should return same as $BFFF
        assert mapper.cpu_read(0xFFFF) == mapper.cpu_read(0xBFFF)

    def test_cpu_read_32kb_no_mirror(self) -> None:
        """32KB PRG ROM should not mirror."""
        # Build PRG ROM where first half differs from second half
        prg_rom = bytes([0xAA] * 16384 + [0xBB] * 16384)
        chr_rom = bytes(8192)
        mapper = Mapper0(prg_rom, chr_rom, Mirroring.HORIZONTAL)
        # $8000 reads from first half, $C000 reads from second half
        assert mapper.cpu_read(0x8000) == 0xAA
        assert mapper.cpu_read(0xC000) == 0xBB

    def test_cpu_read_below_range_returns_open_bus(self) -> None:
        mapper = self._make_mapper()
        assert mapper.cpu_read(0x7FFF) == 0

    def test_cpu_read_above_range_still_valid(self) -> None:
        """$FFFF is the last valid address."""
        mapper = self._make_mapper()
        # Should not raise
        mapper.cpu_read(0xFFFF)

    # -- cpu_write ---------------------------------------------------------

    def test_cpu_write_is_noop(self) -> None:
        """NROM cpu_write should be a no-op (no writable CPU address space)."""
        mapper = self._make_mapper()
        # Should not raise
        mapper.cpu_write(0x8000, 0x42)
        # Value should remain unchanged
        assert mapper.cpu_read(0x8000) == 0

    # -- ppu_read ----------------------------------------------------------

    def test_ppu_read_first_byte(self) -> None:
        mapper = self._make_mapper()
        assert mapper.ppu_read(0x0000) == 0

    def test_ppu_read_last_byte(self) -> None:
        mapper = self._make_mapper()
        assert mapper.ppu_read(0x1FFF) == 0x1FFF % 256

    def test_ppu_read_mid_range(self) -> None:
        mapper = self._make_mapper()
        addr = 0x1000
        expected = addr % 256
        assert mapper.ppu_read(addr) == expected

    def test_ppu_read_out_of_range_returns_open_bus(self) -> None:
        mapper = self._make_mapper()
        assert mapper.ppu_read(0x2000) == 0

    # -- ppu_write ---------------------------------------------------------

    def test_ppu_write_chr_ram(self) -> None:
        """CHR RAM writes should be readable."""
        mapper = self._make_mapper()
        mapper.ppu_write(0x0000, 0x42)
        assert mapper.ppu_read(0x0000) == 0x42

    def test_ppu_write_multiple_addresses(self) -> None:
        mapper = self._make_mapper()
        for addr in [0x0000, 0x0FFF, 0x1FFF]:
            mapper.ppu_write(addr, 0xAB)
            assert mapper.ppu_read(addr) == 0xAB

    def test_ppu_write_out_of_range_is_noop(self) -> None:
        """Writes outside $0000-$1FFF should not raise (just ignored)."""
        mapper = self._make_mapper()
        # ppu_write does nothing for out-of-range addresses
        mapper.ppu_write(0x2000, 0xFF)

    # -- MapperInterface conformance ---------------------------------------

    def test_implements_mapper_interface(self) -> None:
        mapper = self._make_mapper()
        assert isinstance(mapper, MapperInterface)


# ---------------------------------------------------------------------------
# ROMLoader tests
# ---------------------------------------------------------------------------


class TestROMLoader:
    """Tests for ROMLoader."""

    ROM_PATH = "rom/super-mario-bros.nes"

    def test_load_super_mario_bros(self) -> None:
        """Load the real Super Mario Bros ROM and verify header."""
        loader = ROMLoader(self.ROM_PATH)
        header, mapper = loader.load()

        # Super Mario Bros header:
        # PRG ROM: 2 * 16KB = 32KB
        assert header.prg_rom_size == 32768
        # CHR ROM: 1 * 8KB = 8KB
        assert header.chr_rom_size == 8192
        # Mapper 0
        assert header.mapper_number == 0
        # Vertical mirroring (flags6 & 0x01)
        assert header.mirroring == Mirroring.VERTICAL
        # No battery RAM
        assert header.has_battery_ram is False
        # No trainer
        assert header.has_trainer is False

    def test_load_returns_mapper0(self) -> None:
        loader = ROMLoader(self.ROM_PATH)
        header, mapper = loader.load()
        assert isinstance(mapper, Mapper0)
        assert isinstance(mapper, MapperInterface)

    def test_mapper_cpu_read_from_loaded_rom(self) -> None:
        """Verify the loaded mapper can read CPU address space."""
        loader = ROMLoader(self.ROM_PATH)
        header, mapper = loader.load()
        # Should be able to read from $8000 without error
        value = mapper.cpu_read(0x8000)
        assert isinstance(value, int)
        assert 0 <= value <= 255

    def test_mapper_ppu_read_from_loaded_rom(self) -> None:
        """Verify the loaded mapper can read PPU address space."""
        loader = ROMLoader(self.ROM_PATH)
        header, mapper = loader.load()
        # Should be able to read from $0000 without error
        value = mapper.ppu_read(0x0000)
        assert isinstance(value, int)
        assert 0 <= value <= 255

    def test_invalid_magic_raises(self) -> None:
        """An iNES file with invalid magic number should raise ValueError."""
        from unittest.mock import mock_open, patch

        # Construct data with invalid magic
        bad_data = b"BAD\x00" + bytes(12)
        with patch("builtins.open", mock_open(read_data=bad_data)):
            loader = ROMLoader("fake.nes")
            with pytest.raises(ValueError, match="missing magic number"):
                loader.load()

    def test_constructed_ines_data(self) -> None:
        """Test loading from a hand-crafted valid iNES binary."""
        # Build a minimal valid iNES file:
        # 16-byte header + 1 * 16KB PRG ROM + 1 * 8KB CHR ROM
        header_bytes = bytearray(16)
        header_bytes[0:4] = b"NES\x1a"
        header_bytes[4] = 1  # 1 * 16KB PRG ROM
        header_bytes[5] = 1  # 1 * 8KB CHR ROM
        header_bytes[6] = 0x01  # flags6: vertical mirroring
        header_bytes[7] = 0x00  # flags7

        prg_rom = bytes(16384)  # 16KB of zeros
        chr_rom = bytes(8192)  # 8KB of zeros
        rom_data = bytes(header_bytes) + prg_rom + chr_rom

        from unittest.mock import mock_open, patch

        with patch("builtins.open", mock_open(read_data=rom_data)):
            loader = ROMLoader("fake.nes")
            header, mapper = loader.load()

        assert header.prg_rom_size == 16384
        assert header.chr_rom_size == 8192
        assert header.mapper_number == 0
        assert header.mirroring == Mirroring.VERTICAL
        assert isinstance(mapper, Mapper0)

    def test_constructed_ines_horizontal_mirroring(self) -> None:
        """Test iNES data with horizontal mirroring."""
        header_bytes = bytearray(16)
        header_bytes[0:4] = b"NES\x1a"
        header_bytes[4] = 2  # 2 * 16KB = 32KB PRG ROM
        header_bytes[5] = 1  # 1 * 8KB CHR ROM
        header_bytes[6] = 0x00  # flags6: horizontal mirroring (bit 0 clear)
        header_bytes[7] = 0x00

        prg_rom = bytes(32768)
        chr_rom = bytes(8192)
        rom_data = bytes(header_bytes) + prg_rom + chr_rom

        from unittest.mock import mock_open, patch

        with patch("builtins.open", mock_open(read_data=rom_data)):
            loader = ROMLoader("fake.nes")
            header, mapper = loader.load()

        assert header.prg_rom_size == 32768
        assert header.mirroring == Mirroring.HORIZONTAL

    def test_unsupported_mapper_raises(self) -> None:
        """A ROM with unsupported mapper number should raise ValueError."""
        header_bytes = bytearray(16)
        header_bytes[0:4] = b"NES\x1a"
        header_bytes[4] = 1  # PRG ROM
        header_bytes[5] = 1  # CHR ROM
        header_bytes[6] = 0x10  # mapper number 1 in upper nibble
        header_bytes[7] = 0x00

        prg_rom = bytes(16384)
        chr_rom = bytes(8192)
        rom_data = bytes(header_bytes) + prg_rom + chr_rom

        from unittest.mock import mock_open, patch

        with patch("builtins.open", mock_open(read_data=rom_data)):
            loader = ROMLoader("fake.nes")
            with pytest.raises(ValueError, match="Unsupported mapper"):
                loader.load()

    def test_chr_ram_fallback_when_chr_rom_size_zero(self) -> None:
        """When CHR ROM size is 0, should use 8KB CHR RAM."""
        header_bytes = bytearray(16)
        header_bytes[0:4] = b"NES\x1a"
        header_bytes[4] = 1  # PRG ROM
        header_bytes[5] = 0  # CHR ROM size = 0 (CHR RAM)
        header_bytes[6] = 0x00
        header_bytes[7] = 0x00

        prg_rom = bytes(16384)
        rom_data = bytes(header_bytes) + prg_rom

        from unittest.mock import mock_open, patch

        with patch("builtins.open", mock_open(read_data=rom_data)):
            loader = ROMLoader("fake.nes")
            header, mapper = loader.load()

        assert header.chr_rom_size == 0
        # Should still be able to read PPU (8KB CHR RAM)
        value = mapper.ppu_read(0x0000)
        assert value == 0
