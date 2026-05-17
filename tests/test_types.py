"""Tests for familybox.types module."""

from familybox.types import (
    APUInterface,
    CPUBusInterface,
    ControllerInterface,
    MapperInterface,
    Mirroring,
    NESButton,
    NES_PALETTE,
    PPUBusInterface,
    iNESHeader,
)


# ---------------------------------------------------------------------------
# T-TYPES-01: Mirroring enum
# ---------------------------------------------------------------------------


class TestMirroring:
    def test_horizontal_value(self) -> None:
        assert int(Mirroring.HORIZONTAL) == 0

    def test_vertical_value(self) -> None:
        assert int(Mirroring.VERTICAL) == 1

    def test_four_screen_value(self) -> None:
        assert int(Mirroring.FOUR_SCREEN) == 8

    def test_members(self) -> None:
        assert set(Mirroring) == {
            Mirroring.HORIZONTAL,
            Mirroring.VERTICAL,
            Mirroring.FOUR_SCREEN,
        }


# ---------------------------------------------------------------------------
# T-TYPES-02: iNESHeader dataclass
# ---------------------------------------------------------------------------


class TestINESHeader:
    def test_create(self) -> None:
        header = iNESHeader(
            prg_rom_size=16384,
            chr_rom_size=8192,
            mapper_number=0,
            mirroring=Mirroring.HORIZONTAL,
            has_battery_ram=False,
            has_trainer=False,
        )
        assert header.prg_rom_size == 16384
        assert header.chr_rom_size == 8192
        assert header.mapper_number == 0
        assert header.mirroring is Mirroring.HORIZONTAL
        assert header.has_battery_ram is False
        assert header.has_trainer is False

    def test_frozen(self) -> None:
        header = iNESHeader(
            prg_rom_size=16384,
            chr_rom_size=8192,
            mapper_number=0,
            mirroring=Mirroring.HORIZONTAL,
            has_battery_ram=False,
            has_trainer=False,
        )
        try:
            header.prg_rom_size = 32768  # type: ignore[misc]
            raise AssertionError("Frozen dataclass should not allow mutation")
        except AttributeError:
            pass

    def test_equality(self) -> None:
        h1 = iNESHeader(
            prg_rom_size=16384,
            chr_rom_size=8192,
            mapper_number=1,
            mirroring=Mirroring.VERTICAL,
            has_battery_ram=True,
            has_trainer=True,
        )
        h2 = iNESHeader(
            prg_rom_size=16384,
            chr_rom_size=8192,
            mapper_number=1,
            mirroring=Mirroring.VERTICAL,
            has_battery_ram=True,
            has_trainer=True,
        )
        assert h1 == h2


# ---------------------------------------------------------------------------
# T-TYPES-03: NESButton enum
# ---------------------------------------------------------------------------


class TestNESButton:
    def test_values(self) -> None:
        expected = {
            NESButton.A: 0,
            NESButton.B: 1,
            NESButton.SELECT: 2,
            NESButton.START: 3,
            NESButton.UP: 4,
            NESButton.DOWN: 5,
            NESButton.LEFT: 6,
            NESButton.RIGHT: 7,
        }
        for button, value in expected.items():
            assert button == value

    def test_member_count(self) -> None:
        assert len(NESButton) == 8


# ---------------------------------------------------------------------------
# T-TYPES-04: NES_PALETTE constant
# ---------------------------------------------------------------------------


class TestNESPalette:
    def test_length(self) -> None:
        assert len(NES_PALETTE) == 64

    def test_each_entry_is_rgb_tuple(self) -> None:
        for i, color in enumerate(NES_PALETTE):
            assert isinstance(color, tuple), f"Entry {i} is not a tuple"
            assert len(color) == 3, f"Entry {i} does not have 3 elements"
            r, g, b = color
            assert 0 <= r <= 255, f"Entry {i} red out of range"
            assert 0 <= g <= 255, f"Entry {i} green out of range"
            assert 0 <= b <= 255, f"Entry {i} blue out of range"

    def test_first_color(self) -> None:
        assert NES_PALETTE[0] == (84, 84, 84)

    def test_last_color(self) -> None:
        assert NES_PALETTE[63] == (0, 0, 0)


# ---------------------------------------------------------------------------
# T-TYPES-05: Protocol interfaces are runtime_checkable
# ---------------------------------------------------------------------------


class _StubCPUBus:
    def read(self, addr: int) -> int:
        return 0

    def write(self, addr: int, value: int) -> None:
        pass


class _StubPPUBus:
    def read(self, addr: int) -> int:
        return 0

    def write(self, addr: int, value: int) -> None:
        pass

    def read_register(self, addr: int) -> int:
        return 0

    def write_register(self, addr: int, value: int) -> None:
        pass


class _StubMapper:
    def cpu_read(self, addr: int) -> int:
        return 0

    def cpu_write(self, addr: int, value: int) -> None:
        pass

    def ppu_read(self, addr: int) -> int:
        return 0

    def ppu_write(self, addr: int, value: int) -> None:
        pass


class _StubController:
    def read(self) -> int:
        return 0

    def write(self, value: int) -> None:
        pass

    def set_button(self, button: NESButton, pressed: bool) -> None:
        pass


class _StubAPU:
    def write_register(self, addr: int, value: int) -> None:
        pass

    def tick(self) -> float:
        return 0.0

    def get_sample_buffer(self) -> list[float]:
        return []

    def reset(self) -> None:
        pass


class TestProtocolRuntimeCheckable:
    def test_cpu_bus(self) -> None:
        assert isinstance(_StubCPUBus(), CPUBusInterface)

    def test_ppu_bus(self) -> None:
        assert isinstance(_StubPPUBus(), PPUBusInterface)

    def test_mapper(self) -> None:
        assert isinstance(_StubMapper(), MapperInterface)

    def test_controller(self) -> None:
        assert isinstance(_StubController(), ControllerInterface)

    def test_apu(self) -> None:
        assert isinstance(_StubAPU(), APUInterface)

    def test_non_conforming_is_not_instance(self) -> None:
        assert not isinstance("not a bus", CPUBusInterface)
