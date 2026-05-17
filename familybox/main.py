"""FamilyBox — FC/NES emulator entry point."""

#  *
#  * @Author: ShaoqiLiang
#  * @Date: 2026-05-16 22:07:49
#  * @LastEditors: ShaoqiLiang
#  *

import argparse
import logging
import sys

from familybox.nes import NES


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="FamilyBox — FC/NES emulator",
    )
    parser.add_argument(
        "rom",
        help="Path to .nes ROM file",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without creating a window (for testing)",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level (default: WARNING)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """FamilyBox entry point."""
    args = parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s:%(name)s:%(message)s",
    )

    try:
        nes = NES(args.rom, headless=args.headless)
        nes.run()
    except FileNotFoundError:
        print(f"Error: ROM file not found: {args.rom}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: Invalid ROM file: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nExiting...")


if __name__ == "__main__":
    main()
