"""NES APU Pulse Channel implementation.

Provides two pulse wave channels (Pulse 1 and Pulse 2) with:
- 4 duty cycle modes (12.5%, 25%, 50%, 75%)
- Volume envelope (constant or decaying)
- Sweep unit for frequency modulation
- Length counter for timed playback
"""

#  *
#  * @Author: ShaoqiLiang
#  * @Date: 2026-05-16 22:07:49
#  * @LastEditors: ShaoqiLiang
#  *

from dataclasses import dataclass

# Length counter lookup table (32 entries indexed by bits 7-3 of $4003/$4007)
LENGTH_TABLE: list[int] = [
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

# Duty cycle lookup table (4 modes, 8 steps each)
DUTY_TABLE: list[list[int]] = [
    [0, 1, 0, 0, 0, 0, 0, 0],  # 12.5%
    [0, 1, 1, 0, 0, 0, 0, 0],  # 25%
    [0, 1, 1, 1, 1, 0, 0, 0],  # 50%
    [1, 0, 0, 1, 1, 1, 1, 1],  # 75% (negated 25%)
]


@dataclass(slots=True)
class PulseState:
    """Pulse channel state registers."""

    enabled: bool = False
    duty: int = 0
    length_counter: int = 0
    volume: int = 0
    envelope: int = 0
    sweep_enabled: bool = False
    sweep_period: int = 0
    sweep_negate: bool = False
    sweep_shift: int = 0
    timer: int = 0
    timer_period: int = 0


class PulseChannel:
    """NES APU Pulse wave channel.

    Handles register writes, timer countdown, duty sequence stepping,
    volume envelope, sweep unit, and length counter.
    """

    def __init__(self) -> None:
        self._state: PulseState = PulseState()
        self._duty_index: int = 0
        # Envelope internal state
        self._envelope_divider: int = 0
        self._envelope_decay: int = 0
        self._envelope_loop: bool = False
        self._envelope_constant: bool = False
        # Sweep internal state
        self._sweep_divider: int = 0
        self._sweep_reload: bool = False

    def reset(self) -> None:
        """Reset channel to initial state."""
        self._state = PulseState()
        self._duty_index = 0
        self._envelope_divider = 0
        self._envelope_decay = 0
        self._envelope_loop = False
        self._envelope_constant = False
        self._sweep_divider = 0
        self._sweep_reload = False

    def write_register(self, addr: int, value: int) -> None:
        """Write to a pulse channel register.

        Args:
            addr: Register address ($4000-$4003 for pulse 1, $4004-$4007 for pulse 2).
            value: 8-bit value to write.
        """
        reg = addr & 0x03
        if reg == 0:  # $4000/$4004 — Duty/Volume
            self._state.duty = (value >> 6) & 0x03
            self._envelope_loop = bool(value & 0x20)
            self._envelope_constant = bool(value & 0x10)
            self._state.volume = value & 0x0F
            self._state.envelope = value & 0x0F
        elif reg == 1:  # $4001/$4005 — Sweep
            self._state.sweep_enabled = bool(value & 0x80)
            self._state.sweep_period = (value >> 4) & 0x07
            self._state.sweep_negate = bool(value & 0x08)
            self._state.sweep_shift = value & 0x07
            self._sweep_reload = True
        elif reg == 2:  # $4002/$4006 — Timer low
            self._state.timer_period = (self._state.timer_period & 0x700) | value
        elif reg == 3:  # $4003/$4007 — Timer high / Length counter
            self._state.timer_period = (self._state.timer_period & 0xFF) | (
                (value & 0x07) << 8
            )
            if self._state.enabled:
                self._state.length_counter = LENGTH_TABLE[(value >> 3) & 0x1F]
            self._duty_index = 0
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
            self._duty_index = (self._duty_index + 1) & 0x07
        else:
            self._state.timer -= 1

        # Output logic
        if self._state.length_counter == 0:
            return 0
        if not self._state.enabled:
            return 0
        if DUTY_TABLE[self._state.duty][self._duty_index] == 0:
            return 0
        if self._state.timer_period < 8:
            return 0

        # Determine volume
        if self._envelope_constant:
            vol = self._state.volume
        else:
            vol = self._envelope_decay

        return vol

    def output(self) -> int:
        """Return current output sample without advancing the timer."""
        if self._state.length_counter == 0:
            return 0
        if not self._state.enabled:
            return 0
        if DUTY_TABLE[self._state.duty][self._duty_index] == 0:
            return 0
        if self._state.timer_period < 8:
            return 0
        if self._envelope_constant:
            return self._state.volume
        return self._envelope_decay

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
        """Update length counter and sweep (called at half frame rate ~120 Hz)."""
        # Length counter
        if not self._envelope_loop and self._state.length_counter > 0:
            self._state.length_counter -= 1

        # Sweep
        self._tick_sweep()

    def _tick_sweep(self) -> None:
        """Update sweep unit."""
        if self._sweep_reload:
            if self._state.sweep_enabled and self._sweep_divider == 0:
                self._sweep_divider = self._state.sweep_period
            self._sweep_reload = False
        elif self._sweep_divider > 0:
            self._sweep_divider -= 1
        else:
            self._sweep_divider = self._state.sweep_period
            if (
                self._state.sweep_enabled
                and self._state.sweep_shift > 0
                and self._state.timer_period >= 8
            ):
                delta = self._state.timer_period >> self._state.sweep_shift
                if self._state.sweep_negate:
                    new_period = self._state.timer_period - delta
                    # For pulse 1, add ones' complement + 1 (handled at APU level)
                else:
                    new_period = self._state.timer_period + delta
                if new_period > 0x7FF:
                    self._state.enabled = False
                else:
                    self._state.timer_period = new_period

    @property
    def state(self) -> PulseState:
        """Access the internal state (for testing)."""
        return self._state
