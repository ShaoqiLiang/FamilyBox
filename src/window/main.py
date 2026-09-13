"""FamilyBox — FC/NES emulator entry point."""

#  *
#  * @Author: ShaoqiLiang
#  * @Date: 2026-05-16 22:07:49
#  * @LastEditors: ShaoqiLiang
#  *

import argparse
import logging
import sys
from pathlib import Path

from window.frontends.pygame_frontend import NES


def _default_rom() -> str | None:
    """Bundled ROM next to the package / in PyInstaller _MEIPASS."""
    candidates = []
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        candidates.append(base / "rom" / "super-mario-bros.nes")
        candidates.append(Path(sys.executable).parent / "rom" / "super-mario-bros.nes")
    here = Path(__file__).resolve().parents[2]
    candidates.append(here / "rom" / "super-mario-bros.nes")
    for p in candidates:
        if p.is_file():
            return str(p)
    return None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="FamilyBox — FC/NES emulator",
    )
    parser.add_argument(
        "rom",
        nargs="?",
        default=None,
        help="Path to .nes ROM file (default: bundled super-mario-bros.nes)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run without creating a window (for testing)",
    )
    parser.add_argument(
        "--region",
        default="ntsc",
        choices=["ntsc", "pal"],
        help="Video timing standard (default: ntsc). Use pal for European "
        "cartridges: 312 lines / 50.007 fps / 1.66 MHz CPU.",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level (default: WARNING)",
    )
    args = parser.parse_args(argv)
    if args.rom is None:
        args.rom = _default_rom()
        if args.rom is None:
            parser.error("No ROM given and bundled super-mario-bros.nes not found")
    return args


def main(argv: list[str] | None = None) -> None:
    """FamilyBox entry point."""
    args = parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s:%(name)s:%(message)s",
    )
    from window.binding.core_api import NesCore, _LIB_PATH
    from window.frontends.pygame_frontend import _debug_on

    # Always show build flavour so it's obvious which DLL is loaded
    try:
        probe = NesCore()
        c_debug = bool(probe.debug_enabled())
        probe.close()
    except Exception:
        c_debug = False
    py_debug = _debug_on()
    mode = "DEBUG" if (c_debug or py_debug) else "RELEASE"
    print("=" * 48, flush=True)
    print(f"  FamilyBox  mode={mode}", flush=True)
    print(f"  C core debug : {c_debug}", flush=True)
    print(f"  Python debug : {py_debug}", flush=True)
    print(f"  DLL          : {_LIB_PATH}", flush=True)
    print(f"  ROM          : {args.rom}", flush=True)
    print("  JUMP = Space / Z / N / J     RUN = M / K", flush=True)
    print("  MAXIMIZE = title-bar button; ESC = restore small window", flush=True)
    print("  START = Enter / Tab          SELECT = Shift", flush=True)
    print("  MOVE = Arrows or WASD", flush=True)
    print("=" * 48, flush=True)
    logging.getLogger(__name__).info("DLL: %s mode=%s", _LIB_PATH, mode)

    nes = None
    try:
        nes = NES(args.rom, headless=args.headless, region=args.region)
        nes.run()
    except FileNotFoundError as e:
        print(f"Error: ROM file not found: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: Invalid ROM file: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        if nes is not None:
            nes.close()


if __name__ == "__main__":
    main()
