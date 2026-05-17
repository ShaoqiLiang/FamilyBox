"""Tests for familybox.main entry point."""

import pytest

from familybox.main import parse_args


class TestParseArgs:
    """Command-line argument parsing tests."""

    def test_rom_path_required(self) -> None:
        """ROM path is required."""
        with pytest.raises(SystemExit):
            parse_args([])

    def test_rom_path(self) -> None:
        """ROM path is parsed correctly."""
        args = parse_args(["rom/super-mario-bros.nes"])
        assert args.rom == "rom/super-mario-bros.nes"
        assert args.headless is False

    def test_headless_flag(self) -> None:
        """--headless flag is parsed."""
        args = parse_args(["rom/test.nes", "--headless"])
        assert args.headless is True

    def test_log_level_default(self) -> None:
        """Default log level is WARNING."""
        args = parse_args(["rom/test.nes"])
        assert args.log_level == "WARNING"

    def test_log_level_custom(self) -> None:
        """Custom log level is parsed."""
        args = parse_args(["rom/test.nes", "--log-level", "DEBUG"])
        assert args.log_level == "DEBUG"

    def test_invalid_log_level(self) -> None:
        """Invalid log level causes exit."""
        with pytest.raises(SystemExit):
            parse_args(["rom/test.nes", "--log-level", "INVALID"])
