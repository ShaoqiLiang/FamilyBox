"""ctypes binding for the C FamilyBox core."""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path
from typing import Any

_LIB_NAME = (
    "familybox_core.dll"
    if sys.platform == "win32"
    else "familybox_core.dylib"
    if sys.platform == "darwin"
    else "familybox_core.so"
)


def _find_lib() -> Path:
    if getattr(sys, "frozen", False):
        # PyInstaller onefile extracts to sys._MEIPASS; onedir uses exe dir
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        for cand in (
            base / "familybox" / _LIB_NAME,
            base / _LIB_NAME,
            Path(sys.executable).parent / _LIB_NAME,
            Path(sys.executable).parent / "familybox" / _LIB_NAME,
        ):
            if cand.exists():
                return cand
    return Path(__file__).resolve().parent / _LIB_NAME


_LIB_PATH = _find_lib()

# Must match FB_CORE_ABI_VERSION in familybox/include/familybox.h. The core
# reports its value via nes_abi_version(); a mismatch means the DLL on disk
# is older or newer than this binding — fail fast with a rebuild hint.
REQUIRED_ABI_VERSION = 1


class NesCore:
    """Thin wrapper around libfamilybox.

    Sole ctypes.CDLL load point; every familybox.h function has exactly one
    prototype declaration here (design doc §5).
    """

    def __init__(self) -> None:
        if not _LIB_PATH.exists():
            raise FileNotFoundError(
                f"C core not found: {_LIB_PATH}. Build with familybox\\build.bat (Windows) or familybox/build.sh"
            )
        self._lib = ctypes.CDLL(str(_LIB_PATH))
        lib = self._lib

        lib.nes_abi_version.restype = ctypes.c_int32
        lib.nes_abi_version.argtypes = []
        abi_fn = getattr(lib, "nes_abi_version", None)
        if abi_fn is None:
            raise RuntimeError(
                f"C core at {_LIB_PATH} does not export nes_abi_version — "
                "the DLL predates the ABI freeze. Rebuild with "
                "familybox\\build.bat."
            )
        actual = int(abi_fn())
        if actual != REQUIRED_ABI_VERSION:
            raise RuntimeError(
                f"ABI version mismatch: core at {_LIB_PATH} reports "
                f"{actual}, binding expects {REQUIRED_ABI_VERSION}. "
                "The DLL is stale or newer than the binding — rebuild with "
                "familybox\\build.bat or update familybox/core_api.py."
            )

        lib.nes_video.restype = ctypes.POINTER(ctypes.c_uint8)
        lib.nes_video.argtypes = [ctypes.c_void_p]

        lib.nes_create.restype = ctypes.c_void_p
        lib.nes_create.argtypes = []
        lib.nes_destroy.restype = None
        lib.nes_destroy.argtypes = [ctypes.c_void_p]
        lib.nes_load_rom.restype = ctypes.c_int
        lib.nes_load_rom.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        lib.nes_reset.restype = None
        lib.nes_reset.argtypes = [ctypes.c_void_p]
        lib.nes_set_buttons.restype = None
        lib.nes_set_buttons.argtypes = [ctypes.c_void_p, ctypes.c_uint8]
        lib.nes_run_frame.restype = ctypes.c_int
        lib.nes_run_frame.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.POINTER(ctypes.c_int16),
            ctypes.c_int,
        ]
        lib.nes_get_debug.restype = None
        lib.nes_get_debug.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_uint16),
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.POINTER(ctypes.c_uint8),
        ]
        lib.nes_dump_palette.restype = None
        lib.nes_dump_palette.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_uint8),
        ]
        lib.nes_peek_ppu.restype = ctypes.c_uint8
        lib.nes_peek_ppu.argtypes = [ctypes.c_void_p, ctypes.c_uint16]
        lib.nes_get_ppuctrl.restype = ctypes.c_uint8
        lib.nes_get_ppuctrl.argtypes = [ctypes.c_void_p]
        lib.nes_get_ppumask.restype = ctypes.c_uint8
        lib.nes_get_ppumask.argtypes = [ctypes.c_void_p]
        lib.nes_get_v.restype = ctypes.c_uint16
        lib.nes_get_v.argtypes = [ctypes.c_void_p]
        lib.nes_get_status.restype = ctypes.c_uint8
        lib.nes_get_status.argtypes = [ctypes.c_void_p]
        lib.nes_dump_oam.restype = None
        lib.nes_dump_oam.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint8)]
        lib.nes_peek_cpu.restype = ctypes.c_uint8
        lib.nes_peek_cpu.argtypes = [ctypes.c_void_p, ctypes.c_uint16]
        lib.nes_ctrl_log.restype = ctypes.c_int
        lib.nes_ctrl_log.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_int,
        ]
        lib.nes_get_v_samples.restype = None
        lib.nes_get_v_samples.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_uint16),
        ]
        lib.nes_get_t.restype = ctypes.c_uint16
        lib.nes_get_t.argtypes = [ctypes.c_void_p]
        lib.nes_get_s0_hits.restype = ctypes.c_int
        lib.nes_get_s0_hits.argtypes = [ctypes.c_void_p]
        lib.nes_reset_s0_hits.restype = None
        lib.nes_reset_s0_hits.argtypes = [ctypes.c_void_p]
        lib.nes_debug_enabled.restype = ctypes.c_int
        lib.nes_debug_enabled.argtypes = []
        lib.nes_get_scroll_writes.restype = ctypes.c_int
        lib.nes_get_scroll_writes.argtypes = [ctypes.c_void_p]
        lib.nes_wrlog_copy.restype = ctypes.c_int
        lib.nes_wrlog_copy.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_int,
        ]
        lib.nes_get_nmi_count.restype = ctypes.c_int
        lib.nes_get_nmi_count.argtypes = [ctypes.c_void_p]
        lib.nes_get_last_s0_sl.restype = ctypes.c_int
        lib.nes_get_last_s0_sl.argtypes = [ctypes.c_void_p]

        self._handle = lib.nes_create()
        if not self._handle:
            raise MemoryError("nes_create failed")
        # Zero-copy video (design doc §4.2/§5): the core owns the frame
        # buffer; we hold one long-lived typed view over it. Valid until the
        # next run_frame/reset on this handle — copy if retaining.
        video = ctypes.cast(
            lib.nes_video(self._handle),
            ctypes.POINTER(ctypes.c_uint8 * (256 * 240 * 3)),
        ).contents
        # cast("B"): ctypes reports format "<B", which memoryview indexing
        # rejects; the cast view supports indexing/hashing/frombuffer.
        self._video_view = memoryview(video).cast("B")
        self._pcm = (ctypes.c_int16 * 8192)()
        self._lib_path = _LIB_PATH

    def close(self) -> None:
        if getattr(self, "_handle", None):
            self._lib.nes_destroy(self._handle)
            self._handle = None

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def load_rom(self, path: str) -> int:
        return self._lib.nes_load_rom(self._handle, str(path).encode("utf-8"))

    def reset(self) -> None:
        self._lib.nes_reset(self._handle)

    def set_buttons(self, buttons: int) -> None:
        self._lib.nes_set_buttons(self._handle, buttons & 0xFF)

    def abi_version(self) -> int:
        """ABI version reported by the loaded C core."""
        return int(self._lib.nes_abi_version())

    def run_frame(self) -> tuple[memoryview, bytes]:
        """Run one frame. Returns (rgb_view, pcm_bytes).

        rgb_view is a zero-copy view over the core-internal frame buffer
        (256*240*3, RGB). It stays valid only until the next run_frame or
        reset on this handle; hash/blit it immediately, or copy (bytes) if
        retaining across frames. This removes the two 184 KB copies per
        frame the old binding performed.
        """
        n = self._lib.nes_run_frame(self._handle, None, self._pcm, 8192)
        if n < 0:
            raise RuntimeError("nes_run_frame failed")
        pcm = bytes(memoryview(self._pcm).cast("B")[: n * 2]) if n else b""
        return self._video_view, pcm

    def debug(self) -> dict[str, int]:
        pc = ctypes.c_uint16(0)
        a = ctypes.c_uint8(0)
        x = ctypes.c_uint8(0)
        y = ctypes.c_uint8(0)
        p = ctypes.c_uint8(0)
        self._lib.nes_get_debug(
            self._handle,
            ctypes.byref(pc),
            ctypes.byref(a),
            ctypes.byref(x),
            ctypes.byref(y),
            ctypes.byref(p),
        )
        return {
            "pc": pc.value,
            "a": a.value,
            "x": x.value,
            "y": y.value,
            "p": p.value,
        }

    def dump_palette(self) -> list[int]:
        buf = (ctypes.c_uint8 * 32)()
        self._lib.nes_dump_palette(self._handle, buf)
        return list(buf)

    def peek_ppu(self, addr: int) -> int:
        return int(self._lib.nes_peek_ppu(self._handle, addr))

    def ppu_regs(self) -> dict[str, int]:
        return {
            "ctrl": int(self._lib.nes_get_ppuctrl(self._handle)),
            "mask": int(self._lib.nes_get_ppumask(self._handle)),
            "v": int(self._lib.nes_get_v(self._handle)),
            "status": int(self._lib.nes_get_status(self._handle)),
        }

    def dump_oam(self) -> list[int]:
        buf = (ctypes.c_uint8 * 256)()
        self._lib.nes_dump_oam(self._handle, buf)
        return list(buf)

    def peek_cpu(self, addr: int) -> int:
        return int(self._lib.nes_peek_cpu(self._handle, addr))

    def ctrl_log(self) -> list[int]:
        buf = (ctypes.c_uint8 * 32)()
        n = int(self._lib.nes_ctrl_log(self._handle, buf, 32))
        return list(buf[:n])

    def v_samples(self) -> list[int]:
        buf = (ctypes.c_uint16 * 4)()
        self._lib.nes_get_v_samples(self._handle, buf)
        return [int(buf[i]) for i in range(4)]

    def get_t(self) -> int:
        return int(self._lib.nes_get_t(self._handle))

    def s0_hits(self) -> int:
        return int(self._lib.nes_get_s0_hits(self._handle))

    def reset_s0_hits(self) -> None:
        self._lib.nes_reset_s0_hits(self._handle)

    def debug_enabled(self) -> bool:
        return bool(self._lib.nes_debug_enabled())

    def scroll_writes(self) -> int:
        return int(self._lib.nes_get_scroll_writes(self._handle))

    def nmi_count(self) -> int:
        return int(self._lib.nes_get_nmi_count(self._handle))

    def last_s0_sl(self) -> int:
        return int(self._lib.nes_get_last_s0_sl(self._handle))

    def wrlog(self) -> list[dict[str, Any]]:
        """Pull recent PPU register writes. kind: 0=ctrl 1=mask 4=$2005 5=$2006 6=$2007."""
        buf = (ctypes.c_uint8 * (128 * 8))()
        n = int(self._lib.nes_wrlog_copy(self._handle, buf, 128))
        KIND = {0: "ctrl", 1: "mask", 4: "scroll2005", 5: "addr2006", 6: "data2007"}
        out = []
        for i in range(n):
            b = i * 8
            kind = buf[b]
            val = buf[b + 1]
            addr = buf[b + 2] | (buf[b + 3] << 8)
            sl = buf[b + 4] | (buf[b + 5] << 8)
            if sl >= 32768:
                sl -= 65536
            cy = buf[b + 6] | (buf[b + 7] << 8)
            out.append(
                {
                    "kind": KIND.get(kind, str(kind)),
                    "value": val,
                    "addr": addr,
                    "scanline": sl,
                    "cycle": cy,
                }
            )
        return out
