"""NES system top-level — pygame shell over the C core."""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import pygame

from familybox.core_api import NesCore, _LIB_PATH

log = logging.getLogger(__name__)

# Same 64-entry table as familybox/ppu — for debug RGB printout only
_NES_RGB = [
    (84, 84, 84), (0, 30, 116), (8, 16, 144), (48, 0, 136),
    (68, 0, 100), (92, 0, 48), (84, 4, 0), (60, 24, 0),
    (32, 42, 0), (8, 58, 0), (0, 64, 0), (0, 60, 0),
    (0, 50, 60), (0, 0, 0), (0, 0, 0), (0, 0, 0),
    (152, 150, 152), (8, 76, 196), (48, 50, 236), (92, 30, 228),
    (136, 20, 176), (160, 20, 100), (152, 34, 32), (120, 60, 0),
    (84, 90, 0), (40, 114, 0), (8, 124, 0), (0, 118, 40),
    (0, 102, 120), (0, 0, 0), (0, 0, 0), (0, 0, 0),
    (236, 238, 236), (76, 154, 236), (120, 124, 236), (176, 98, 236),
    (228, 84, 236), (236, 88, 180), (236, 106, 100), (212, 136, 32),
    (160, 170, 0), (116, 196, 0), (76, 208, 32), (56, 204, 108),
    (56, 180, 204), (60, 60, 60), (0, 0, 0), (0, 0, 0),
    (236, 238, 236), (168, 204, 236), (188, 188, 236), (212, 178, 236),
    (236, 174, 236), (236, 174, 212), (236, 180, 176), (228, 196, 144),
    (204, 210, 120), (180, 222, 120), (168, 226, 144), (152, 226, 180),
    (160, 214, 228), (160, 162, 160), (0, 0, 0), (0, 0, 0),
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
    pygame.K_x: 0x02,
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

        if not headless:
            pygame.init()
            self._screen = pygame.display.set_mode((256, 240))
            pygame.display.set_caption("FamilyBox -Auth:ShaoqiLiang")
            self._clock = pygame.time.Clock()
            try:
                pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=1024)
                self._channel = pygame.mixer.Channel(0)
            except pygame.error as e:
                log.warning("Audio init failed: %s", e)

        self._surface: pygame.Surface | None = None
        if not headless:
            self._surface = pygame.image.frombuffer(
                bytes(256 * 240 * 3), (256, 240), "RGB"
            )

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
                self._clock.tick(60)

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
                (8, 8), (128, 8), (248, 8),
                (8, 40), (128, 40), (248, 40),
                (8, 100), (128, 100), (248, 100),
                (128, 200), (128, 220),
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
        if pcm and self._channel is not None:
            try:
                snd = pygame.mixer.Sound(buffer=pcm)
                self._channel.queue(snd)
            except pygame.error:
                pass

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._running = False
            elif event.type == pygame.KEYDOWN:
                self._handle_key(event.key, True)
            elif event.type == pygame.KEYUP:
                self._handle_key(event.key, False)

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
        surf = pygame.image.frombuffer(rgb, (256, 240), "RGB")
        self._screen.blit(surf, (0, 0))
        pygame.display.flip()

    def close(self) -> None:
        self._core.close()
        if not self._headless:
            pygame.quit()
