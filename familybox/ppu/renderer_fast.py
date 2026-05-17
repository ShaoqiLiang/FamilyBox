"""Fast PPU renderer using a C extension via ctypes."""

#  *
#  * @Author: ShaoqiLiang
#  * @Date: 2026-05-16 22:07:49
#  * @LastEditors: ShaoqiLiang
#  *

from __future__ import annotations

import ctypes
import os
import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from familybox.ppu.ppu import PPU

# Locate the compiled C library
_DIR = os.path.dirname(os.path.abspath(__file__))
if sys.platform == "win32":
    _LIB_NAME = "renderer_c.dll"
elif sys.platform == "darwin":
    _LIB_NAME = "renderer_c.dylib"
else:
    _LIB_NAME = "renderer_c.so"

_LIB_PATH = os.path.join(_DIR, _LIB_NAME)

try:
    _lib = ctypes.CDLL(_LIB_PATH)
    _render_scanline = _lib.render_scanline
    _render_scanline.argtypes = [
        ctypes.POINTER(ctypes.c_ubyte),  # framebuffer
        ctypes.POINTER(ctypes.c_ubyte),  # oam
        ctypes.POINTER(ctypes.c_ubyte),  # nametable
        ctypes.POINTER(ctypes.c_ubyte),  # palette
        ctypes.POINTER(ctypes.c_ubyte),  # chr_rom
        ctypes.c_int,                    # scanline
        ctypes.c_int,                    # vram_addr
        ctypes.c_int,                    # fine_x
        ctypes.c_int,                    # bg_pattern_addr
        ctypes.c_int,                    # sprite_pattern_addr
        ctypes.c_int,                    # sprite_size
        ctypes.c_int,                    # show_bg
        ctypes.c_int,                    # show_sprites
        ctypes.c_int,                    # show_left_bg
        ctypes.c_int,                    # show_left_sprites
        ctypes.c_int,                    # mirroring
        ctypes.POINTER(ctypes.c_int),    # sprite_zero_hit_out
    ]
    _render_scanline.restype = None
    _AVAILABLE = True
except OSError:
    _AVAILABLE = False


def is_available() -> bool:
    """Return True if the C extension was loaded successfully."""
    return _AVAILABLE


class FastRenderer:
    """PPU renderer backed by a compiled C extension."""

    def __init__(self, ppu: PPU) -> None:
        self._ppu = ppu
        # RGB byte buffer: 256 * 240 * 3
        self._framebuffer_bytes: bytearray = bytearray(256 * 240 * 3)
        self._sprite_zero_hit = ctypes.c_int(0)

    def render_pixel(self, x: int, y: int) -> None:
        """No-op per-pixel — rendering is done per scanline."""
        # This method exists for interface compatibility with PPU.tick().
        # Actual rendering happens in render_scanline().

    def render_scanline(self, scanline: int) -> None:
        """Render an entire scanline in one C call."""
        ppu = self._ppu
        bus = ppu._bus

        # Get buffer pointers — access internal state of PPUBus/PPU directly
        bus_any: Any = bus
        fb_ptr = (ctypes.c_ubyte * len(self._framebuffer_bytes)).from_buffer(
            self._framebuffer_bytes
        )
        oam_ptr = (ctypes.c_ubyte * len(ppu._oam)).from_buffer(ppu._oam)
        nt_ptr = (ctypes.c_ubyte * len(bus_any._nametable)).from_buffer(
            bus_any._nametable
        )
        pal_ptr = (ctypes.c_ubyte * len(bus_any._palette)).from_buffer(
            bus_any._palette
        )

        chr_rom: bytearray = bus_any._mapper._chr_rom
        chr_ptr = (ctypes.c_ubyte * len(chr_rom)).from_buffer(chr_rom)

        self._sprite_zero_hit.value = 0

        _render_scanline(
            fb_ptr,
            oam_ptr,
            nt_ptr,
            pal_ptr,
            chr_ptr,
            scanline,
            ppu._vram_addr,
            ppu._fine_x,
            ppu._ctrl.bg_pattern_addr,
            ppu._ctrl.sprite_pattern_addr,
            ppu._ctrl.sprite_size,
            1 if ppu._mask.show_bg else 0,
            1 if ppu._mask.show_sprites else 0,
            1 if ppu._mask.show_left_bg else 0,
            1 if ppu._mask.show_left_sprites else 0,
            int(bus_any._mirroring),
            ctypes.byref(self._sprite_zero_hit),
        )

        if self._sprite_zero_hit.value:
            ppu._status.sprite_zero_hit = True

    def get_framebuffer_bytes(self) -> bytes:
        """Return the framebuffer as raw RGB bytes."""
        return bytes(self._framebuffer_bytes)

    def get_framebuffer(self) -> list[int]:
        """Return framebuffer as list of RGB ints (for compatibility)."""
        result: list[int] = [0] * (256 * 240)
        buf = self._framebuffer_bytes
        for i in range(256 * 240):
            off = i * 3
            result[i] = (buf[off] << 16) | (buf[off + 1] << 8) | buf[off + 2]
        return result
