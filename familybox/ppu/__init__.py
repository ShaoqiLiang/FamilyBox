"""NES PPU (Picture Processing Unit) module.

Provides the PPU core (registers, timing, NMI), the pixel renderer
(background and sprites), and the NES colour palette constant.
"""

from familybox.ppu.palette import NES_PALETTE
from familybox.ppu.ppu import PPU, PPUMASK, PPUCTRL, PPUSTATUS, SpriteData
from familybox.ppu.renderer import Renderer

__all__ = [
    "NES_PALETTE",
    "PPU",
    "PPUCTRL",
    "PPUMASK",
    "PPUSTATUS",
    "Renderer",
    "SpriteData",
]
