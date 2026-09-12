"""Tests for the NES pygame shell over the C core."""

from __future__ import annotations

from collections.abc import Generator

import pygame
import pytest

from familybox.nes import NES

ROM_PATH = "rom/super-mario-bros.nes"


@pytest.fixture()
def nes() -> Generator[NES, None, None]:
    n = NES(ROM_PATH, headless=True)
    yield n
    n.close()


class TestNESInit:
    def test_load_rom_succeeds(self, nes: NES) -> None:
        assert nes._core is not None

    def test_headless_no_pygame_display(self, nes: NES) -> None:
        assert nes._screen is None

    def test_reset_succeeds(self, nes: NES) -> None:
        nes.reset()
        nes.reset()

    def test_run_frame_succeeds(self, nes: NES) -> None:
        nes.reset()
        nes._run_frame()
        assert nes._last_rgb
        assert len(nes._last_rgb) == 256 * 240 * 3


class TestKeyMapping:
    def test_handle_key_a(self, nes: NES) -> None:
        nes._handle_key(pygame.K_z, True)
        assert nes._buttons & 0x01
        nes._handle_key(pygame.K_z, False)
        assert not (nes._buttons & 0x01)

    def test_handle_key_unmapped(self, nes: NES) -> None:
        nes._handle_key(ord("q"), True)
        assert nes._buttons == 0


@pytest.fixture()
def windowed_nes(monkeypatch: pytest.MonkeyPatch) -> Generator[NES, None, None]:
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    pygame.init()
    n = NES(ROM_PATH, headless=False)
    yield n
    n.close()


class TestWindowMaximize:
    def test_default_small_window(self, windowed_nes: NES) -> None:
        assert windowed_nes._screen is not None
        assert windowed_nes._screen.get_size() == (256, 240)
        assert not windowed_nes._maximized

    def test_maximize_is_borderless_fullscreen(self, windowed_nes: NES) -> None:
        pygame.event.post(pygame.event.Event(pygame.WINDOWMAXIMIZED))
        windowed_nes._handle_events()
        assert windowed_nes._maximized
        assert windowed_nes._screen is not None
        assert windowed_nes._screen.get_size() == pygame.display.get_desktop_sizes()[0]
        assert windowed_nes._screen.get_flags() & pygame.NOFRAME

    def test_esc_restores_small_window(self, windowed_nes: NES) -> None:
        pygame.event.post(pygame.event.Event(pygame.WINDOWMAXIMIZED))
        windowed_nes._handle_events()
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        windowed_nes._handle_events()
        assert windowed_nes._screen is not None
        assert windowed_nes._screen.get_size() == (256, 240)
        assert windowed_nes._screen.get_flags() & pygame.RESIZABLE
        assert not windowed_nes._maximized

    def test_present_works_in_maximized_mode(self, windowed_nes: NES) -> None:
        windowed_nes.reset()
        windowed_nes._run_frame()
        pygame.event.post(pygame.event.Event(pygame.WINDOWMAXIMIZED))
        windowed_nes._handle_events()
        windowed_nes._present()  # scaled blit must not raise

    def test_focus_lost_clears_buttons(self, windowed_nes: NES) -> None:
        windowed_nes._handle_key(pygame.K_RIGHT, True)
        assert windowed_nes._buttons == 0x80
        pygame.event.post(pygame.event.Event(pygame.WINDOWFOCUSLOST))
        windowed_nes._handle_events()
        assert windowed_nes._buttons == 0
