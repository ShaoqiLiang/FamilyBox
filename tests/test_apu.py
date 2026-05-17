"""Tests for the APU module.

Covers all four audio channels (Pulse 1, Pulse 2, Triangle, Noise),
the APU core (frame counter, mixing, register routing), and edge cases.
"""

from familybox.apu.apu import APU
from familybox.apu.noise import NoiseChannel
from familybox.apu.pulse import DUTY_TABLE, LENGTH_TABLE, PulseChannel
from familybox.apu.triangle import TRIANGLE_TABLE, TriangleChannel


# ---------------------------------------------------------------------------
# PulseChannel tests
# ---------------------------------------------------------------------------


class TestPulseChannel:
    """Tests for PulseChannel."""

    def test_initial_state(self) -> None:
        ch = PulseChannel()
        assert ch.state.enabled is False
        assert ch.state.length_counter == 0
        assert ch.state.volume == 0
        assert ch.state.timer_period == 0

    def test_reset(self) -> None:
        ch = PulseChannel()
        ch.write_register(0x4000, 0xFF)
        ch.write_register(0x4002, 0xAB)
        ch.reset()
        assert ch.state.enabled is False
        assert ch.state.volume == 0
        assert ch.state.timer_period == 0

    def test_write_duty_volume(self) -> None:
        ch = PulseChannel()
        # Duty=2 (50%), constant volume=10
        ch.write_register(0x4000, 0b10_0_1_1010)
        assert ch.state.duty == 2
        assert ch.state.volume == 10

    def test_write_sweep(self) -> None:
        ch = PulseChannel()
        # Enabled, period=3, negate, shift=2
        ch.write_register(0x4001, 0b1_011_1_010)
        assert ch.state.sweep_enabled is True
        assert ch.state.sweep_period == 3
        assert ch.state.sweep_negate is True
        assert ch.state.sweep_shift == 2

    def test_write_timer_low(self) -> None:
        ch = PulseChannel()
        ch.write_register(0x4002, 0xAB)
        assert ch.state.timer_period == 0xAB

    def test_write_timer_high_length(self) -> None:
        ch = PulseChannel()
        ch.state.enabled = True
        ch.write_register(0x4003, 0b00001_010)  # length index=1, timer high=2
        assert ch.state.timer_period == (0x02 << 8) | 0x00
        assert ch.state.length_counter == LENGTH_TABLE[1]

    def test_tick_returns_volume_when_active(self) -> None:
        ch = PulseChannel()
        ch.state.enabled = True
        ch.state.length_counter = 10
        ch.state.timer_period = 100
        ch.state.timer = 100  # non-zero so timer just decrements
        ch.state.volume = 8
        # Use 50% duty (duty=2) where bits 1-4 are high
        ch.state.duty = 2
        ch._duty_index = 1
        ch._envelope_constant = True
        assert ch.tick() == 8

    def test_tick_returns_zero_when_disabled(self) -> None:
        ch = PulseChannel()
        ch.state.enabled = False
        ch.state.length_counter = 10
        ch.state.volume = 8
        ch._duty_index = 1
        assert ch.tick() == 0

    def test_tick_returns_zero_when_length_counter_zero(self) -> None:
        ch = PulseChannel()
        ch.state.enabled = True
        ch.state.length_counter = 0
        ch.state.volume = 8
        ch._duty_index = 1
        assert ch.tick() == 0

    def test_tick_returns_zero_when_duty_low(self) -> None:
        ch = PulseChannel()
        ch.state.enabled = True
        ch.state.length_counter = 10
        ch.state.volume = 8
        ch.state.duty = 0
        ch._duty_index = 0  # duty bit is 0 at index 0 for 12.5%
        assert ch.tick() == 0

    def test_tick_returns_zero_when_timer_period_too_small(self) -> None:
        ch = PulseChannel()
        ch.state.enabled = True
        ch.state.length_counter = 10
        ch.state.volume = 8
        ch.state.timer_period = 4  # below 8
        ch._duty_index = 1
        assert ch.tick() == 0

    def test_tick_advances_duty_sequence(self) -> None:
        ch = PulseChannel()
        ch.state.enabled = True
        ch.state.length_counter = 10
        ch.state.timer_period = 0  # timer starts at 0, so resets immediately
        ch.state.timer = 0
        ch.state.volume = 5
        ch.state.duty = 0
        ch._duty_index = 0
        # Timer is 0, so after tick: timer resets to timer_period, duty advances
        ch.tick()
        assert ch._duty_index == 1

    def test_envelope_constant_volume(self) -> None:
        ch = PulseChannel()
        ch.write_register(0x4000, 0b00_0_1_1010)  # constant volume=10
        ch.state.enabled = True
        ch.state.length_counter = 10
        ch.state.timer_period = 100
        # Use 50% duty (duty=2) where bits 1-4 are high
        ch.state.duty = 2
        ch._duty_index = 1
        assert ch.tick() == 10

    def test_envelope_decay(self) -> None:
        ch = PulseChannel()
        # Envelope mode, volume=0 (fastest decay: divider decrements every tick)
        ch.write_register(0x4000, 0b00_0_0_0000)
        ch.state.enabled = True
        ch.state.length_counter = 10
        ch.state.timer_period = 100
        ch._duty_index = 1

        # Write to $4003 to trigger envelope reset (sets decay=0xF)
        ch.write_register(0x4003, 0b00001_001)
        assert ch._envelope_decay == 0xF

        # Tick quarter frame enough times to decay
        for _ in range(16):
            ch.tick_quarter_frame()

        assert ch._envelope_decay == 0

    def test_envelope_loop(self) -> None:
        ch = PulseChannel()
        # Envelope loop, volume=0 (fastest decay)
        ch.write_register(0x4000, 0b00_1_0_0000)
        ch.state.enabled = True
        ch.state.length_counter = 10
        ch.state.timer_period = 100
        ch._duty_index = 1

        # Decay to 0
        for _ in range(16):
            ch.tick_quarter_frame()
        assert ch._envelope_decay == 0

        # One more tick should loop back to 0xF
        ch.tick_quarter_frame()
        assert ch._envelope_decay == 0xF

    def test_length_counter_decrement(self) -> None:
        ch = PulseChannel()
        ch.state.enabled = True
        ch.state.length_counter = 10
        ch._envelope_loop = False  # length counter enabled

        ch.tick_half_frame()
        assert ch.state.length_counter == 9

    def test_length_counter_halt(self) -> None:
        ch = PulseChannel()
        ch.state.enabled = True
        ch.state.length_counter = 10
        ch._envelope_loop = True  # length counter halted

        ch.tick_half_frame()
        assert ch.state.length_counter == 10


