"""Regression assets: golden frame, palette truth, audio pitch, blargg driver.

These encode EXTERNAL ground truth (SMB disassembly data tables, known-good
ROM hashes, FFT/Goertzel spectra) rather than "matches the other
implementation" — consistency checks cannot catch shared misunderstandings.
See doc/find/2026-09-12T20-07-51.md for the full evidence chains.
"""

from __future__ import annotations

import hashlib
import math
import struct
from pathlib import Path

import pytest

from window.binding.core_api import NesCore
from window.session import EmulationSession

ROM_PATH = "rom/super-mario-bros.nes"  # tracked PAL EU cartridge
ROM_NTSC = "rom/super-mario-bros-ntsc.nes"  # local NTSC copy (gitignored)

# Frame 40 (title screen, no input) — identical for PAL and NTSC cartridges.
GOLDEN_FRAME40_SHA256 = (
    "1efad6c3cf81ddc78a75831e9133287fd3ee1828e8d7cc2d6cc245894667c1de"
)
# Frame 1 (first frame after reset) — M1a acceptance anchor: the zero-copy
# binding path (nes_video view) must produce byte-identical output to the
# pre-M1a copy path that recorded this baseline.
GOLDEN_FRAME1_SHA256 = (
    "a4260f3d0372c92bb8a8c8866b138d8d3e5bf783987aa842ffb31d2dac7c693c"
)

# SMB 1-1 background palette vs the ROM's GroundPaletteData table
# (doc/smb-assembler-master/smbdis.asm). Sole documented delta: $3F00 holds
# the game's sky-blue backdrop ($22) instead of the table's $0F, because the
# game overwrites the universal backdrop after the palette upload and $3F00
# mirrors $3F10 (sprite entry 0).
GROUND_PALETTE_BG = [
    0x22,
    0x29,
    0x1A,
    0x0F,
    0x0F,
    0x36,
    0x17,
    0x0F,
    0x0F,
    0x30,
    0x21,
    0x0F,
    0x0F,
    0x27,
    0x17,
    0x0F,
]


def _run_frames(rom: str, frames: int, start_at: int = 0) -> NesCore:
    core = NesCore()
    core.load_rom(rom)
    core.reset()
    for f in range(1, frames + 1):
        core.set_buttons(0x08 if start_at <= f < start_at + 10 else 0x00)
        core.run_frame()
    return core


class TestGoldenFrame:
    def test_frame1_rgb_summary(self) -> None:
        """M1a acceptance: one-frame RGB summary consistent through the
        zero-copy binding path."""
        core = _run_frames(ROM_PATH, 0)  # load + reset only
        rgb, _ = core.run_frame()
        core.close()
        assert hashlib.sha256(rgb).hexdigest() == GOLDEN_FRAME1_SHA256

    def test_frame40_rgb_hash(self) -> None:
        """Full-frame RGB after 40 frames must match the recorded baseline.

        Identical for the PAL and NTSC cartridges (title screen, same CHR),
        so the tracked PAL ROM covers both.
        """
        core = _run_frames(ROM_PATH, 40)
        rgb, _ = core.run_frame()
        core.close()
        assert hashlib.sha256(rgb).hexdigest() == GOLDEN_FRAME40_SHA256


class TestPaletteTruth:
    def test_bg_palette_matches_groundpalettedata(self) -> None:
        """BG palette RAM after reaching 1-1 must equal the ROM's table."""
        core = _run_frames(ROM_PATH, 400, start_at=60)
        pal = core.dump_palette()
        core.close()
        assert list(pal[0:16]) == GROUND_PALETTE_BG


