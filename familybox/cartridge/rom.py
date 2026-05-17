"""iNES ROM file parser and loader."""

from familybox.cartridge.mapper import Mapper0
from familybox.types import MapperInterface, Mirroring, iNESHeader

#  *
#  * @Author: ShaoqiLiang
#  * @Date: 2026-05-16 22:07:49
#  * @LastEditors: ShaoqiLiang
#  *

class ROMLoader:
    """iNES ROM file loader.

    Parses the 16-byte iNES header, extracts PRG ROM and CHR ROM data,
    and creates the appropriate mapper instance.
    """

    MAGIC: bytes = b"NES\x1a"

    def __init__(self, filepath: str) -> None:
        self._filepath: str = filepath

    def load(self) -> tuple[iNESHeader, MapperInterface]:
        """Load and parse the ROM file.

        Returns:
            A tuple of (header, mapper).

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file is not a valid iNES format.
        """
        with open(self._filepath, "rb") as f:
            data = f.read()

        header = self._parse_header(data)

        # PRG ROM starts right after the 16-byte header
        prg_start = 16
        prg_end = prg_start + header.prg_rom_size
        chr_end = prg_end + header.chr_rom_size

        prg_rom = data[prg_start:prg_end]
        chr_rom = data[prg_end:chr_end] if header.chr_rom_size > 0 else bytes(8192)

        mapper = self._create_mapper(header, prg_rom, chr_rom)
        return header, mapper

    def _parse_header(self, data: bytes) -> iNESHeader:
        """Parse the iNES header from raw bytes.

        Args:
            data: Raw ROM file data.

        Returns:
            Parsed iNESHeader instance.

        Raises:
            ValueError: If the magic number is invalid.
        """
        if data[:4] != self.MAGIC:
            raise ValueError("Invalid iNES file: missing magic number")

        prg_rom_size = data[4] * 16384  # 16KB units
        chr_rom_size = data[5] * 8192  # 8KB units

        flags6 = data[6]
        flags7 = data[7]

        mapper_number = (flags6 >> 4) | (flags7 & 0xF0)
        mirroring = Mirroring.VERTICAL if (flags6 & 0x01) else Mirroring.HORIZONTAL
        has_battery_ram = bool(flags6 & 0x02)
        has_trainer = bool(flags6 & 0x04)

        return iNESHeader(
            prg_rom_size=prg_rom_size,
            chr_rom_size=chr_rom_size,
            mapper_number=mapper_number,
            mirroring=mirroring,
            has_battery_ram=has_battery_ram,
            has_trainer=has_trainer,
        )

    def _create_mapper(
        self, header: iNESHeader, prg_rom: bytes, chr_rom: bytes
    ) -> MapperInterface:
        """Create a mapper instance based on the mapper number.

        Args:
            header: Parsed iNES header.
            prg_rom: PRG ROM data.
            chr_rom: CHR ROM data.

        Returns:
            A MapperInterface implementation.

        Raises:
            ValueError: If the mapper number is not supported.
        """
        if header.mapper_number == 0:
            return Mapper0(prg_rom, chr_rom, header.mirroring)
        raise ValueError(f"Unsupported mapper: {header.mapper_number}")
