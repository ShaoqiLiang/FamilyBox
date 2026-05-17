"""NES controller implementation."""

#  *
#  * @Author: ShaoqiLiang
#  * @Date: 2026-05-16 22:07:49
#  * @LastEditors: ShaoqiLiang
#  *

from familybox.types import NESButton


class Joystick:
    """NES controller (joypad) implementation.

    Emulates the standard NES controller's shift-register based serial
    interface accessed through CPU ports $4016/$4017.
    """

    def __init__(self) -> None:
        self._buttons: int = 0
        self._shift_register: int = 0
        self._strobe: bool = False

    def read(self) -> int:
        """Read one bit from the controller shift register.

        In strobe mode the current bit 0 of ``_buttons`` is returned
        repeatedly.  Outside strobe mode the lowest bit of the shift
        register is returned and the register is shifted right by one.

        Returns:
            0 or 1.
        """
        if self._strobe:
            return self._buttons & 0x01

        value = self._shift_register & 0x01
        self._shift_register >>= 1
        return value

    def write(self, value: int) -> None:
        """Write to the controller port (strobe signal).

        When bit 0 is set the button state is latched into the shift
        register.  When bit 0 is cleared the shift register is ready to
        be read out serially.

        Args:
            value: Data bus value written by the CPU.
        """
        self._strobe = bool(value & 0x01)
        if self._strobe:
            self._shift_register = self._buttons

    def set_button(self, button: NESButton, pressed: bool) -> None:
        """Set or clear a single button in the button state bit-field.

        Args:
            button: The button to modify.
            pressed: ``True`` to press, ``False`` to release.
        """
        if pressed:
            self._buttons |= 1 << button
        else:
            self._buttons &= ~(1 << button)

    def reset(self) -> None:
        """Reset all controller state to initial values."""
        self._buttons = 0
        self._shift_register = 0
        self._strobe = False