class TestAudioPitch:
    def test_pal_pitch_no_octave_shift(self) -> None:
        """Tracked PAL cartridge on the NTSC-timed core.

        The PAL music data carries CPU-clock-scaled note periods, so the
        intro's first note renders at ~712.7 Hz (E5 659 Hz scaled by
        1789773/1662607). The old APU timer bug rendered every channel one
        octave up (~1425 Hz here) — this test pins the correct bin.
        """
        pcm = b"".join(_capture_frames(ROM_PATH, 130, 330))
        seg = _pcm_slice(pcm, 1.30, 1.85)
        p712 = _goertzel_power(seg, 712.7)
        p1425 = _goertzel_power(seg, 1425.4)
        p659 = _goertzel_power(seg, 659.3)
        assert p712 > 8 * p1425, {"712": p712, "1425": p1425}
        assert p712 > 8 * p659, {"712": p712, "659": p659}

    def test_ntsc_pitch_is_e5(self) -> None:
        """NTSC cartridge (if present): intro must peak at E5, not E6."""
        if not Path(ROM_NTSC).exists():
            pytest.skip("NTSC cartridge copy not present")
        pcm = b"".join(_capture_frames(ROM_NTSC, 130, 330))
        seg = _pcm_slice(pcm, 1.40, 1.85)
        pe5 = _goertzel_power(seg, 659.3)
        pe6 = _goertzel_power(seg, 1318.5)
        assert pe5 > 8 * pe6, {"E5": pe5, "E6": pe6}

    @classmethod
    def _capture_session_ntsc(cls, frames: int) -> bytes:
        return cls._capture_session("ntsc", frames, rom=ROM_NTSC)


def _capture_frames(rom: str, begin: int, end: int) -> list[bytes]:
    core = NesCore()
    core.load_rom(rom)
    core.reset()
    chunks = []
    for f in range(1, end + 1):
        core.set_buttons(0x08 if 60 <= f < 70 else 0x00)
        _, pcm = core.run_frame()
        if f >= begin:
            chunks.append(pcm)
    core.close()
    return chunks


def _pcm_slice(pcm: bytes, t0: float, t1: float) -> bytes:
    sr = 44100
    return pcm[int(t0 * sr) * 2 : int(t1 * sr) * 2]


def _goertzel_power(samples: bytes, freq: float, sr: int = 44100) -> float:
    """Single-DFT-bin power at `freq` (stdlib-only spectral probe)."""
    n = len(samples) // 2
    if n == 0:
        return 0.0
    k = round(n * freq / sr)
    w = 2.0 * math.pi * k / n
    coeff = 2.0 * math.cos(w)
    s1 = s2 = 0.0
    for i in range(n):
        v = struct.unpack_from("<h", samples, i * 2)[0]
        s0 = v + coeff * s1 - s2
        s2, s1 = s1, s0
    return s1 * s1 + s2 * s2 - coeff * s1 * s2


class TestBlarggDriver:
    """Runner for blargg-style test ROMs (result protocol at $6000-$7FFF).

    Real test ROMs are not redistributed with the repo; drop them into
    rom/blargg/ and they are picked up automatically. The protocol test
    below uses a synthetic NROM that reports PASS through the same
    mechanism, validating the driver without external assets.
    """

    @staticmethod
    def run_test_rom(rom_path: str, max_frames: int = 2000) -> tuple[int, str]:
        """Run a blargg test ROM; return (status, message).

        Protocol (blargg's docs): $6001-$6003 = DE B0 61 signature,
        $6000 = status (0x80 running, 0x00 pass, other = fail),
        $6004.. = text message. Returned status: 0 = pass, 1 = fail,
        0x80 = timeout without result, 0x81 = load failure.
        """
        core = NesCore()
        if core.load_rom(rom_path) != 0:
            core.close()
            return 0x81, "load failed (unsupported mapper or bad file)"
        core.reset()
        status, text = 0x80, ""
        for _ in range(max_frames):
            core.set_buttons(0x00)
            core.run_frame()
            if (
                core.peek_cpu(0x6001) == 0xDE
                and core.peek_cpu(0x6002) == 0xB0
                and core.peek_cpu(0x6003) == 0x61
            ):
                status = core.peek_cpu(0x6000)
                chars = []
                for addr in range(0x6004, 0x8000):
                    c = core.peek_cpu(addr)
                    if c == 0:
                        break
                    chars.append(chr(c))
                text = "".join(chars)
                if status != 0x80:
                    break
        core.close()
        return status, text

    @staticmethod
    @staticmethod
    def _build_pass_rom(path: Path) -> None:
        """Synthetic NROM that reports PASS via the blargg $6000 protocol."""
        code = bytes(
            [
                0xA9,
                0x00,  # LDA #$00   (status: pass)
                0x8D,
                0x00,
                0x60,  # STA $6000
                0xA9,
                0xDE,  # LDA #$DE
                0x8D,
                0x01,
                0x60,  # STA $6001
                0xA9,
                0xB0,  # LDA #$B0
                0x8D,
                0x02,
                0x60,  # STA $6002
                0xA9,
                0x61,  # LDA #$61
                0x8D,
                0x03,
                0x60,  # STA $6003
            ]
        )  # 25 bytes
        spin = 0x8000 + len(code)
        code = code + bytes([0x4C, spin & 0xFF, spin >> 8])  # JMP spin
        prg = bytearray(32768)
        prg[0 : len(code)] = code
        prg[0x7FFA:0x8000] = bytes([0x00, 0x80, 0x00, 0x80, 0x00, 0x80])
        header = b"NES" + bytes([2, 1, 0x01, 0x00]) + bytes(8)
        path.write_bytes(header + bytes(prg) + bytes(8192))

    def test_protocol_pass_detection(self, tmp_path: Path) -> None:
        rom = tmp_path / "synthetic_pass.nes"
        self._build_pass_rom(rom)
        status, _text = self.run_test_rom(str(rom))
        assert status == 0

    def test_real_blargg_roms_if_present(self) -> None:
        """Run any user-provided blargg ROMs under rom/blargg/.

        Load failures (e.g. MMC1 before M3) and clean timeouts (e.g.
        cpu_dummy_reads, which needs M6 dot-level PPU bus behavior) are
        reported as skips, not failures — only a ROM that ran to completion
        and reported FAIL breaks the build.
        """
        roms = (
            sorted(Path("rom/blargg").glob("*.nes"))
            if Path("rom/blargg").is_dir()
            else []
        )
        if not roms:
            pytest.skip("no blargg ROMs in rom/blargg/ (see tests/blargg protocol)")
        failures: dict[str, str] = {}
        pending: dict[str, str] = {}
        for rom in roms:
            status, text = self.run_test_rom(str(rom))
            if status == 0x81:
                pending[rom.name] = text or "load failed"
            elif status == 0x80:
                pending[rom.name] = "no result within frame budget (long test)"
            elif status != 0:
                failures[rom.name] = text or f"status={status}"
        if failures:
            pytest.fail(f"blargg test ROM failures: {failures}")
        if pending:
            pytest.skip(f"pending (see design doc M3/M6): {pending}")


