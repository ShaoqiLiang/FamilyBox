"""PPU renderer -- background and sprite pixel rendering."""

#  *
#  * @Author: ShaoqiLiang
#  * @Date: 2026-05-16 22:07:49
#  * @LastEditors: ShaoqiLiang
#  *

from __future__ import annotations

from typing import TYPE_CHECKING

from familybox.types import NES_PALETTE

if TYPE_CHECKING:
    from familybox.ppu.ppu import PPU

# Sprite 0 index constant
_SPRITE_ZERO: int = 0


class Renderer:
    """PPU renderer.

    Renders background tiles and sprites into a 256x240 framebuffer.
    Each framebuffer entry is an RGB integer (0xRRGGBB).
    """

    def __init__(self, ppu: PPU) -> None:
        self._ppu: PPU = ppu
        self._framebuffer: list[int] = [0] * (256 * 240)
        self._bg_color_index: int = 0
        self._sprite_index: int = -1

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render_pixel(self, x: int, y: int) -> None:
        """Render a single pixel and write it to the framebuffer.

        Args:
            x: Screen X coordinate (0-255).
            y: Screen Y coordinate (0-239).
        """
        bg_color = self._get_bg_pixel(x, y)
        sprite_color, sprite_priority = self._get_sprite_pixel(x, y)

        bg_opaque: bool = self._bg_color_index != 0
        sprite_found: bool = self._sprite_index >= 0

        final: int
        if not sprite_found:
            final = bg_color
        elif not bg_opaque:
            final = sprite_color
        elif sprite_priority:
            final = bg_color
        else:
            final = sprite_color

        # Sprite 0 hit: fires when both sprite 0 and BG have non-transparent
        # pixels, regardless of sprite priority.  Cannot fire at x < 8 when
        # either left-edge clipping flag is disabled.
        if (
            sprite_found
            and bg_opaque
            and self._sprite_index == _SPRITE_ZERO
            and (x >= 8 or (self._ppu._mask.show_left_bg and self._ppu._mask.show_left_sprites))
        ):
            self._ppu._status.sprite_zero_hit = True

        self._framebuffer[y * 256 + x] = final

    def get_framebuffer(self) -> list[int]:
        """Return the current framebuffer (256*240 RGB integers)."""
        return self._framebuffer

    # ------------------------------------------------------------------
    # Background rendering
    # ------------------------------------------------------------------

    def _get_bg_pixel(self, x: int, y: int) -> int:
        """Return the background pixel colour at (*x*, *y*).

        Returns 0 (transparent) when background rendering is disabled.
        For colour index 0 (the universal background colour) the actual
        NES palette colour is returned so the caller can display it.
        """
        if not self._ppu._mask.show_bg:
            self._bg_color_index = 0
            return 0

        # Left 8px clipping: when show_left_bg is off, x=0..7 are transparent
        if not self._ppu._mask.show_left_bg and x < 8:
            self._bg_color_index = 0
            return 0

        # Absolute coordinates in the 512x480 nametable space
        abs_x = (x + self._ppu._fine_x) & 0x1FF
        abs_y = (y + ((self._ppu._vram_addr >> 12) & 0x07)) & 0x1FF

        coarse_x = abs_x >> 3
        coarse_y = abs_y >> 3
        fine_x = abs_x & 0x07
        fine_y = abs_y & 0x07

        # Nametable select (bit 10 = X overflow, bit 11 = Y overflow)
        nt_addr = (
            0x2000
            | (self._ppu._vram_addr & 0x0C00)
            | (coarse_y % 30) << 5
            | (coarse_x % 32)
        )

        tile_index = self._ppu._bus.read(nt_addr)

        pattern_addr = self._ppu._ctrl.bg_pattern_addr + tile_index * 16
        lo = self._ppu._bus.read(pattern_addr + fine_y)
        hi = self._ppu._bus.read(pattern_addr + fine_y + 8)
        bit = 7 - fine_x
        color_index = ((lo >> bit) & 1) | (((hi >> bit) & 1) << 1)

        # Track the raw colour index for compositing decisions
        self._bg_color_index = color_index

        # Attribute table lookup (wrap coarse_x/y like nametable)
        attr_addr = (
            0x23C0
            | (self._ppu._vram_addr & 0x0C00)
            | (((coarse_y % 30) >> 2) << 3)
            | ((coarse_x % 32) >> 2)
        )
        attr_byte = self._ppu._bus.read(attr_addr)
        shift = ((coarse_y & 2) << 1) | (coarse_x & 2)
        palette_index = (attr_byte >> shift) & 0x03

        palette_addr = 0x3F00 + palette_index * 4 + color_index
        return _NES_COLORS[self._ppu._bus.read(palette_addr)]

    # ------------------------------------------------------------------
    # Sprite rendering
    # ------------------------------------------------------------------

    def _get_sprite_pixel(self, x: int, y: int) -> tuple[int, int]:
        """Return the sprite pixel colour and priority.

        Returns ``(0, 0)`` when no sprite covers the pixel or sprite
        rendering is disabled.  Reads OAM bytes inline to avoid object
        allocation overhead.
        """
        if not self._ppu._mask.show_sprites:
            self._sprite_index = -1
            return (0, 0)

        # Left 8px clipping: when show_left_sprites is off, x=0..7 have no sprites
        if not self._ppu._mask.show_left_sprites and x < 8:
            self._sprite_index = -1
            return (0, 0)

        sprite_size = self._ppu._ctrl.sprite_size
        oam = self._ppu._oam
        bus_read = self._ppu._bus.read

        for i in range(64):
            base = i << 2
            sy = oam[base]  # OAM Y
            stile = oam[base + 1]  # OAM tile
            sattr = oam[base + 2]  # OAM attributes
            sx = oam[base + 3]  # OAM X

            # NES OAM Y is the sprite's top Y + 1
            start_y = (sy + 1) & 0xFF
            rel_y = (y - start_y) & 0xFF
            if rel_y >= sprite_size:
                continue

            # Check horizontal range
            if x < sx or x >= sx + 8:
                continue

            rel_x = x - sx

            # Inline flip checks (avoid @property calls)
            if sattr & 0x80:  # flip_v
                rel_y = sprite_size - 1 - rel_y
            if sattr & 0x40:  # flip_h
                rel_x = 7 - rel_x

            # Choose pattern table
            if sprite_size == 16:
                tile = stile & 0xFE
                table = (stile & 1) * 0x1000
                if rel_y >= 8:
                    tile += 1
                    rel_y -= 8
            else:
                table = self._ppu._ctrl.sprite_pattern_addr
                tile = stile

            pattern_addr = table + tile * 16 + rel_y
            lo = bus_read(pattern_addr)
            hi = bus_read(pattern_addr + 8)
            bit = 7 - rel_x
            color_index = ((lo >> bit) & 1) | (((hi >> bit) & 1) << 1)

            if color_index == 0:
                continue

            palette_addr = 0x3F10 + (sattr & 0x03) * 4 + color_index
            color = _NES_COLORS[bus_read(palette_addr)]
            self._sprite_index = i
            return (color, (sattr >> 5) & 1)

        self._sprite_index = -1
        return (0, 0)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _nes_color(palette_index: int) -> int:
        """Convert a NES palette index (0-63) to an RGB integer."""
        return _NES_COLORS[palette_index & 0x3F]


# Pre-computed NES palette as RGB integers (module-level for fast access)
_NES_COLORS: list[int] = [(r << 16) | (g << 8) | b for r, g, b in NES_PALETTE]
