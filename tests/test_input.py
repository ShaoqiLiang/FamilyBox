"""Tests for the input module (Joystick controller)."""

import pytest

from familybox.input.controller import Joystick
from familybox.types import NESButton


# ---------------------------------------------------------------------------
# T-INPUT-02 / T-INPUT-03 / T-INPUT-04: strobe latch
# ---------------------------------------------------------------------------


class TestStrobeLatch:
    """Strobe signal latches button state into the shift register."""

    def test_strobe_on_returns_bit0(self) -> None:
        """While strobe is active (write $01), read always returns bit 0."""
        js = Joystick()
        js.set_button(NESButton.A, True)
        js.write(0x01)  # strobe on
        assert js.read() == 1
        # Repeated reads while strobe is on keep returning bit 0
        assert js.read() == 1
        assert js.read() == 1

    def test_strobe_off_shifts_out(self) -> None:
        """After strobe is released (write $00), reads shift out one bit at a time."""
        js = Joystick()
        js.set_button(NESButton.A, True)
        js.set_button(NESButton.START, True)
        js.write(0x01)  # strobe on -- latch
        js.write(0x00)  # strobe off -- ready to shift
        # Bit 0 (A) should come out first
        assert js.read() == 1  # A
        assert js.read() == 0  # B
        assert js.read() == 0  # Select
        assert js.read() == 1  # Start


# ---------------------------------------------------------------------------
# T-INPUT-04 / T-INPUT-07: 8 sequential reads
# ---------------------------------------------------------------------------


class TestSequentialRead:
    """Eight consecutive reads return A/B/Select/Start/Up/Down/Left/Right."""

    @pytest.mark.parametrize(
        "button,position",
        [
            (NESButton.A, 0),
            (NESButton.B, 1),
            (NESButton.SELECT, 2),
            (NESButton.START, 3),
            (NESButton.UP, 4),
            (NESButton.DOWN, 5),
            (NESButton.LEFT, 6),
            (NESButton.RIGHT, 7),
        ],
    )
    def test_single_button_read(self, button: NESButton, position: int) -> None:
        js = Joystick()
        js.set_button(button, True)
        js.write(0x01)
        js.write(0x00)
        for i in range(8):
            expected = 1 if i == position else 0
            assert js.read() == expected, f"position {i} should be {expected}"

    def test_all_buttons_pressed(self) -> None:
        """All 8 buttons pressed returns 1 for every read."""
        js = Joystick()
        for btn in NESButton:
            js.set_button(btn, True)
        js.write(0x01)
        js.write(0x00)
        for i in range(8):
            assert js.read() == 1, f"position {i} should be 1"

    def test_no_buttons_pressed(self) -> None:
        """No buttons pressed returns 0 for every read."""
        js = Joystick()
        js.write(0x01)
        js.write(0x00)
        for i in range(8):
            assert js.read() == 0, f"position {i} should be 0"


# ---------------------------------------------------------------------------
# T-INPUT-08: button combinations
# ---------------------------------------------------------------------------


class TestButtonCombinations:
    """Multiple buttons pressed simultaneously."""

    def test_a_and_b(self) -> None:
        js = Joystick()
        js.set_button(NESButton.A, True)
        js.set_button(NESButton.B, True)
        js.write(0x01)
        js.write(0x00)
        assert js.read() == 1  # A
        assert js.read() == 1  # B
        assert js.read() == 0  # Select

    def test_up_right(self) -> None:
        js = Joystick()
        js.set_button(NESButton.UP, True)
        js.set_button(NESButton.RIGHT, True)
        js.write(0x01)
        js.write(0x00)
        # Skip to positions 4 (UP) and 7 (RIGHT)
        for i in range(8):
            val = js.read()
            if i == 4:
                assert val == 1  # UP
            elif i == 7:
                assert val == 1  # RIGHT
            else:
                assert val == 0

    def test_select_start_a(self) -> None:
        js = Joystick()
        js.set_button(NESButton.SELECT, True)
        js.set_button(NESButton.START, True)
        js.set_button(NESButton.A, True)
        js.write(0x01)
        js.write(0x00)
        assert js.read() == 1  # A
        assert js.read() == 0  # B
        assert js.read() == 1  # Select
        assert js.read() == 1  # Start
        for _ in range(4):
            assert js.read() == 0


# ---------------------------------------------------------------------------
# T-INPUT-05: set_button set/clear
# ---------------------------------------------------------------------------


class TestSetButton:
    """set_button correctly sets and clears individual buttons."""

    def test_set_and_clear_a(self) -> None:
        js = Joystick()
        js.set_button(NESButton.A, True)
        js.write(0x01)
        assert js.read() == 1
        js.set_button(NESButton.A, False)
        js.write(0x01)
        assert js.read() == 0

    def test_set_and_clear_all_buttons(self) -> None:
        js = Joystick()
        for btn in NESButton:
            js.reset()
            js.set_button(btn, True)
            js.write(0x01)
            js.write(0x00)
            # Shift to the correct bit position
            for _ in range(btn):
                js.read()
            assert js.read() == 1, f"{btn.name} should be pressed"
            js.reset()
            js.set_button(btn, True)
            js.set_button(btn, False)
            js.write(0x01)
            js.write(0x00)
            for _ in range(btn):
                js.read()
            assert js.read() == 0, f"{btn.name} should be released"

    def test_set_does_not_affect_other_buttons(self) -> None:
        js = Joystick()
        js.set_button(NESButton.A, True)
        js.set_button(NESButton.UP, True)
        # Clear only A
        js.set_button(NESButton.A, False)
        js.write(0x01)
        js.write(0x00)
        assert js.read() == 0  # A cleared
        assert js.read() == 0  # B
        assert js.read() == 0  # Select
        assert js.read() == 0  # Start
        assert js.read() == 1  # UP still set


# ---------------------------------------------------------------------------
# T-INPUT-06: reset
# ---------------------------------------------------------------------------


class TestReset:
    """reset() clears all internal state."""

    def test_reset_clears_buttons(self) -> None:
        js = Joystick()
        js.set_button(NESButton.A, True)
        js.set_button(NESButton.START, True)
        js.reset()
        js.write(0x01)
        js.write(0x00)
        for _ in range(8):
            assert js.read() == 0

    def test_reset_clears_strobe(self) -> None:
        js = Joystick()
        js.set_button(NESButton.A, True)
        js.write(0x01)  # strobe on
        js.reset()
        # After reset strobe is off, shift register is empty
        js.write(0x01)
        js.write(0x00)
        assert js.read() == 0

    def test_reset_idempotent(self) -> None:
        js = Joystick()
        js.set_button(NESButton.B, True)
        js.reset()
        js.reset()  # double reset should be safe
        js.write(0x01)
        js.write(0x00)
        for _ in range(8):
            assert js.read() == 0


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    """Joystick satisfies the ControllerInterface protocol."""

    def test_satisfies_protocol(self) -> None:
        from familybox.types import ControllerInterface

        js = Joystick()
        assert isinstance(js, ControllerInterface)