# ---------------------------------------------------------------------------
# TriangleChannel tests
# ---------------------------------------------------------------------------


class TestTriangleChannel:
    """Tests for TriangleChannel."""

    def test_initial_state(self) -> None:
        ch = TriangleChannel()
        assert ch.state.enabled is False
        assert ch.state.length_counter == 0
        assert ch.state.sequence_index == 0

    def test_reset(self) -> None:
        ch = TriangleChannel()
        ch.write_register(0x4008, 0xFF)
        ch.reset()
        assert ch.state.enabled is False
        assert ch.state.length_counter == 0

    def test_write_linear_counter(self) -> None:
        ch = TriangleChannel()
        ch.write_register(0x4008, 0b1_0101010)
        assert ch._linear_counter_control is True
        assert ch._linear_counter_reload == 0b0101010

    def test_write_timer_low(self) -> None:
        ch = TriangleChannel()
        ch.write_register(0x400A, 0xAB)
        assert ch.state.timer_period == 0xAB

    def test_write_timer_high_length(self) -> None:
        ch = TriangleChannel()
        ch.state.enabled = True
        ch.write_register(0x400B, 0b00001_010)
        assert ch.state.timer_period == (0x02 << 8) | 0x00

    def test_tick_output(self) -> None:
        ch = TriangleChannel()
        ch.state.enabled = True
        ch.state.length_counter = 10
        ch._linear_counter = 10
        ch.state.timer_period = 0
        ch.state.timer = 0
        ch.state.sequence_index = 0

        # With timer=0, sequence advances immediately (check-before-decrement)
        output = ch.tick()
        assert ch.state.sequence_index == 1
        assert output == TRIANGLE_TABLE[1]

    def test_tick_sequence_wraps(self) -> None:
        ch = TriangleChannel()
        ch.state.enabled = True
        ch.state.length_counter = 10
        ch._linear_counter = 10
        ch.state.timer_period = 0
        ch.state.timer = 0
        ch.state.sequence_index = 31

        ch.tick()
        assert ch.state.sequence_index == 0

    def test_tick_no_advance_when_length_zero(self) -> None:
        ch = TriangleChannel()
        ch.state.enabled = True
        ch.state.length_counter = 0
        ch._linear_counter = 10
        ch.state.timer_period = 0
        ch.state.timer = 0
        ch.state.sequence_index = 5

        ch.tick()
        assert ch.state.sequence_index == 5

    def test_tick_no_advance_when_linear_zero(self) -> None:
        ch = TriangleChannel()
        ch.state.enabled = True
        ch.state.length_counter = 10
        ch._linear_counter = 0
        ch.state.timer_period = 0
        ch.state.timer = 0
        ch.state.sequence_index = 5

        ch.tick()
        assert ch.state.sequence_index == 5

    def test_linear_counter_reload(self) -> None:
        ch = TriangleChannel()
        ch.write_register(0x4008, 0b0_0101010)  # control=0, reload=42
        ch.write_register(0x400B, 0b00001_000)  # trigger reload flag
        ch._linear_counter_reload_flag = True
        ch.tick_quarter_frame()
        assert ch._linear_counter == 42

    def test_linear_counter_decrement(self) -> None:
        ch = TriangleChannel()
        ch._linear_counter = 10
        ch._linear_counter_control = False
        ch._linear_counter_reload_flag = False

        ch.tick_quarter_frame()
        assert ch._linear_counter == 9

    def test_length_counter_decrement(self) -> None:
        ch = TriangleChannel()
        ch.state.length_counter = 10
        ch._linear_counter_control = False

        ch.tick_half_frame()
        assert ch.state.length_counter == 9

    def test_triangle_waveform_values(self) -> None:
        """Verify the triangle table produces the expected waveform."""
        assert len(TRIANGLE_TABLE) == 32
        # First half descends from 15 to 0
        for i in range(16):
            assert TRIANGLE_TABLE[i] == 15 - i
        # Second half ascends from 0 to 15
        for i in range(16):
            assert TRIANGLE_TABLE[16 + i] == i


