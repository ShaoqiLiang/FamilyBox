"""PPU (Picture Processing Unit) core.

Handles PPUCTRL / PPUMASK / PPUSTATUS registers, OAM, VRAM addressing
(scroll and address latches), timing (scanline / cycle state machine),
VBlank NMI signalling, and delegates pixel rendering to :class:`Renderer`.
"""

#  *
#  * @Author: ShaoqiLiang
#  * @Date: 2026-05-16 22:07:49
#  * @LastEditors: ShaoqiLiang
#  *

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from familybox.ppu.renderer import Renderer
from familybox.types import PPUBusInterface


# ---------------------------------------------------------------------------
# Data structures (T-PPU-01 .. T-PPU-04)
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class PPUCTRL:
    """PPU control register ($2000)."""

    nametable_addr: int = 0x2000
    vram_increment: int = 1
    sprite_pattern_addr: int = 0
    bg_pattern_addr: int = 0
    sprite_size: int = 8
    nmi_enabled: bool = False


@dataclass(slots=True)
class PPUMASK:
    """PPU mask register ($2001)."""

    greyscale: bool = False
    show_left_bg: bool = False
    show_left_sprites: bool = False
    show_bg: bool = False
    show_sprites: bool = False
    emphasize_red: bool = False
    emphasize_green: bool = False
    emphasize_blue: bool = False


@dataclass(slots=True)
class PPUSTATUS:
    """PPU status register ($2002)."""

    sprite_overflow: bool = False
    sprite_zero_hit: bool = False
    vblank: bool = False


@dataclass(slots=True)
class SpriteData:
    """A single OAM entry (4 bytes)."""

    y: int = 0
    tile: int = 0
    attr: int = 0
    x: int = 0

    @property
    def palette(self) -> int:
        """Sprite palette index (0-3)."""
        return self.attr & 0x03

    @property
    def flip_h(self) -> bool:
        """Horizontal flip flag."""
        return bool(self.attr & 0x40)

    @property
    def flip_v(self) -> bool:
        """Vertical flip flag."""
        return bool(self.attr & 0x80)

    @property
    def priority(self) -> int:
        """Sprite priority (0 = in front of background, 1 = behind)."""
        return (self.attr >> 5) & 0x01


# ---------------------------------------------------------------------------
# PPU core (T-PPU-07 .. T-PPU-18)
# ---------------------------------------------------------------------------


