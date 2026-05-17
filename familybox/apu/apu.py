"""NES APU (Audio Processing Unit) core implementation.

Coordinates four audio channels (2 pulse, 1 triangle, 1 noise) using
a frame counter for timing, and mixes their output using the standard
NES mixing formula for final audio output.
"""
#  *
#  * @Author: ShaoqiLiang
#  * @Date: 2026-05-16 22:07:49
#  * @LastEditors: ShaoqiLiang
#  *

from familybox.apu.noise import NoiseChannel
from familybox.apu.pulse import PulseChannel
from familybox.apu.triangle import TriangleChannel

# NTSC CPU frequency (cycles per second)
_CPU_FREQ: int = 1_789_773

# Frame counter step thresholds (in CPU cycles)
# 4-step mode: quarter frames at 7457, 14913, 22371, 29829
_FOUR_STEP_QUARTER: list[int] = [7457, 14913, 22371, 29829]
# 5-step mode: quarter frames at 7457, 14913, 22371, 29829, 37281
_FIVE_STEP_QUARTER: list[int] = [7457, 14913, 22371, 29829, 37281]


class APU:
    """NES Audio Processing Unit.

    Manages four audio channels and provides mixed audio output.
    Uses a frame counter to schedule envelope, length counter,
    and sweep updates at quarter-frame and half-frame rates.
    """

    def __init__(self) -> None:
        self._pulse1: PulseChannel = PulseChannel()
        self._pulse2: PulseChannel = PulseChannel()
        self._triangle: TriangleChannel = TriangleChannel()
        self._noise: NoiseChannel = NoiseChannel()

        # Frame counter state
        self._frame_counter: int = 0
        self._frame_mode: int = 0  # 0 = 4-step, 1 = 5-step
        self._frame_step: int = 0
        self._irq_inhibit: bool = False

        # Audio output
        self._sample_buffer: list[float] = []
        self._sample_timer: float = 0.0
        self._sample_rate: int = 44100
        self._cycles_per_sample: float = _CPU_FREQ / self._sample_rate

    def reset(self) -> None:
        """Reset APU and all channels to initial state."""
        self._pulse1.reset()
        self._pulse2.reset()
        self._triangle.reset()
        self._noise.reset()
        self._frame_counter = 0
        self._frame_step = 0
        self._sample_buffer.clear()
        self._sample_timer = 0.0

    def write_register(self, addr: int, value: int) -> None:
        """Route register write to the appropriate channel.

        Args:
            addr: APU register address ($4000-$4017).
            value: 8-bit value to write.
        """
        if 0x4000 <= addr <= 0x4003:
            self._pulse1.write_register(addr, value)
        elif 0x4004 <= addr <= 0x4007:
            self._pulse2.write_register(addr, value)
        elif 0x4008 <= addr <= 0x400B:
            self._triangle.write_register(addr, value)
        elif 0x400C <= addr <= 0x400F:
            self._noise.write_register(addr, value)
        elif addr == 0x4015:
            self._write_status(value)
        elif addr == 0x4017:
            self._frame_mode = (value >> 7) & 0x01
            self._irq_inhibit = bool(value & 0x40)
            self._frame_counter = 0
            self._frame_step = 0

    def tick(self, cycles: int = 1) -> float:
        """Advance APU by *cycles* CPU cycles.

        Returns:
            Mixed audio sample (last computed, or 0.0 if no sample produced).
        """
        # Advance frame counter and check for envelope/length updates
        self._frame_counter += cycles
        self._check_frame_steps()

        # Batch tick channels (advance timers by N cycles)
        self._batch_tick_channels(cycles)

        # Sample rate conversion: mix only when a sample is needed
        sample = 0.0
        self._sample_timer += cycles
        if self._sample_timer >= self._cycles_per_sample:
            self._sample_timer -= self._cycles_per_sample
            p1 = self._pulse1.output()
            p2 = self._pulse2.output()
            t = self._triangle.output()
            n = self._noise.output()
            sample = self._mix(p1, p2, t, n)
            self._sample_buffer.append(sample)

        return sample

    def _batch_tick_channels(self, cycles: int) -> None:
        """Advance all channel timers by *cycles* at once."""
        # Pulse channels (two instances, same logic)
        for pulse in (self._pulse1, self._pulse2):
            ps = pulse._state
            if ps.timer >= cycles:
                ps.timer -= cycles
            else:
                remaining = cycles
                while remaining > 0:
                    if ps.timer < remaining:
                        remaining -= ps.timer + 1
                        ps.timer = ps.timer_period
                        pulse._duty_index = (pulse._duty_index + 1) & 0x07
                    else:
                        ps.timer -= remaining
                        break

        # Triangle channel
        tri = self._triangle
        ts = tri._state
        if ts.timer >= cycles:
            ts.timer -= cycles
        else:
            remaining = cycles
            while remaining > 0:
                if ts.timer < remaining:
                    remaining -= ts.timer + 1
                    ts.timer = ts.timer_period
                    if ts.length_counter > 0 and tri._linear_counter > 0:
                        ts.sequence_index = (ts.sequence_index + 1) & 0x1F
                else:
                    ts.timer -= remaining
                    break

        # Noise channel — precompute LFSR steps to reduce function calls
        noise = self._noise
        ns = noise._state
        if ns.timer >= cycles:
            ns.timer -= cycles
        else:
            period = ns.timer_period
            if period == 0:
                ns.timer = 0
            else:
                lfsr_steps = 0
                remaining = cycles
                while remaining > 0:
                    if ns.timer < remaining:
                        remaining -= ns.timer + 1
                        ns.timer = period
                        lfsr_steps += 1
                    else:
                        ns.timer -= remaining
                        break
                if lfsr_steps:
                    noise._tick_lfsr_n(lfsr_steps)

    def _check_frame_steps(self) -> None:
        """Check if the frame counter has crossed any step thresholds."""
        if self._frame_mode == 0:
            steps = _FOUR_STEP_QUARTER
            max_steps = 4
            half_set = frozenset((1, 3))
        else:
            steps = _FIVE_STEP_QUARTER
            max_steps = 5
            half_set = frozenset((0, 2))

        while (
            self._frame_step < max_steps
            and self._frame_counter >= steps[self._frame_step]
        ):
            self._tick_frame(self._frame_step in half_set)
            self._frame_step += 1
            if self._frame_step >= max_steps:
                self._frame_counter = 0
                self._frame_step = 0

    def _tick_frame(self, half_frame: bool) -> None:
        """Process a frame step.

        Args:
            half_frame: If True, also update length counters and sweep.
        """
        # Quarter frame: always update envelope and linear counter
        self._pulse1.tick_quarter_frame()
        self._pulse2.tick_quarter_frame()
        self._triangle.tick_quarter_frame()
        self._noise.tick_quarter_frame()

        # Half frame: additionally update length counters and sweep
        if half_frame:
            self._pulse1.tick_half_frame()
            self._pulse2.tick_half_frame()
            self._triangle.tick_half_frame()
            self._noise.tick_half_frame()

    def _write_status(self, value: int) -> None:
        """Handle write to $4015 (status register).

        Enables/disables individual channels and resets length counters
        when a channel is disabled.
        """
        self._pulse1.state.enabled = bool(value & 0x01)
        self._pulse2.state.enabled = bool(value & 0x02)
        self._triangle.state.enabled = bool(value & 0x04)
        self._noise.state.enabled = bool(value & 0x08)

        # Reset length counters when channels are disabled
        if not (value & 0x01):
            self._pulse1.state.length_counter = 0
        if not (value & 0x02):
            self._pulse2.state.length_counter = 0
        if not (value & 0x04):
            self._triangle.state.length_counter = 0
        if not (value & 0x08):
            self._noise.state.length_counter = 0

    @staticmethod
    def _mix(p1: int, p2: int, t: int, n: int) -> float:
        """Mix channel outputs using the NES mixing formula.

        The NES uses two separate nonlinear mixing stages:
        - Pulse mix: combines two pulse channels
        - TND mix: combines triangle, noise, and DMC (DMC not implemented)

        Args:
            p1: Pulse 1 output (0-15).
            p2: Pulse 2 output (0-15).
            t: Triangle output (0-15).
            n: Noise output (0-15).

        Returns:
            Mixed sample in range [0.0, ~1.0].
        """
        # Pulse mixing
        pulse_sum = p1 + p2
        pulse_out = 0.0
        if pulse_sum > 0:
            pulse_out = 95.88 / ((8128.0 / pulse_sum) + 100.0)

        # TND mixing (triangle + noise + DMC)
        tnd_out = 0.0
        tnd_val = t / 8227.0 + n / 12241.0
        if tnd_val > 0.0:
            tnd_out = 159.79 / ((1.0 / tnd_val) + 100.0)

        return pulse_out + tnd_out

    def get_sample_buffer(self) -> list[float]:
        """Get and clear the audio sample buffer.

        Returns:
            List of mixed audio samples since last call.
        """
        buffer = self._sample_buffer
        self._sample_buffer = []
        return buffer

    @property
    def pulse1(self) -> PulseChannel:
        """Access pulse channel 1."""
        return self._pulse1

    @property
    def pulse2(self) -> PulseChannel:
        """Access pulse channel 2."""
        return self._pulse2

    @property
    def triangle(self) -> TriangleChannel:
        """Access triangle channel."""
        return self._triangle

    @property
    def noise(self) -> NoiseChannel:
        """Access noise channel."""
        return self._noise