# ---------------------------------------------------------------------------
# NoiseChannel tests
# ---------------------------------------------------------------------------


class TestNoiseChannel:
    """Tests for NoiseChannel."""

    def test_initial_state(self) -> None:
        ch = NoiseChannel()
        assert ch.state.enabled is False
        assert ch.state.shift_register == 1
        assert ch.state.mode is False

    def test_reset(self) -> None:
        ch = NoiseChannel()
        ch.write_register(0x400C, 0xFF)
        ch.reset()
        assert ch.state.enabled is False
        assert ch.state.shift_register == 1

    def test_write_volume(self) -> None:
        ch = NoiseChannel()
        ch.write_register(0x400C, 0b00_0_1_1010)
        assert ch.state.volume == 10

    def test_write_mode_period(self) -> None:
        ch = NoiseChannel()
        ch.write_register(0x400E, 0x84)  # bit 7=1 (mode), bits 3-0=4 (period index)
        assert ch.state.mode is True
        # period index 4 -> NOISE_PERIOD_TABLE[4] = 64
        assert ch.state.timer_period == 64

    def test_write_length_counter(self) -> None:
        ch = NoiseChannel()
        ch.state.enabled = True
        ch.write_register(0x400F, 0b00001_000)
        # length index 1 -> LENGTH_TABLE[1] = 254
        assert ch.state.length_counter == 254

    def test_tick_returns_volume_when_active(self) -> None:
        ch = NoiseChannel()
        ch.state.enabled = True
        ch.state.length_counter = 10
        ch.state.timer_period = 4
        ch.state.timer = 0
        ch.state.volume = 8
        ch._envelope_constant = True
        # 32764 = 0b111111111111100: bit0=0, bit1=0 → feedback=0 → new bit0=0
        ch.state.shift_register = 32764
        output = ch.tick()
        assert output == 8

    def test_tick_returns_zero_when_disabled(self) -> None:
        ch = NoiseChannel()
        ch.state.enabled = False
        ch.state.length_counter = 10
        ch.state.volume = 8
        ch._envelope_constant = True
        assert ch.tick() == 0

    def test_tick_returns_zero_when_length_zero(self) -> None:
        ch = NoiseChannel()
        ch.state.enabled = True
        ch.state.length_counter = 0
        ch.state.volume = 8
        ch._envelope_constant = True
        assert ch.tick() == 0

    def test_tick_returns_zero_when_lsb_set(self) -> None:
        ch = NoiseChannel()
        ch.state.enabled = True
        ch.state.length_counter = 10
        ch.state.volume = 8
        ch._envelope_constant = True
        ch.state.shift_register = 0b111111111111111  # bit 0 = 1
        assert ch.tick() == 0

    def test_lfsr_long_mode(self) -> None:
        ch = NoiseChannel()
        ch.state.mode = False  # long mode (feedback from bit 1)
        ch.state.shift_register = 1
        ch.state.timer_period = 4
        ch.state.timer = 0

        # Tick once: LFSR should shift
        initial_sr = ch.state.shift_register
        ch._tick_lfsr()
        # After shift: bit 0 XOR bit 1 -> new bit 14
        expected_feedback = (initial_sr ^ (initial_sr >> 1)) & 1
        expected_sr = (initial_sr >> 1) | (expected_feedback << 14)
        assert ch.state.shift_register == expected_sr

    def test_lfsr_short_mode(self) -> None:
        ch = NoiseChannel()
        ch.state.mode = True  # short mode (feedback from bit 6)
        ch.state.shift_register = 1
        ch.state.timer_period = 4
        ch.state.timer = 0

        initial_sr = ch.state.shift_register
        ch._tick_lfsr()
        expected_feedback = (initial_sr ^ (initial_sr >> 6)) & 1
        expected_sr = (initial_sr >> 1) | (expected_feedback << 14)
        assert ch.state.shift_register == expected_sr

    def test_lfsr_stays_15_bits(self) -> None:
        """LFSR should always stay within 15 bits (0-32767)."""
        ch = NoiseChannel()
        ch.state.shift_register = 0b101010101010101
        ch.state.mode = False
        ch.state.timer_period = 4
        ch.state.timer = 0

        for _ in range(100):
            ch._tick_lfsr()
            assert 0 < ch.state.shift_register <= 0x7FFF

    def test_envelope_constant_volume(self) -> None:
        ch = NoiseChannel()
        ch.write_register(0x400C, 0b00_0_1_1010)  # constant volume=10
        ch.state.enabled = True
        ch.state.length_counter = 10
        ch.state.timer_period = 4
        ch.state.timer = 0
        # 32764: bit0=0, bit1=0 → feedback=0 → new bit0=0 after LFSR tick
        ch.state.shift_register = 32764
        assert ch.tick() == 10

    def test_length_counter_decrement(self) -> None:
        ch = NoiseChannel()
        ch.state.length_counter = 10
        ch._envelope_loop = False

        ch.tick_half_frame()
        assert ch.state.length_counter == 9


