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
