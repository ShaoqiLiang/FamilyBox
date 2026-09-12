"""NES system top-level — pygame shell over the C core."""

from __future__ import annotations

import logging
import os
import time
from array import array
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pygame

from familybox.core_api import NesCore, _LIB_PATH

log = logging.getLogger(__name__)

SoundFactory = Callable[[bytes], Any]


class _AudioPump:
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
        self._pending += pcm
        if self._t0 is not None:
            consumed = (now - self._t0) * self.SR
            if consumed > self._enqueued + self.RESYNC_SLACK:
                # Starved far past everything we queued (long stall): drop
                # the clock and re-prime so the cushion rebuilds.
                self._t0 = None
                self._enqueued = 0
                self._last_dur = 0
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
            del self._pending[: len(self._pending) - self.MAX_PENDING]

    def stats(self, now: float) -> tuple[int, int]:
        """(estimated unstarted backlog in samples, pending samples)."""
        if self._t0 is None:
            return 0, len(self._pending) // 2
        consumed = (now - self._t0) * self.SR
        return int(self._enqueued - consumed), len(self._pending) // 2


# Same 64-entry table as familybox/ppu — for debug RGB printout only
_NES_RGB = [
    (84, 84, 84),
    (0, 30, 116),
    (8, 16, 144),
    (48, 0, 136),
    (68, 0, 100),
    (92, 0, 48),
    (84, 4, 0),
    (60, 24, 0),
    (32, 42, 0),
    (8, 58, 0),
    (0, 64, 0),
    (0, 60, 0),
    (0, 50, 60),
    (0, 0, 0),
    (0, 0, 0),
    (0, 0, 0),
    (152, 150, 152),
    (8, 76, 196),
    (48, 50, 236),
    (92, 30, 228),
    (136, 20, 176),
    (160, 20, 100),
    (152, 34, 32),
    (120, 60, 0),
    (84, 90, 0),
    (40, 114, 0),
    (8, 124, 0),
    (0, 118, 40),
    (0, 102, 120),
    (0, 0, 0),
    (0, 0, 0),
    (0, 0, 0),
    (236, 238, 236),
    (76, 154, 236),
    (120, 124, 236),
    (176, 98, 236),
    (228, 84, 236),
    (236, 88, 180),
    (236, 106, 100),
    (212, 136, 32),
    (160, 170, 0),
    (116, 196, 0),
    (76, 208, 32),
    (56, 204, 108),
    (56, 180, 204),
    (60, 60, 60),
    (0, 0, 0),
    (0, 0, 0),
    (236, 238, 236),
    (168, 204, 236),
    (188, 188, 236),
    (212, 178, 236),
    (236, 174, 236),
    (236, 174, 212),
    (236, 180, 176),
    (228, 196, 144),
    (204, 210, 120),
    (180, 222, 120),
    (168, 226, 144),
    (152, 226, 180),
    (160, 214, 228),
    (160, 162, 160),
    (0, 0, 0),
    (0, 0, 0),
]


def _debug_on() -> bool:
    if os.environ.get("FAMILYBOX_DEBUG", "") in ("1", "true", "TRUE"):
        return True
    marker = _LIB_PATH.parent / ".fb_debug"
    return marker.is_file()


def _log_dir() -> Path:
    # project root / build / log  (works from source and typical venv layout)
    here = Path(__file__).resolve().parent.parent
    d = here / "build" / "log"
    d.mkdir(parents=True, exist_ok=True)
    return d


# bit0=A bit1=B bit2=Select bit3=Start bit4=Up bit5=Down bit6=Left bit7=Right
_KEY_MAP = {
    # A (jump) / B (run)
    pygame.K_z: 0x01,
    pygame.K_n: 0x01,
    pygame.K_j: 0x01,
    pygame.K_SPACE: 0x01,  # jump
    pygame.K_m: 0x02,
    pygame.K_k: 0x02,
    # Select / Start
    pygame.K_RSHIFT: 0x04,
    pygame.K_LSHIFT: 0x04,
    pygame.K_RETURN: 0x08,
    pygame.K_TAB: 0x08,
    # D-pad: arrows + WASD
    pygame.K_UP: 0x10,
    pygame.K_DOWN: 0x20,
    pygame.K_LEFT: 0x40,
    pygame.K_RIGHT: 0x80,
    pygame.K_w: 0x10,
    pygame.K_s: 0x20,
    pygame.K_a: 0x40,
    pygame.K_d: 0x80,
}