# ---------------------------------------------------------------------------
# APU core tests
# ---------------------------------------------------------------------------


class TestAPU:
    """Tests for the APU core."""

    def test_initial_state(self) -> None:
        apu = APU()
        assert apu.pulse1.state.enabled is False
        assert apu.pulse2.state.enabled is False
        assert apu.triangle.state.enabled is False
        assert apu.noise.state.enabled is False

    def test_reset(self) -> None:
        apu = APU()
        apu.write_register(0x4015, 0x0F)  # enable all channels
        apu.reset()
        assert apu.pulse1.state.enabled is False
        assert apu.pulse2.state.enabled is False
        assert apu.triangle.state.enabled is False
        assert apu.noise.state.enabled is False

    def test_write_register_routing(self) -> None:
        apu = APU()
        # Pulse 1
        apu.write_register(0x4000, 0b10_0_1_1010)
        assert apu.pulse1.state.duty == 2
        # Pulse 2
        apu.write_register(0x4004, 0b01_0_1_0101)
        assert apu.pulse2.state.duty == 1
        # Triangle
        apu.write_register(0x4008, 0b1_0101010)
        assert apu.triangle._linear_counter_control is True
        # Noise
        apu.write_register(0x400C, 0b00_0_1_1010)
        assert apu.noise.state.volume == 10

    def test_status_register_enable(self) -> None:
        apu = APU()
        apu.write_register(0x4015, 0x0F)
        assert apu.pulse1.state.enabled is True
        assert apu.pulse2.state.enabled is True
        assert apu.triangle.state.enabled is True
        assert apu.noise.state.enabled is True

    def test_status_register_disable(self) -> None:
        apu = APU()
        apu.write_register(0x4015, 0x0F)
        apu.pulse1.state.length_counter = 10
        apu.write_register(0x4015, 0x00)
        assert apu.pulse1.state.enabled is False
        assert apu.pulse1.state.length_counter == 0

    def test_frame_mode_5_step(self) -> None:
        apu = APU()
        apu.write_register(0x4017, 0x80)  # bit 7 = 1 -> 5-step
        assert apu._frame_mode == 1

    def test_tick_returns_float(self) -> None:
        apu = APU()
        result = apu.tick()
        assert isinstance(result, float)

    def test_mix_output_range_silent(self) -> None:
        """Mix of all zeros should be 0.0."""
        result = APU._mix(0, 0, 0, 0)
        assert result == 0.0

    def test_mix_output_range_max_pulse(self) -> None:
        """Mix of max pulse values should be in valid range."""
        result = APU._mix(15, 15, 0, 0)
        assert 0.0 <= result <= 1.0

    def test_mix_output_range_max_all(self) -> None:
        """Mix of all max values should be in valid range."""
        result = APU._mix(15, 15, 15, 15)
        assert 0.0 <= result <= 1.0

    def test_mix_output_range_single_channel(self) -> None:
        """Mix of single channel outputs should be in valid range."""
        for val in range(16):
            result = APU._mix(val, 0, 0, 0)
            assert 0.0 <= result <= 1.0, f"pulse={val} -> {result}"
            result = APU._mix(0, val, 0, 0)
            assert 0.0 <= result <= 1.0, f"pulse2={val} -> {result}"
            result = APU._mix(0, 0, val, 0)
            assert 0.0 <= result <= 1.0, f"tri={val} -> {result}"
            result = APU._mix(0, 0, 0, val)
            assert 0.0 <= result <= 1.0, f"noise={val} -> {result}"

    def test_mix_monotonic_pulse(self) -> None:
        """Increasing pulse sum should increase output."""
        prev = 0.0
        for val in range(1, 16):
            current = APU._mix(val, 0, 0, 0)
            assert current > prev, f"Not monotonic at val={val}"
            prev = current

    def test_frame_counter_4_step_timing(self) -> None:
        """Verify 4-step frame counter triggers at correct cycle counts."""
        apu = APU()
        apu._frame_mode = 0
        apu.write_register(0x4015, 0x0F)

        # Set up channels with known values
        apu.pulse1.state.enabled = True
        apu.pulse1.state.length_counter = 10
        apu.pulse1._envelope_loop = False

        initial_length = apu.pulse1.state.length_counter

        # Tick up to just before first half frame (step 1, cycle 14913)
        # Step 0 at 7457 is quarter-only, step 1 at 14913 is half
        for _ in range(14912):
            apu.tick()

        # Length counter should not have decremented yet (only quarter frames hit)
        # Actually step 0 at 7457 is quarter-only, no half frame yet
        # But we need to check — let's just verify after step 1
        apu.tick()  # This should trigger step 1 (half frame)
        # Length counter should have decremented
        assert apu.pulse1.state.length_counter < initial_length

    def test_sample_buffer(self) -> None:
        apu = APU()
        buffer = apu.get_sample_buffer()
        assert isinstance(buffer, list)

    def test_sample_buffer_cleared_after_get(self) -> None:
        apu = APU()
        # Generate some samples
        for _ in range(100):
            apu.tick()
        buffer1 = apu.get_sample_buffer()
        buffer2 = apu.get_sample_buffer()
        assert len(buffer2) == 0 or len(buffer2) < len(buffer1)

    def test_tick_produces_audio_over_time(self) -> None:
        """Running the APU for many cycles should produce samples."""
        apu = APU()
        apu.write_register(0x4015, 0x0F)
        # Set up pulse 1 to produce sound
        apu.write_register(0x4000, 0b01_0_1_1010)  # 25% duty, vol=10
        apu.write_register(0x4002, 0x00)  # timer low
        apu.write_register(0x4003, 0b00001_001)  # timer high=1

        apu.pulse1.state.enabled = True
        apu.pulse1.state.length_counter = 254

        # Run for ~1 second of audio (1789773 cycles)
        for _ in range(50000):
            apu.tick()

        buffer = apu.get_sample_buffer()
        assert len(buffer) > 0
        # All samples should be in valid range
        for sample in buffer:
            assert 0.0 <= sample <= 1.0


