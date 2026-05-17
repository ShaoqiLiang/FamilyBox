"""NES APU Triangle Channel implementation.

Provides a triangle wave channel with:
- 32-step triangle waveform sequence
- Linear counter for additional length control
- Length counter for timed playback
- No volume control (always outputs at full amplitude)
"""

#  *
#  * @Author: ShaoqiLiang
#  * @Date: 2026-05-16 22:07:49
#  * @LastEditors: ShaoqiLiang
#  *

from dataclasses import dataclass

# 32-step triangle waveform lookup table
TRIANGLE_TABLE: list[int] = [
    15,
    14,
    13,
    12,
    11,
    10,
    9,
    8,
    7,
    6,
    5,
    4,
    3,
    2,
    1,
    0,
    0,
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    11,
    12,
    13,
    14,
    15,
]

# Length counter lookup table (shared with pulse, but included for self-containment)
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
class TriangleState:
    """Triangle channel state registers."""

    enabled: bool = False
    length_counter: int = 0
    timer: int = 0
    timer_period: int = 0
    sequence_index: int = 0


class TriangleChannel:
    """NES APU Triangle wave channel.

    Generates a 32-step triangle waveform. Unlike pulse channels,
    the triangle channel has no volume envelope — it outputs at
    constant amplitude when active.
    """

    def __init__(self) -> None:
        self._state: TriangleState = TriangleState()
        # Linear counter state
        self._linear_counter: int = 0
        self._linear_counter_reload: int = 0
        self._linear_counter_control: bool = False
        self._linear_counter_reload_flag: bool = False

    def reset(self) -> None:
        """Reset channel to initial state."""
        self._state = TriangleState()
        self._linear_counter = 0
        self._linear_counter_reload = 0
        self._linear_counter_control = False
        self._linear_counter_reload_flag = False

    def write_register(self, addr: int, value: int) -> None:
        """Write to a triangle channel register.

        Args:
            addr: Register address ($4008, $400A, $400B).
            value: 8-bit value to write.
        """
        reg = addr & 0x03
        if reg == 0:  # $4008 — Linear counter / Length counter halt
            self._linear_counter_control = bool(value & 0x80)
            self._linear_counter_reload = value & 0x7F
        elif reg == 2:  # $400A — Timer low
            self._state.timer_period = (self._state.timer_period & 0x700) | value
        elif reg == 3:  # $400B — Timer high / Length counter
            self._state.timer_period = (self._state.timer_period & 0xFF) | (
                (value & 0x07) << 8
            )
            if self._state.enabled:
                self._state.length_counter = _LENGTH_TABLE[(value >> 3) & 0x1F]
            self._linear_counter_reload_flag = True

    def tick(self) -> int:
        """Advance the channel by one CPU cycle.

        Returns:
            Output sample value (0-15) from TRIANGLE_TABLE.
        """
        # Timer countdown (check before decrement for NES-accurate timing)
        if self._state.timer == 0:
            self._state.timer = self._state.timer_period
            # Only advance sequence if both counters are non-zero
            if self._state.length_counter > 0 and self._linear_counter > 0:
                self._state.sequence_index = (self._state.sequence_index + 1) & 0x1F
        else:
            self._state.timer -= 1

        return TRIANGLE_TABLE[self._state.sequence_index]

    def output(self) -> int:
        """Return current output sample without advancing the timer."""
        return TRIANGLE_TABLE[self._state.sequence_index]

    def tick_quarter_frame(self) -> None:
        """Update linear counter (called at quarter frame rate ~240 Hz)."""
        if self._linear_counter_reload_flag:
            self._linear_counter = self._linear_counter_reload
        elif self._linear_counter > 0:
            self._linear_counter -= 1

        if not self._linear_counter_control:
            self._linear_counter_reload_flag = False

    def tick_half_frame(self) -> None:
        """Update length counter (called at half frame rate ~120 Hz)."""
        if not self._linear_counter_control and self._state.length_counter > 0:
            self._state.length_counter -= 1

    @property
    def state(self) -> TriangleState:
        """Access the internal state (for testing)."""
        return self._state