class PPU:
    """NES PPU core.

    Args:
        bus: The PPU address bus (pattern tables, nametables, palette).
    """

    def __init__(self, bus: PPUBusInterface, *, use_fast_renderer: bool = True) -> None:
        self._bus: PPUBusInterface = bus

        # Registers
        self._ctrl: PPUCTRL = PPUCTRL()
        self._mask: PPUMASK = PPUMASK()
        self._status: PPUSTATUS = PPUSTATUS()

        # OAM
        self._oam: bytearray = bytearray(256)
        self._oam_addr: int = 0

        # VRAM address state
        self._vram_addr: int = 0
        self._temp_addr: int = 0
        self._write_toggle: bool = False
        self._fine_x: int = 0
        self._data_buffer: int = 0

        # Timing
        self._scanline: int = 261
        self._cycle: int = 0
        self._frame: int = 0
        self._even_frame: bool = True

        # NMI
        self._nmi_output: bool = False
        self._nmi_occurred: bool = False

        # Renderer — try fast C renderer, fall back to pure Python
        import os

        self._use_fast_renderer: bool = False
        if use_fast_renderer and not os.environ.get("FAMILYBOX_NO_FAST_RENDERER"):
            try:
                from familybox.ppu.renderer_fast import FastRenderer, is_available

                if is_available():
                    self._renderer: FastRenderer | Renderer = FastRenderer(self)
                    self._use_fast_renderer = True
                else:
                    self._renderer = Renderer(self)
            except Exception:
                self._renderer = Renderer(self)
        else:
            self._renderer = Renderer(self)

    # ------------------------------------------------------------------
    # Reset (T-PPU-08)
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset all PPU registers and internal state."""
        self._ctrl = PPUCTRL()
        self._mask = PPUMASK()
        self._status = PPUSTATUS()
        self._oam_addr = 0
        self._vram_addr = 0
        self._temp_addr = 0
        self._write_toggle = False
        self._fine_x = 0
        self._data_buffer = 0
        self._scanline = 261
        self._cycle = 0
        self._frame = 0
        self._even_frame = True
        self._nmi_output = False
        self._nmi_occurred = False

    # ------------------------------------------------------------------
    # Tick -- timing state machine (T-PPU-09 .. T-PPU-11)
    # ------------------------------------------------------------------

    def tick(self) -> bool:
        """Advance one PPU cycle.

        The cycle counter is incremented first, then the actions for the
        new cycle value are executed.  This ensures that after
        ``_advance_to(ppu, scanline, cycle)`` the actions for that
        (scanline, cycle) pair have already been performed.

        Returns:
            ``True`` if an NMI was triggered this cycle.
        """
        nmi_triggered = False

        # Check for NMI from PPUCTRL edge detection
        if self._nmi_output:
            nmi_triggered = True
            self._nmi_output = False

        # Advance timing
        self._cycle += 1
        if self._cycle > 340:
            self._cycle = 0
            self._scanline += 1
            if self._scanline > 261:
                self._scanline = 0
                self._frame += 1
                self._even_frame = not self._even_frame

        # VBlank entry at scanline 241, cycle 1
        if self._scanline == 241 and self._cycle == 1:
            self._status.vblank = True
            self._status.sprite_zero_hit = False
            if not self._nmi_occurred:
                self._nmi_occurred = True
                if self._ctrl.nmi_enabled:
                    nmi_triggered = True

        # Pre-render scanline (261)
        if self._scanline == 261:
            if self._cycle == 1:
                self._status.vblank = False
                self._status.sprite_overflow = False
                self._nmi_occurred = False
            # Copy horizontal bits from temp_addr to vram_addr (cycles 257-340)
            if self._cycle >= 257 and self._cycle <= 340:
                self._vram_addr = (self._vram_addr & ~0x041F) | (self._temp_addr & 0x041F)
            # Copy vertical bits from temp_addr to vram_addr (cycles 280-304)
            if self._cycle >= 280 and self._cycle <= 304:
                self._vram_addr = (self._vram_addr & ~0x7BE0) | (self._temp_addr & 0x7BE0)

        # Visible scanlines: copy horizontal bits at cycle 257
        if 0 <= self._scanline <= 239 and self._cycle == 257:
            self._vram_addr = (self._vram_addr & ~0x041F) | (self._temp_addr & 0x041F)

        # Render visible pixels (scanlines 0-239, cycles 1-256)
        # Fast path: render entire scanline at cycle 256
        if self._use_fast_renderer and self._scanline <= 239 and self._cycle == 256:
            cast(Any, self._renderer).render_scanline(self._scanline)
        # elif 0 <= self._scanline <= 239 and 1 <= self._cycle <= 256:
        #     self._renderer.render_pixel(self._cycle - 1, self._scanline)

        return nmi_triggered

    def tick_scanlines(self, count: int = 1) -> bool:
        """Advance PPU by *count* full scanlines (341 cycles each).

        This is a batched fast-path that handles only the meaningful
        cycle/scanline events instead of ticking through every cycle.

        Returns:
            ``True`` if an NMI was triggered.
        """
        nmi_triggered = False

        for _ in range(count):
            # Check for pending NMI from PPUCTRL edge detection
            if self._nmi_output:
                nmi_triggered = True
                self._nmi_output = False

            sl = self._scanline

            if sl <= 239:
                # --- Visible scanline ---
                # Render scanline (fast renderer batches at cycle 256)
                if self._use_fast_renderer:
                    cast(Any, self._renderer).render_scanline(sl)
                    # for px in range(256):
                    #     self._renderer.render_pixel(px, sl)
                        # self._renderer.render_pixel(px, sl)
                # Copy horizontal bits at cycle 257
                self._vram_addr = (self._vram_addr & ~0x041F) | (
                    self._temp_addr & 0x041F
                )
                self._cycle = 0
                self._scanline = sl + 1

            elif sl == 240:
                # Post-render: nothing happens
                self._cycle = 0
                self._scanline = 241

            elif sl == 241:
                # VBlank entry at cycle 1
                self._status.vblank = True
                self._status.sprite_zero_hit = False
                if self._ctrl.nmi_enabled and not self._nmi_occurred:
                    self._nmi_occurred = True
                    nmi_triggered = True
                self._cycle = 0
                self._scanline = 242

            elif sl < 261:
                # Idle VBlank scanlines
                self._cycle = 0
                self._scanline = sl + 1

            else:
                # Pre-render scanline (261)
                # Cycle 1: clear flags
                self._status.vblank = False
                self._status.sprite_overflow = False
                self._nmi_occurred = False
                # Copy horizontal bits (cycles 257-340)
                self._vram_addr = (self._vram_addr & ~0x041F) | (
                    self._temp_addr & 0x041F
                )
                # Copy vertical bits (cycles 280-304)
                self._vram_addr = (self._vram_addr & ~0x7BE0) | (
                    self._temp_addr & 0x7BE0
                )
                self._cycle = 0
                self._scanline = 0
                self._frame += 1
                self._even_frame = not self._even_frame

        return nmi_triggered

    # ------------------------------------------------------------------
    # Register reads (T-PPU-12)
    # ------------------------------------------------------------------

    def read_register(self, addr: int) -> int:
        """CPU reads from PPU registers ($2000-$2007).

        Args:
            addr: CPU-mapped register address.

        Returns:
            8-bit register value.
        """
        if addr == 0x2002:  # PPUSTATUS
            value = (
                (int(self._status.vblank) << 7)
                | (int(self._status.sprite_zero_hit) << 6)
                | (int(self._status.sprite_overflow) << 5)
            )
            self._status.vblank = False
            self._write_toggle = False
            return value
        if addr == 0x2004:  # OAMDATA
            return self._oam[self._oam_addr]
        if addr == 0x2007:  # PPUDATA
            value = self._bus.read(self._vram_addr)
            if self._vram_addr < 0x3F00:
                buffered = self._data_buffer
                self._data_buffer = value
                return buffered
            return value
        return 0

    # ------------------------------------------------------------------
    # Register writes (T-PPU-13 .. T-PPU-16)
    # ------------------------------------------------------------------

    def write_register(self, addr: int, value: int) -> None:
        """CPU writes to PPU registers ($2000-$2007).

        Args:
            addr: CPU-mapped register address.
            value: 8-bit value to write.
        """
        if addr == 0x2000:  # PPUCTRL
            old_nmi_enabled = self._ctrl.nmi_enabled
            self._ctrl = self._decode_ctrl(value)
            # NMI edge detection: if NMI is being enabled while VBlank is active
            if not old_nmi_enabled and self._ctrl.nmi_enabled and self._nmi_occurred:
                self._nmi_output = True
        elif addr == 0x2001:  # PPUMASK
            self._mask = self._decode_mask(value)
        elif addr == 0x2003:  # OAMADDR
            self._oam_addr = value & 0xFF
        elif addr == 0x2004:  # OAMDATA
            self._oam[self._oam_addr] = value & 0xFF
            self._oam_addr = (self._oam_addr + 1) & 0xFF
        elif addr == 0x2005:  # PPUSCROLL
            if not self._write_toggle:
                self._temp_addr = (self._temp_addr & 0xFFE0) | (value >> 3)
                self._fine_x = value & 0x07
            else:
                self._temp_addr = (
                    (self._temp_addr & 0x8C1F)
                    | ((value & 0xF8) << 2)
                    | ((value & 0x07) << 12)
                )
            self._write_toggle = not self._write_toggle
        elif addr == 0x2006:  # PPUADDR
            if not self._write_toggle:
                self._temp_addr = (self._temp_addr & 0x80FF) | ((value & 0x3F) << 8)
            else:
                self._temp_addr = (self._temp_addr & 0xFF00) | value
                self._vram_addr = self._temp_addr
            self._write_toggle = not self._write_toggle
        elif addr == 0x2007:  # PPUDATA
            self._bus.write(self._vram_addr, value & 0xFF)
            self._vram_addr = (self._vram_addr + self._ctrl.vram_increment) & 0x7FFF

    # ------------------------------------------------------------------
    # OAM access (T-PPU-17)
    # ------------------------------------------------------------------

    def get_oam_sprite(self, index: int) -> SpriteData:
        """Return the OAM entry at *index* (0-63) as a :class:`SpriteData`.

        Args:
            index: Sprite index (0-63).

        Returns:
            Parsed sprite data.
        """
        offset = index * 4
        return SpriteData(
            y=self._oam[offset],
            tile=self._oam[offset + 1],
            attr=self._oam[offset + 2],
            x=self._oam[offset + 3],
        )

    # ------------------------------------------------------------------
    # Internal register decoding helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _decode_ctrl(value: int) -> PPUCTRL:
        """Decode a raw byte into a :class:`PPUCTRL` instance."""
        return PPUCTRL(
            nametable_addr=0x2000 + (value & 0x03) * 0x0400,
            vram_increment=32 if value & 0x04 else 1,
            sprite_pattern_addr=0x1000 if value & 0x08 else 0,
            bg_pattern_addr=0x1000 if value & 0x10 else 0,
            sprite_size=16 if value & 0x20 else 8,
            nmi_enabled=bool(value & 0x80),
        )

    @staticmethod
    def _decode_mask(value: int) -> PPUMASK:
        """Decode a raw byte into a :class:`PPUMASK` instance."""
        return PPUMASK(
            greyscale=bool(value & 0x01),
            show_left_bg=bool(value & 0x02),
            show_left_sprites=bool(value & 0x04),
            show_bg=bool(value & 0x08),
            show_sprites=bool(value & 0x10),
            emphasize_red=bool(value & 0x20),
            emphasize_green=bool(value & 0x40),
            emphasize_blue=bool(value & 0x80),
        )
