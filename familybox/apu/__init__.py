"""NES APU (Audio Processing Unit) module.

Provides audio channel emulation for the NES sound hardware:
- PulseChannel: Two pulse wave channels with sweep and envelope
- TriangleChannel: Triangle wave channel with linear counter
- NoiseChannel: Pseudo-random noise channel with LFSR
- APU: Core coordinator with frame counter and mixing
"""

from familybox.apu.apu import APU
from familybox.apu.noise import NoiseChannel
from familybox.apu.pulse import PulseChannel
from familybox.apu.triangle import TriangleChannel

__all__ = [
    "APU",
    "NoiseChannel",
    "PulseChannel",
    "TriangleChannel",
]
