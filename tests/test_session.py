"""L4 session tests: audio drop-rate acceptance (M2) + region plumbing (M2.5)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from window.session import EmulationSession

ROM = "rom/super-mario-bros.nes"


class FakeClock:
    """Synthetic clock advancing a fixed delta per call."""

    def __init__(self, start: float = 0.0, delta: float = 0.0) -> None:
        self.t = start
        self.delta = delta

    def __call__(self) -> float:
        t = self.t
        self.t += self.delta
        return t

    def jump(self, seconds: float) -> None:
        self.t += seconds


class _SilentChannel:
    """Mixer-channel stand-in: records sounds, never plays them."""

    def __init__(self) -> None:
        self.queued = 0

    def play(self, snd: object) -> None:
        self.queued += 1

    def queue(self, snd: object) -> None:
        self.queued += 1

    def get_queue(self) -> None:
        return None


def _ntsc_frame_seconds() -> float:
    return (341 * 262 / 3) / 1789773


def _make_session(
    region: str = "ntsc",
    clock: "FakeClock | None" = None,
    sleep: "Callable[[float], None] | None" = None,
) -> EmulationSession:
    kwargs: dict[str, object] = {}
    if clock is not None:
        kwargs["clock"] = clock
    if sleep is not None:
        kwargs["sleep"] = sleep
    return EmulationSession(
        ROM,
        region=region,
        channel=_SilentChannel(),
        sound_factory=lambda data: object(),
        **kwargs,
    )


class TestSessionBasics:
    def test_unknown_region_rejected(self) -> None:
        with pytest.raises(ValueError, match="unknown region"):
            EmulationSession(ROM, region="secam")

    def test_missing_rom(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            EmulationSession(tmp_path / "nope.nes", sleep=lambda s: None)

    def test_step_returns_frame_and_paces(self) -> None:
        fs = _ntsc_frame_seconds()
        clk = FakeClock(delta=fs / 2)  # two clock reads per step = one frame
        slept: list[float] = []
        s = _make_session(clock=clk, sleep=lambda sec: slept.append(sec))
        s.reset()
        rgb, pcm = s.step()
        assert len(rgb) == 256 * 240 * 3
        assert len(pcm) % 2 == 0
        assert s._frame_index == 1

    def test_region_propagates_frame_cadence(self) -> None:
        """PAL timing: ~896 samples/frame (33209 cycles @ 44100 Hz)."""
        clk = FakeClock(delta=(341 * 312 * 5 / 16) / 1662607 / 2)
        s = _make_session(region="pal", clock=clk, sleep=lambda sec: None)
        s.reset()
        totals = [len(s.step()[1]) // 2 for _ in range(30)]
        avg = sum(totals) / len(totals)
        assert 850 <= avg <= 940, avg  # PAL ~880 vs NTSC ~734


class TestDropRate:
    def test_zero_drops_on_realtime_cadence(self) -> None:
        """M2 acceptance: 20 s of emulated audio at exact native cadence
        must drop nothing and never underrun (drop-rate bar is < 0.1%)."""
        fs = _ntsc_frame_seconds()
        clk = FakeClock(delta=fs / 2)
        s = _make_session(clock=clk, sleep=lambda sec: None)
        s.reset()
        for _ in range(1200):  # ~20 s of audio
            s.step()
        assert s.drop_rate() == 0.0
        assert s.underruns() == 0
        assert s.pump is not None and s.pump.total_pushed > 800_000

    def test_stall_causes_bounded_underrun_then_recovers(self) -> None:
        fs = _ntsc_frame_seconds()
        clk = FakeClock(delta=fs / 2)
        s = _make_session(clock=clk, sleep=lambda sec: None)
        s.reset()
        for _ in range(120):
            s.step()
        clk.jump(2.0)  # the frontend froze for 2 s: mixer starves
        for _ in range(240):
            s.step()
        assert s.underruns() >= 1  # the stall was detected and accounted
        assert s.drop_rate() < 0.01  # recovery keeps losses bounded