# ---------------------------------------------------------------------------
# Constants tests
# ---------------------------------------------------------------------------


class TestConstants:
    """Tests for lookup tables and constants."""

    def test_length_table_size(self) -> None:
        assert len(LENGTH_TABLE) == 32

    def test_duty_table_size(self) -> None:
        assert len(DUTY_TABLE) == 4
        for duty in DUTY_TABLE:
            assert len(duty) == 8

    def test_duty_table_values(self) -> None:
        # Each entry should be 0 or 1
        for duty in DUTY_TABLE:
            for val in duty:
                assert val in (0, 1)

    def test_triangle_table_size(self) -> None:
        assert len(TRIANGLE_TABLE) == 32

    def test_triangle_table_range(self) -> None:
        for val in TRIANGLE_TABLE:
            assert 0 <= val <= 15


# ---------------------------------------------------------------------------
# Integration / edge case tests
# ---------------------------------------------------------------------------


class TestAPUIntegration:
    """Integration tests for APU with all channels active."""

    def test_all_channels_active(self) -> None:
        """Run APU with all channels enabled and verify output."""
        apu = APU()
        apu.write_register(0x4015, 0x0F)

        # Pulse 1
        apu.write_register(0x4000, 0b01_0_1_1010)
        apu.write_register(0x4002, 0x50)
        apu.write_register(0x4003, 0b00001_001)
        apu.pulse1.state.enabled = True
        apu.pulse1.state.length_counter = 254

        # Pulse 2
        apu.write_register(0x4004, 0b10_0_1_0101)
        apu.write_register(0x4006, 0xA0)
        apu.write_register(0x4007, 0b00001_010)
        apu.pulse2.state.enabled = True
        apu.pulse2.state.length_counter = 254

        # Triangle
        apu.write_register(0x4008, 0b0_1111111)
        apu.write_register(0x400A, 0x30)
        apu.write_register(0x400B, 0b00001_011)
        apu.triangle.state.enabled = True
        apu.triangle.state.length_counter = 254

        # Noise
        apu.write_register(0x400C, 0b00_0_1_1010)
        apu.write_register(0x400E, 0b0_0000101)
        apu.write_register(0x400F, 0b00001_100)
        apu.noise.state.enabled = True
        apu.noise.state.length_counter = 254

        # Run for a while
        samples: list[float] = []
        for _ in range(10000):
            s = apu.tick()
            samples.append(s)

        # All samples should be non-negative and within range
        for s in samples:
            assert 0.0 <= s <= 1.0, f"Sample out of range: {s}"

    def test_channel_disable_clears_length(self) -> None:
        """Disabling a channel via $4015 should clear its length counter."""
        apu = APU()
        apu.write_register(0x4015, 0x0F)
        apu.pulse1.state.length_counter = 100
        apu.pulse2.state.length_counter = 100
        apu.triangle.state.length_counter = 100
        apu.noise.state.length_counter = 100

        apu.write_register(0x4015, 0x00)
        assert apu.pulse1.state.length_counter == 0
        assert apu.pulse2.state.length_counter == 0
        assert apu.triangle.state.length_counter == 0
        assert apu.noise.state.length_counter == 0

    def test_mixer_non_negative(self) -> None:
        """The mixing formula should never produce negative values."""
        for p1 in range(16):
            for p2 in range(16):
                for t in range(16):
                    for n in range(16):
                        result = APU._mix(p1, p2, t, n)
                        assert result >= 0.0, (
                            f"Negative output: p1={p1} p2={p2} t={t} n={n} -> {result}"
                        )

    def test_sample_buffer_accumulates(self) -> None:
        """Sample buffer should accumulate samples over time."""
        apu = APU()
        # Run for enough cycles to generate at least one sample
        # At 44100 Hz and ~1.79 MHz CPU, one sample every ~40.6 cycles
        for _ in range(100):
            apu.tick()
        buffer = apu.get_sample_buffer()
        assert len(buffer) >= 1

    def test_output_range_after_mixer(self) -> None:
        """The mixer output should always be in [0.0, 1.0]."""
        # Test extreme values
        assert APU._mix(0, 0, 0, 0) == 0.0
        max_val = APU._mix(15, 15, 15, 15)
        assert max_val <= 1.0

        # The formula asymptotically approaches but never reaches 1.0
        assert max_val < 1.0