class NES:
    """Pygame front-end for the C emulator core."""

    def __init__(self, rom_path: str, headless: bool = False) -> None:
        self._core = NesCore()
        self._debug = _debug_on()
        mode = "DEBUG" if (self._debug or self._core.debug_enabled()) else "RELEASE"
        print(f"[NES] starting in {mode} mode", flush=True)
        log.info("C core loaded from %s (%s)", _LIB_PATH, mode)
        rc = self._core.load_rom(rom_path)
        if rc != 0:
            raise FileNotFoundError(f"Failed to load ROM ({rc}): {rom_path}")

        self._headless = headless
        self._running = True
        self._buttons = 0
        self._frame_no = 0
        self._t0 = time.perf_counter()
        self._log_path = self._open_run_log(mode, rom_path)

        self._screen: pygame.Surface | None = None
        self._clock: pygame.time.Clock | None = None
        self._channel = None
        self._pump: _AudioPump | None = None
        self._maximized = False

        if not headless:
            pygame.init()
            self._screen = pygame.display.set_mode((256, 240), pygame.RESIZABLE)
            pygame.display.set_caption("FamilyBox -Auth:ShaoqiLiang")
            self._clock = pygame.time.Clock()
            try:
                pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=1024)
                self._channel = pygame.mixer.Channel(0)
                init = pygame.mixer.get_init()
                assert init is not None
                freq, _size, out_ch = init
                if freq != 44100:
                    log.warning(
                        "Mixer opened at %d Hz, core emits 44100 Hz — pitch will drift",
                        freq,
                    )
                if out_ch != 1:
                    log.info("Mixer opened as %d-channel; pump duplicates mono", out_ch)
                self._pump = _AudioPump(self._channel, channels=out_ch)
            except pygame.error as e:
                log.warning("Audio init failed: %s", e)

    def _open_run_log(self, mode: str, rom_path: str) -> Path | None:
        """Append-only log under build/log. Always created so runs are comparable."""
        try:
            ts = time.strftime("%Y%m%d_%H%M%S")
            path = _log_dir() / f"nes_{ts}.log"
            header = (
                f"===== FamilyBox run {ts} mode={mode} rom={rom_path} =====\n"
                f"DLL={_LIB_PATH}\n"
            )
            with path.open("a", encoding="utf-8") as f:
                f.write(header)
            # also append a line to the combined session log
            with (_log_dir() / "nes_session.log").open("a", encoding="utf-8") as f:
                f.write(header)
            print(f"[NES] log -> {path}", flush=True)
            return path
        except OSError as e:
            log.warning("cannot open run log: %s", e)
            return None

    def _log_line(self, line: str) -> None:
        if not self._log_path:
            return
        try:
            with self._log_path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
            with (_log_dir() / "nes_session.log").open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass

    def reset(self) -> None:
        self._core.reset()

    def run(self) -> None:
        self._core.reset()
        for _ in range(2):
            self._core.run_frame()

        while self._running:
            self._run_frame()
            if not self._headless:
                self._handle_events()
                self._present()
                assert self._clock is not None
                # Native core rate; tick(60) underfeeds the mixer by ~0.16%,
                # which drains the audio queue and crackles the stream.
                self._clock.tick(60.0988)

    def _debug_dump(self) -> None:
        c = self._core
        d = c.debug()
        regs = c.ppu_regs()
        vs = c.v_samples()
        oam = c.dump_oam()
        pal = c.dump_palette()
        rgb = getattr(self, "_last_rgb", b"")
        ms = int((time.perf_counter() - self._t0) * 1000)
        out: list[str] = []
        out.append(
            f"[PY] t={ms}ms f={self._frame_no} pc={d['pc']:#06x} "
            f"A={d['a']:#04x} X={d['x']:#04x} Y={d['y']:#04x} P={d['p']:#04x}"
        )
        out.append(
            f"     ctrl={regs['ctrl']:#04x} mask={regs['mask']:#04x} "
            f"st={regs['status']:#04x} v={regs['v']:#06x} t={c.get_t():#06x}"
        )
        out.append(
            f"     v0/20/40/100={[hex(x) for x in vs]} s0hits={c.s0_hits()} "
            f"last_s0_sl={c.last_s0_sl()} nmi={c.nmi_count()} "
            f"oam0={oam[:4]}"
        )
        lines = []
        for i in range(32):
            idx = pal[i]
            r, g, b = _NES_RGB[idx & 0x3F]
            lines.append(f"{i:02d}:idx={idx:02X} rgb({r:3d},{g:3d},{b:3d})")
        out.append("     PALETTE RAM (32 entries):")
        for i in range(0, 32, 4):
            out.append("       " + "  ".join(lines[i : i + 4]))
        if rgb and len(rgb) >= 256 * 240 * 3:

            def pix(x: int, y: int) -> tuple[int, int, int]:
                o = (y * 256 + x) * 3
                return (rgb[o], rgb[o + 1], rgb[o + 2])

            samples = [
                (8, 8),
                (128, 8),
                (248, 8),
                (8, 40),
                (128, 40),
                (248, 40),
                (8, 100),
                (128, 100),
                (248, 100),
                (128, 200),
                (128, 220),
            ]
            out.append(
                "     FRAME pixels (x,y)->rgb: "
                + " ".join(f"({x},{y})={pix(x, y)}" for x, y in samples)
            )
        wrs = c.wrlog()
        if wrs:
            tail = wrs[-10:]
            out.append(f"     last_writes={len(wrs)} showing {len(tail)}:")
            for w in tail:
                out.append(
                    f"       {w['kind']:10s} v={w['value']:#04x} addr={w['addr']:#06x} "
                    f"sl={w['scanline']} cy={w['cycle']}"
                )
        for line in out:
            print(line, flush=True)
            self._log_line(line)

    def _run_frame(self) -> None:
        rgb, pcm = self._core.run_frame()
        self._last_rgb = rgb
        self._frame_no += 1
        if self._debug and self._frame_no % 60 == 0:
            self._debug_dump()
        if pcm and self._pump is not None:
            try:
                self._pump.push(pcm, time.perf_counter())
            except pygame.error as e:
                log.warning("Audio pump failed: %s", e)

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self._restore_window()
                else:
                    self._handle_key(event.key, True)
            elif event.type == pygame.KEYUP:
                self._handle_key(event.key, False)
            elif event.type == pygame.WINDOWMAXIMIZED:
                self._enter_maximized()
            elif event.type in (pygame.WINDOWFOCUSLOST, pygame.WINDOWMINIMIZED):
                # While unfocused/minimized, KEYUP events are missed — release
                # everything so no direction/fire bit gets stuck.
                self._buttons = 0
                self._core.set_buttons(0)

    def _handle_key(self, key: int, pressed: bool) -> None:
        bit = _KEY_MAP.get(key)
        if bit is None:
            return
        if pressed:
            self._buttons |= bit
        else:
            self._buttons &= ~bit
        self._core.set_buttons(self._buttons)

    def _present(self) -> None:
        rgb = getattr(self, "_last_rgb", None)
        if not rgb or self._screen is None:
            return
        frame = pygame.image.frombuffer(rgb, (256, 240), "RGB")
        win_w, win_h = self._screen.get_size()
        if (win_w, win_h) == (256, 240):
            self._screen.blit(frame, (0, 0))
        else:
            # Integer-scale with letterbox bars: pixel-perfect at any size.
            scale = max(1, min(win_w // 256, win_h // 240))
            w, h = 256 * scale, 240 * scale
            self._screen.fill((0, 0, 0))
            self._screen.blit(
                pygame.transform.scale(frame, (w, h)),
                ((win_w - w) // 2, (win_h - h) // 2),
            )
        pygame.display.flip()

    def _enter_maximized(self) -> None:
        """Maximize button clicked: borderless window filling the desktop."""
        if self._headless or self._maximized:
            return
        desktop = pygame.display.get_desktop_sizes()[0]
        # set_mode() reuses the existing window and ignores changed window
        # flags, so recreate the display to drop the title bar.
        pygame.display.quit()
        pygame.display.init()
        self._screen = pygame.display.set_mode(desktop, pygame.NOFRAME)
        self._maximized = True

    def _restore_window(self) -> None:
        """ESC in maximized mode: back to the small titled window."""
        if self._headless or not self._maximized:
            return
        pygame.display.quit()
        pygame.display.init()
        self._screen = pygame.display.set_mode((256, 240), pygame.RESIZABLE)
        self._maximized = False

    def close(self) -> None:
        self._core.close()
        if not self._headless:
            pygame.quit()
