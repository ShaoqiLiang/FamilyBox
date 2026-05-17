"""Tests for the NES system top-level module."""

import pytest

import pygame

from familybox.nes import NES


ROM_PATH: str = "rom/super-mario-bros.nes"


@pytest.fixture()
def nes_instance() -> NES:
    """Create a headless NES instance with Super Mario Bros ROM."""
    return NES(ROM_PATH, headless=True)


class TestNESInit:
    """T-NES-01 / T-NES-02: NES initialisation and component assembly."""

    def test_load_rom_succeeds(self) -> None:
        """NES should load a valid ROM without error."""
        nes = NES(ROM_PATH, headless=True)
        assert nes._header is not None
        assert nes._mapper is not None

    def test_components_created(self) -> None:
        """All internal components should be created."""
        nes = NES(ROM_PATH, headless=True)
        assert nes._cpu is not None
        assert nes._ppu is not None
        assert nes._apu is not None
        assert nes._controller is not None
        assert nes._cpu_bus is not None
        assert nes._ppu_bus is not None

    def test_headless_no_pygame_display(self) -> None:
        """Headless mode should not create pygame display objects."""
        nes = NES(ROM_PATH, headless=True)
        assert not hasattr(nes, "_screen") or nes._screen is None
        assert not hasattr(nes, "_clock") or nes._clock is None

    def test_running_flag_default(self) -> None:
        """The _running flag should be True after init."""
        nes = NES(ROM_PATH, headless=True)
        assert nes._running is True


class TestNESReset:
    """T-NES-04: System reset."""

    def test_reset_succeeds(self, nes_instance: NES) -> None:
        """Reset should complete without error."""
        nes_instance.reset()

    def test_reset_multiple_times(self, nes_instance: NES) -> None:
        """Calling reset multiple times should not raise."""
        nes_instance.reset()
        nes_instance.reset()
        nes_instance.reset()


class TestNESFrame:
    """T-NES-05 .. T-NES-08: Frame execution."""

    def test_run_frame_succeeds(self, nes_instance: NES) -> None:
        """Executing one frame should complete without error."""
        nes_instance.reset()
        nes_instance._run_frame()

    def test_framebuffer_non_empty(self, nes_instance: NES) -> None:
        """After enabling rendering and running one frame, the framebuffer
        should contain non-zero pixel data."""
        nes_instance.reset()
        # Enable background rendering via PPUMASK ($2001)
        nes_instance._ppu.write_register(0x2001, 0x08)
        nes_instance._run_frame()
        framebuffer = nes_instance._ppu._renderer.get_framebuffer()
        assert len(framebuffer) == 256 * 240
        assert any(pixel != 0 for pixel in framebuffer)

    def test_framebuffer_size(self, nes_instance: NES) -> None:
        """The framebuffer should be 256*240 pixels."""
        nes_instance.reset()
        nes_instance._run_frame()
        framebuffer = nes_instance._ppu._renderer.get_framebuffer()
        assert len(framebuffer) == 256 * 240


class TestNESKeyMapping:
    """T-NES-09 / T-NES-10: Keyboard event handling and key mapping."""

    def test_handle_key_a(self, nes_instance: NES) -> None:
        """Z key maps to NESButton.A."""
        nes_instance._handle_key(pygame.K_z, True)
        controller = nes_instance._controller
        # Read button state via the shift register
        controller.write(0x01)
        controller.write(0x00)
        assert controller.read() == 1  # A pressed

    def test_handle_key_b(self, nes_instance: NES) -> None:
        """X key maps to NESButton.B."""
        nes_instance._handle_key(pygame.K_x, True)
        controller = nes_instance._controller
        controller.write(0x01)
        controller.write(0x00)
        controller.read()  # skip A
        assert controller.read() == 1  # B pressed

    def test_handle_key_start(self, nes_instance: NES) -> None:
        """Enter key maps to NESButton.START."""
        nes_instance._handle_key(pygame.K_RETURN, True)
        controller = nes_instance._controller
        controller.write(0x01)
        controller.write(0x00)
        for _ in range(3):
            controller.read()  # skip A, B, Select
        assert controller.read() == 1  # Start pressed

    def test_handle_key_select(self, nes_instance: NES) -> None:
        """Right Shift maps to NESButton.SELECT."""
        nes_instance._handle_key(pygame.K_RSHIFT, True)
        controller = nes_instance._controller
        controller.write(0x01)
        controller.write(0x00)
        for _ in range(2):
            controller.read()  # skip A, B
        assert controller.read() == 1  # Select pressed

    def test_handle_key_directions(self, nes_instance: NES) -> None:
        """Arrow keys map to directional buttons."""
        nes_instance._handle_key(pygame.K_UP, True)
        controller = nes_instance._controller
        controller.write(0x01)
        controller.write(0x00)
        for _ in range(4):
            controller.read()  # skip A, B, Select, Start
        assert controller.read() == 1  # Up pressed

    def test_handle_key_release(self, nes_instance: NES) -> None:
        """Releasing a key should clear the button state."""
        nes_instance._handle_key(pygame.K_z, True)
        nes_instance._handle_key(pygame.K_z, False)
        controller = nes_instance._controller
        controller.write(0x01)
        controller.write(0x00)
        assert controller.read() == 0  # A released

    def test_handle_key_unmapped(self, nes_instance: NES) -> None:
        """Unmapped keys should not affect controller state."""
        nes_instance._handle_key(pygame.K_q, True)
        controller = nes_instance._controller
        controller.write(0x01)
        controller.write(0x00)
        assert controller.read() == 0  # nothing pressed
