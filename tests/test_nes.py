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
        assert windowed_nes._screen.get_size() == (1024, 768)
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
        assert windowed_nes._screen.get_size() == (1024, 768)
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


class _FakeChannel:
    """Records play/queue calls; get_busy scriptable."""

    def __init__(self) -> None:
        self.played: list[object] = []
        self.queued: list[object] = []

    def play(self, snd: object) -> None:
        self.played.append(snd)

    def queue(self, snd: object) -> None:
        self.queued.append(snd)

    def get_busy(self) -> bool:
        return bool(self.played or self.queued)


class _FakeSound:
    def __init__(self, data: bytes) -> None:
        self.data = data


def _frame_pcm() -> bytes:
    # One core frame: ~733.75 -> 734 samples, mono s16 (1468 bytes)
    return b"\x00\x01" * 734


class TestAudioPump:
    FRAME = 734  # mono samples per core frame

    def _pump(self, channels: int = 1) -> tuple[object, _FakeChannel, list[bytes]]:
        from familybox.session import AudioPump as _AudioPump

        ch = _FakeChannel()
        data: list[bytes] = []

        def factory(d: bytes) -> _FakeSound:
            data.append(d)
            return _FakeSound(d)

        return _AudioPump(ch, channels=channels, sound_factory=factory), ch, data

    def test_primes_before_first_play(self) -> None:
        pump, ch, _ = self._pump()
        for i in range(pump.PRIME // self.FRAME):  # one frame short of PRIME
            pump.push(_frame_pcm(), now=i * self.FRAME / 44100)
        assert ch.played == [] and ch.queued == []

    def test_primes_then_plays_not_queues(self) -> None:
        pump, ch, _ = self._pump()
        t = 0.0
        for i in range((pump.PRIME + self.FRAME - 1) // self.FRAME):
            pump.push(_frame_pcm(), now=t)
            t += self.FRAME / 44100
        assert len(ch.played) == 1 and ch.queued == []

    def test_steady_state_nothing_lost(self) -> None:
        pump, ch, data = self._pump()
        t = 0.0
        n = 600  # ~10 s at 60.0988 fps
        for _ in range(n):
            pump.push(_frame_pcm(), now=t)
            t += self.FRAME / 44100
        assert len(ch.played) == 1
        assert 50 <= len(ch.queued) <= 75  # ~one queue per 160 ms chunk
        enqueued = sum(len(d) for d in data) // 2  # mono samples sent
        pushed = n * self.FRAME
        backlog, pending = pump.stats(t)
        assert enqueued + pending == pushed  # no samples dropped
        assert 0 <= backlog <= 2 * pump.CHUNK + self.FRAME

    def test_fast_loop_slot_protocol(self) -> None:
        pump, ch, _ = self._pump()
        for _ in range(10):
            pump.push(_frame_pcm(), now=0.0)  # all pushes at the same instant
        # one chunk playing + at most one queued; the rest waits in pending
        assert len(ch.played) == 1
        assert len(ch.queued) <= 1
        assert pump.stats(0.0)[1] > 0
        assert pump.stats(0.0)[1] <= pump.MAX_PENDING // 2 + self.FRAME

    def test_stereo_conversion_interleaves(self) -> None:
        pump, ch, data = self._pump(channels=2)
        t = 0.0
        for _ in range((pump.PRIME + self.FRAME - 1) // self.FRAME + 2):
            pump.push(_frame_pcm(), now=t)
            t += self.FRAME / 44100
        assert len(data) == 1
        assert len(data[0]) == pump.CHUNK * 4  # duplicated to stereo
        mono = (_frame_pcm() * 10)[: pump.CHUNK * 2]
        expect = bytearray()
        for k in range(0, len(mono), 2):
            expect += mono[k : k + 2] * 2
        assert data[0] == bytes(expect)

    def test_starvation_resyncs_and_reprimes(self) -> None:
        pump, ch, _ = self._pump()
        t = 0.0
        for _ in range(20):  # steady flow
            pump.push(_frame_pcm(), now=t)
            t += self.FRAME / 44100
        plays_before = len(ch.played)
        queues_before = len(ch.queued)
        t += 1.0  # long stall: mixer starved far past everything queued
        pump.push(_frame_pcm(), now=t)  # triggers resync
        # push until the pump re-primes and plays again; note pending may
        # hold leftovers from before the stall, so PRIME completes early
        for _ in range(20):
            t += self.FRAME / 44100
            pump.push(_frame_pcm(), now=t)
            if len(ch.played) > plays_before:
                break
        assert len(ch.played) == plays_before + 1  # re-prime uses play()
        assert len(ch.queued) == queues_before  # and never queue()
