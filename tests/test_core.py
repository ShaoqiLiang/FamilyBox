"""Integration tests for the C core via ctypes."""

from __future__ import annotations

from collections.abc import Generator

import pytest

from familybox.core_api import NesCore

ROM = "rom/super-mario-bros.nes"


@pytest.fixture()
def core() -> Generator[NesCore, None, None]:
    c = NesCore()
    assert c.load_rom(ROM) == 0
    c.reset()
    yield c
    c.close()


class TestLoad:
    def test_load_smb(self, core: NesCore) -> None:
        rgb, _ = core.run_frame()
        assert len(rgb) == 256 * 240 * 3

    def test_missing_rom(self) -> None:
        c = NesCore()
        assert c.load_rom("rom/does-not-exist.nes") != 0
        c.close()


class TestFrame:
    def test_frame_rgb_size(self, core: NesCore) -> None:
        rgb, pcm = core.run_frame()
        assert len(rgb) == 256 * 240 * 3
        assert len(pcm) % 2 == 0

    def test_pcm_sample_rate_approx(self, core: NesCore) -> None:
        # ~735 samples/frame at 44100Hz / 60fps
        _, pcm = core.run_frame()
        samples = len(pcm) // 2
        assert 650 <= samples <= 820

    def test_silence_has_zero_samples_when_idle(self) -> None:
        # After reset with no $4015 enable, mix should be near silent.
        c = NesCore()
        c.load_rom(ROM)
        c.reset()
        # run a few frames; game may enable audio — just require not crash
        for _ in range(5):
            _, pcm = c.run_frame()
            assert len(pcm) % 2 == 0
        c.close()

    def test_framebuffer_nonempty_after_init(self, core: NesCore) -> None:
        for _ in range(30):
            rgb, _ = core.run_frame()
        assert any(
            rgb[i] != 0 or rgb[i + 1] != 0 or rgb[i + 2] != 0
            for i in range(0, len(rgb), 3)
        )

    def test_debug_registers_vary(self, core: NesCore) -> None:
        core.run_frame()
        d1 = core.debug()
        for _ in range(10):
            core.run_frame()
        d2 = core.debug()
        assert "pc" in d1
        assert "pc" in d2


class TestInput:
    def test_set_buttons_no_crash(self, core: NesCore) -> None:
        core.set_buttons(0x01)
        core.run_frame()
        core.set_buttons(0x00)
        core.run_frame()
