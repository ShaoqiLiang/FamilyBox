"""L4 application layer: owns the core handle, audio feeding and pacing.

The session is UI-agnostic (design doc §6): audio goes out through an
injected mixer-channel-like object, pacing sleeps through an injected
sleep callable, and time comes from an injected clock — tests drive it on
synthetic time without sleeping.
"""

from __future__ import annotations

import time
from array import array
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pygame

from window.binding.core_api import NesCore

SoundFactory = Callable[[bytes], Any]
_REGION_IDS = {"ntsc": 0, "pal": 1}


class AudioPump:
    """Streams core PCM to the mixer on the audio clock.

    Two hardware facts shape this pump:
    - pygame-ce may open the mixer as stereo even when channels=1 is
      requested (get_init() is authoritative), so mono core samples must be
      duplicated to L/R before reaching Sound.
    - Channel.queue() is a ONE-DEEP slot: queueing again REPLACES the sound
      still waiting, discarding it. So the mixer can hold at most two chunks
      (playing + queued) and a new queue() is only issued once the previously
      queued chunk has started playing. That moment is tracked with our own
      audio-clock bookkeeping (consumed = elapsed * SR since playback start),
      not with get_busy(), which flickers at chunk boundaries.

    Chunks are ~160 ms so normal Python/OS jitter never empties the mixer.
    """

    SR = 44100
    CHUNK = SR * 160 // 1000  # mono samples per Sound (~160 ms)
    PRIME = SR * 160 // 1000  # accumulate this much before starting playback
    MAX_PENDING = SR * 2 // 5  # trim unqueued backlog beyond ~0.4 s
    RESYNC_SLACK = SR // 10  # starved this deep for this long -> re-prime
    # Fallback slot margin for channels without get_queue(): SDL consumes in
    # buffer-sized quanta, so the wall-clock estimate can run ahead of the
    # mixer by about one buffer. Queueing before the previously queued chunk
    # actually STARTED would REPLACE (drop) it.
    SLOT_MARGIN = SR * 50 // 1000

    def __init__(
        self,
        channel: Any,
        channels: int = 1,
        sound_factory: SoundFactory | None = None,
    ) -> None:
        self._channel = channel
        self._channels = channels
        if sound_factory is None:

            def sound_factory(data: bytes) -> Any:
                return pygame.mixer.Sound(buffer=data)

        self._make_sound = sound_factory
        self._pending = bytearray()
        self._t0: float | None = None  # playback start (first chunk played)
        self._enqueued = 0  # mono samples handed to the mixer
        self._last_dur = 0  # duration of the most recent chunk
        self._refs: deque[Any] = deque(maxlen=8)
        # lifetime statistics (M2 acceptance: long-run drop rate < 0.1%)
        self.total_pushed = 0
        self.total_dropped = 0
        self.total_underruns = 0

    def _to_mixer(self, data: bytes) -> bytes:
        if self._channels == 1:
            return data
        a = array("h")
        a.frombytes(data)
        out = array("h", bytes(len(a) * 4))
        out[0::2] = a
        out[1::2] = a
        return out.tobytes()

    def _slot_free(self, consumed: float) -> bool:
        """True when the one-deep queue slot is free for a new chunk."""
        get_queue = getattr(self._channel, "get_queue", None)
        if get_queue is not None:
            try:
                return get_queue() is None
            except pygame.error:
                pass
        return consumed >= self._enqueued - self._last_dur + self.SLOT_MARGIN

    def push(self, pcm: bytes, now: float) -> None:
        self.total_pushed += len(pcm) // 2
        self._pending += pcm
        if self._t0 is not None:
            consumed = (now - self._t0) * self.SR
            if consumed > self._enqueued + self.RESYNC_SLACK:
                # Starved far past everything we queued (long stall): drop
                # the clock and re-prime so the cushion rebuilds.
                self._t0 = None
                self._enqueued = 0
                self._last_dur = 0
                self.total_underruns += 1
        while self._pending:
            dur = min(len(self._pending) // 2, self.CHUNK)
            if self._t0 is None:
                if dur < self.PRIME:
                    break  # still priming
            else:
                consumed = (now - self._t0) * self.SR
                if not self._slot_free(consumed):
                    break  # one-deep queue slot still occupied
                if consumed <= self._enqueued and dur < self.CHUNK:
                    break  # not starving: hold back for a full chunk
            data = bytes(self._pending[: dur * 2])
            del self._pending[: dur * 2]
            snd = self._make_sound(self._to_mixer(data))
            if self._t0 is None:
                self._channel.play(snd)
                self._t0 = now
            else:
                self._channel.queue(snd)
            self._refs.append(snd)
            self._enqueued += dur
            self._last_dur = dur
        if len(self._pending) > self.MAX_PENDING:
            dropped = len(self._pending) - self.MAX_PENDING
            del self._pending[:dropped]
            self.total_dropped += dropped // 2

    def stats(self, now: float) -> tuple[int, int]:
        """(estimated unstarted backlog in samples, pending samples)."""
        if self._t0 is None:
            return 0, len(self._pending) // 2
        consumed = (now - self._t0) * self.SR
        return int(self._enqueued - consumed), len(self._pending) // 2

    def drop_rate(self) -> float:
        """Fraction of pushed samples that never reached the mixer."""
        if self.total_pushed == 0:
            return 0.0
        return self.total_dropped / self.total_pushed


class EmulationSession:
    """One running machine: core handle + audio feeding + pacing + input.

    The frontend calls step() once per frame and presents what comes back;
    pacing holds each frame to the region's native cadence on the audio
    clock (1/60.0988 s NTSC, 1/50.007 s PAL) instead of wall-clock guesses.
    """

    def __init__(
        self,
        rom_path: str | Path | None,
        *,
        region: str = "ntsc",
        channel: Any = None,
        channels: int = 1,
        sound_factory: SoundFactory | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        if region not in _REGION_IDS:
            raise ValueError(f"unknown region {region!r} (use 'ntsc' or 'pal')")
        self._sleep = sleep
        self._clock_fn = clock
        self._core = NesCore()
        self._core.set_timing(_REGION_IDS[region])
        self._cart_loaded = False
        if rom_path is not None:
            if not self.load_rom(rom_path):
                raise FileNotFoundError(f"Failed to load ROM: {rom_path}")
        self._pump: AudioPump | None = (
            AudioPump(channel, channels=channels, sound_factory=sound_factory)
            if channel is not None
            else None
        )
        self._region = region
        self._frame_index = 0
        self._t0: float | None = None
        if region == "pal":
            self._frame_seconds = (341 * 312 * 5 / 16) / 1662607  # ~1/50.007 s
        else:
            self._frame_seconds = (341 * 262 / 3) / 1789773  # ~1/60.0988 s

    def set_region(self, region: str) -> None:
        """切换时序标准并复位（菜单"模拟 > 时序标准"）。区域属核心时序配置，
        切换即重启当前游戏。"""
        if region not in _REGION_IDS:
            raise ValueError(f"unknown region {region!r} (use 'ntsc' or 'pal')")
        self._region = region
        self._core.set_timing(_REGION_IDS[region])
        if region == "pal":
            self._frame_seconds = (341 * 312 * 5 / 16) / 1662607  # ~1/50.007 s
        else:
            self._frame_seconds = (341 * 262 / 3) / 1789773  # ~1/60.0988 s
        self._core.reset()

    @property
    def cart_loaded(self) -> bool:
        """False until a cartridge loads — frontend shows the loader UI."""
        return self._cart_loaded

    def load_rom(self, rom_path: str | Path) -> bool:
        """Load (or hot-swap) a cartridge and reset. False if the core rejects it."""
        rc = self._core.load_rom(str(rom_path))
        if rc != 0:
            return False
        self._core.reset()
        self._cart_loaded = True
        return True

    @property
    def core(self) -> NesCore:
        """Direct core access — debug facade only; step() owns the run."""
        return self._core

    @property
    def region(self) -> str:
        return self._region

    @property
    def pump(self) -> AudioPump | None:
        return self._pump

    def reset(self) -> None:
        self._core.reset()

    def set_buttons(self, buttons: int) -> None:
        self._core.set_buttons(buttons & 0xFF)

    def step(self) -> tuple[memoryview | None, bytes]:
        """Run one frame, feed audio, hold the native cadence.

        Without a cartridge loaded this only paces and returns (None, b"").
        """
        if not self._cart_loaded:
            return None, b""
        rgb, pcm = self._core.run_frame()
        now = self._clock_fn()
        if self._pump is not None and pcm:
            self._pump.push(pcm, now)
        self._frame_index += 1
        t0 = self._t0
        if t0 is None:
            t0 = now
            self._t0 = t0
        due = t0 + self._frame_index * self._frame_seconds
        delay = due - self._clock_fn()
        if delay > 0:
            self._sleep(delay)
        return rgb, pcm

    # -- statistics (M2 acceptance) --

    def drop_rate(self) -> float:
        return self._pump.drop_rate() if self._pump else 0.0

    def underruns(self) -> int:
        return self._pump.total_underruns if self._pump else 0