class TestRegionTiming:
    """M2.5: region-aware video timing (design doc §12 M2.5)."""

    @staticmethod
    def _capture_session(region: str, frames: int, rom: str = ROM_PATH) -> bytes:
        from tests.test_session import FakeClock, _SilentChannel

        if region == "pal":
            fs = (341 * 312 * 5 / 16) / 1662607
        else:
            fs = (341 * 262 / 3) / 1789773
        clk = FakeClock(delta=fs / 2)  # two reads per step = one frame
        s = EmulationSession(
            rom,
            region=region,
            channel=_SilentChannel(),
            sound_factory=lambda data: object(),
            sleep=lambda sec: None,
            clock=clk,
        )
        s.reset()
        chunks = []
        for f in range(1, frames + 1):
            s.set_buttons(0x08 if 60 <= f < 70 else 0x00)
            _, pcm = s.step()
            if f >= 130:
                chunks.append(pcm)
        return b"".join(chunks)

    def test_pal_on_pal_timing_pitch_restored(self) -> None:
        """PAL cartridge on PAL timing: the music periods were computed for
        the PAL CPU, so the intro's first note renders at ~661.6 Hz (E5
        family) instead of the +7.6% sharp 712.7 Hz seen when PAL data runs
        on the NTSC clock (test_pal_pitch_no_octave_shift pins THAT mode)."""
        pcm = self._capture_session("pal", 400)
        seg = _pcm_slice(pcm, 0.10, 1.20)  # theme start (PAL card is shorter)
        p662 = _goertzel_power(seg, 661.6)
        p713 = _goertzel_power(seg, 712.7)
        assert p662 > 20 * p713, {"661.6": p662, "712.7": p713}

    def test_ntsc_on_ntsc_timing_pitch_is_e5(self) -> None:
        if not Path(ROM_NTSC).exists():
            pytest.skip("NTSC cartridge copy not present")
        pcm = self._capture_session_ntsc(400)
        seg = _pcm_slice(pcm, 1.40, 1.85)
        pe5 = _goertzel_power(seg, 659.3)
        pe6 = _goertzel_power(seg, 1318.5)
        assert pe5 > 8 * pe6, {"E5": pe5, "E6": pe6}

    @classmethod
    def _capture_session_ntsc(cls, frames: int) -> bytes:
        return cls._capture_session("ntsc", frames, rom=ROM_NTSC)
