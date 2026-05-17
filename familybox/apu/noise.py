"""NES APU Noise Channel implementation.

Provides a noise channel with:
- Linear Feedback Shift Register (LFSR) for pseudo-random noise generation
- Two modes (short/long sequence) controlled by mode bit
- Volume envelope (constant or decaying)
- Length counter for timed playback
"""
#  *
#  * @Author: ShaoqiLiang
#  * @Date: 2026-05-16 22:07:49
#  * @LastEditors: ShaoqiLiang
#  *

from dataclasses import dataclass

# Noise channel period lookup table (NTSC)
NOISE_PERIOD_TABLE: list[int] = [
    4,
    8,
    16,
    32,
    64,
    96,
    128,
    160,
    202,
    254,
    380,
    508,
    762,
    1016,
    2034,
    4068,
]

# Length counter lookup table (shared with all channels)
_LENGTH_TABLE: list[int] = [
    10,
    254,
    20,
    2,
    40,
    4,
    80,
    6,
    160,
    8,
    60,
    10,
    14,
    12,
    26,
    14,
    12,
    16,
    24,
    18,
    48,
    20,
    96,
    22,
    192,
    24,
    72,
    26,
    16,
    28,
    32,
    30,
]


@dataclass(slots=True)
class NoiseState:
    """Noise channel state registers."""

    enabled: bool = False
    length_counter: int = 0
    volume: int = 0
    envelope: int = 0
    timer: int = 0
    timer_period: int = 0
    shift_register: int = 1
    mode: bool = False


class NoiseChannel:
    """NES APU Noise channel.

    Generates pseudo-random noise using a 15-bit Linear Feedback
    Shift Register (LFSR). The mode bit selects between short
    (bit 6) and long (bit 1) feedback for different noise textures.
    """

    def __init__(self) -> None:
        self._state: NoiseState = NoiseState()
        # Envelope internal state
        self._envelope_divider: int = 0
        self._envelope_decay: int = 0
        self._envelope_loop: bool = False
        self._envelope_constant: bool = False

    def reset(self) -> None:
        """Reset channel to initial state."""
        self._state = NoiseState()
        self._envelope_divider = 0
        self._envelope_decay = 0
        self._envelope_loop = False
        self._envelope_constant = False

    def write_register(self, addr: int, value: int) -> None:
        """Write to a noise channel register.

        Args:
            addr: Register address ($400C, $400E, $400F).
            value: 8-bit value to write.
        """
        reg = addr & 0x03
        if reg == 0:  # $400C — Volume/Envelope
            self._envelope_loop = bool(value & 0x20)
            self._envelope_constant = bool(value & 0x10)
            self._state.volume = value & 0x0F
            self._state.envelope = value & 0x0F
        elif reg == 2:  # $400E — Mode/Period
            self._state.mode = bool(value & 0x80)
            self._state.timer_period = NOISE_PERIOD_TABLE[value & 0x0F]
        elif reg == 3:  # $400F — Length counter
            if self._state.enabled:
                self._state.length_counter = _LENGTH_TABLE[(value >> 3) & 0x1F]
            # Reset envelope
            self._envelope_decay = 0xF
            self._envelope_divider = self._state.volume

    def tick(self) -> int:
        """Advance the channel by one CPU cycle.

        Returns:
            Output sample value (0-15).
        """
        # Timer countdown (check before decrement for NES-accurate timing)
        if self._state.timer == 0:
            self._state.timer = self._state.timer_period
            self._tick_lfsr()
        else:
            self._state.timer -= 1

        # Output logic
        if self._state.length_counter == 0:
            return 0
        if not self._state.enabled:
            return 0
        if self._state.shift_register & 0x01:
            return 0

        # Determine volume
        if self._envelope_constant:
            return self._state.volume
        return self._envelope_decay

    def output(self) -> int:
        """Return current output sample without advancing the timer."""
        if self._state.length_counter == 0:
            return 0
        if not self._state.enabled:
            return 0
        if self._state.shift_register & 0x01:
            return 0
        if self._envelope_constant:
            return self._state.volume
        return self._envelope_decay

    def _tick_lfsr(self) -> None:
        """Advance the Linear Feedback Shift Register by one step."""
        if self._state.mode:
            feedback_bit = (
                self._state.shift_register ^ (self._state.shift_register >> 6)
            ) & 0x01
        else:
            feedback_bit = (
                self._state.shift_register ^ (self._state.shift_register >> 1)
            ) & 0x01
        self._state.shift_register = (self._state.shift_register >> 1) | (
            feedback_bit << 14
        )

    def _tick_lfsr_n(self, n: int) -> None:
        """Advance the LFSR by *n* steps in one call."""
        sr = self._state.shift_register
        if self._state.mode:
            for _ in range(n):
                sr = (sr >> 1) | (((sr ^ (sr >> 6)) & 1) << 14)
        else:
            for _ in range(n):
                sr = (sr >> 1) | (((sr ^ (sr >> 1)) & 1) << 14)
        self._state.shift_register = sr

    def tick_quarter_frame(self) -> None:
        """Update envelope (called at quarter frame rate ~240 Hz)."""
        if self._envelope_divider == 0:
            self._envelope_divider = self._state.volume
            if self._envelope_decay > 0:
                self._envelope_decay -= 1
            elif self._envelope_loop:
                self._envelope_decay = 0xF
        else:
            self._envelope_divider -= 1

    def tick_half_frame(self) -> None:
        """Update length counter (called at half frame rate ~120 Hz)."""
        if not self._envelope_loop and self._state.length_counter > 0:
            self._state.length_counter -= 1

    @property
    def state(self) -> NoiseState:
        """Access the internal state (for testing)."""
        return self._state
