"""Tests for the NES pygame shell over the C core."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pygame
import pytest

from window.frontends.menu_bar import Action
from window.frontends.pygame_frontend import NES

ROM_PATH = "rom/super-mario-bros.nes"


@pytest.fixture()
def nes() -> Generator[NES, None, None]:
    n = NES(ROM_PATH, headless=True)
    yield n
    n.close()


class TestNESInit:
    def test_load_rom_succeeds(self, nes: NES) -> None:
        assert nes._core is not None

    def test_headless_no_pygame_display(self, nes: NES) -> None:
        assert nes._screen is None

    def test_reset_succeeds(self, nes: NES) -> None:
        nes.reset()
        nes.reset()

    def test_run_frame_succeeds(self, nes: NES) -> None:
        nes.reset()
        nes._run_frame()
        assert nes._last_rgb
        assert len(nes._last_rgb) == 256 * 240 * 3


class TestKeyMapping:
    def test_handle_key_a(self, nes: NES) -> None:
        nes._handle_key(pygame.K_z, True)
        assert nes._buttons & 0x01
        nes._handle_key(pygame.K_z, False)
        assert not (nes._buttons & 0x01)

    def test_handle_key_unmapped(self, nes: NES) -> None:
        nes._handle_key(ord("q"), True)
        assert nes._buttons == 0


@pytest.fixture()
def windowed_nes(monkeypatch: pytest.MonkeyPatch) -> Generator[NES, None, None]:
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    pygame.init()
    n = NES(ROM_PATH, headless=False)
    yield n
    n.close()


class TestWindowMaximize:
    def test_default_small_window(self, windowed_nes: NES) -> None:
        assert windowed_nes._screen is not None
        assert windowed_nes._screen.get_size() == (1024, 768)
        assert not windowed_nes._maximized

    def test_maximize_is_borderless_fullscreen(self, windowed_nes: NES) -> None:
        pygame.event.post(pygame.event.Event(pygame.WINDOWMAXIMIZED))
        windowed_nes._handle_events()
        assert windowed_nes._maximized
        assert windowed_nes._screen is not None
        assert windowed_nes._screen.get_size() == pygame.display.get_desktop_sizes()[0]
        assert windowed_nes._screen.get_flags() & pygame.NOFRAME

    def test_esc_restores_small_window(self, windowed_nes: NES) -> None:
        pygame.event.post(pygame.event.Event(pygame.WINDOWMAXIMIZED))
        windowed_nes._handle_events()
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE))
        windowed_nes._handle_events()
        assert windowed_nes._screen is not None
        assert windowed_nes._screen.get_size() == (1024, 768)
        assert windowed_nes._screen.get_flags() & pygame.RESIZABLE
        assert not windowed_nes._maximized

    def test_present_works_in_maximized_mode(self, windowed_nes: NES) -> None:
        windowed_nes.reset()
        windowed_nes._run_frame()
        pygame.event.post(pygame.event.Event(pygame.WINDOWMAXIMIZED))
        windowed_nes._handle_events()
        windowed_nes._present()  # scaled blit must not raise

    def test_focus_lost_clears_buttons(self, windowed_nes: NES) -> None:
        windowed_nes._handle_key(pygame.K_RIGHT, True)
        assert windowed_nes._buttons == 0x80
        pygame.event.post(pygame.event.Event(pygame.WINDOWFOCUSLOST))
        windowed_nes._handle_events()
        assert windowed_nes._buttons == 0


class _FakeChannel:
    """Records play/queue calls; get_busy scriptable."""

    def __init__(self) -> None:
        self.played: list[object] = []
        self.queued: list[object] = []

    def play(self, snd: object) -> None:
        self.played.append(snd)

    def queue(self, snd: object) -> None:
        self.queued.append(snd)

    def get_busy(self) -> bool:
        return bool(self.played or self.queued)


class _FakeSound:
    def __init__(self, data: bytes) -> None:
        self.data = data


def _frame_pcm() -> bytes:
    # One core frame: ~733.75 -> 734 samples, mono s16 (1468 bytes)
    return b"\x00\x01" * 734


class TestAudioPump:
    FRAME = 734  # mono samples per core frame

    def _pump(self, channels: int = 1) -> tuple[object, _FakeChannel, list[bytes]]:
        from window.session import AudioPump as _AudioPump

        ch = _FakeChannel()
        data: list[bytes] = []

        def factory(d: bytes) -> _FakeSound:
            data.append(d)
            return _FakeSound(d)

        return _AudioPump(ch, channels=channels, sound_factory=factory), ch, data

    def test_primes_before_first_play(self) -> None:
        pump, ch, _ = self._pump()
        for i in range(pump.PRIME // self.FRAME):  # one frame short of PRIME
            pump.push(_frame_pcm(), now=i * self.FRAME / 44100)
        assert ch.played == [] and ch.queued == []

    def test_primes_then_plays_not_queues(self) -> None:
        pump, ch, _ = self._pump()
        t = 0.0
        for i in range((pump.PRIME + self.FRAME - 1) // self.FRAME):
            pump.push(_frame_pcm(), now=t)
            t += self.FRAME / 44100
        assert len(ch.played) == 1 and ch.queued == []

    def test_steady_state_nothing_lost(self) -> None:
        pump, ch, data = self._pump()
        t = 0.0
        n = 600  # ~10 s at 60.0988 fps
        for _ in range(n):
            pump.push(_frame_pcm(), now=t)
            t += self.FRAME / 44100
        assert len(ch.played) == 1
        assert 50 <= len(ch.queued) <= 75  # ~one queue per 160 ms chunk
        enqueued = sum(len(d) for d in data) // 2  # mono samples sent
        pushed = n * self.FRAME
        backlog, pending = pump.stats(t)
        assert enqueued + pending == pushed  # no samples dropped
        assert 0 <= backlog <= 2 * pump.CHUNK + self.FRAME

    def test_fast_loop_slot_protocol(self) -> None:
        pump, ch, _ = self._pump()
        for _ in range(10):
            pump.push(_frame_pcm(), now=0.0)  # all pushes at the same instant
        # one chunk playing + at most one queued; the rest waits in pending
        assert len(ch.played) == 1
        assert len(ch.queued) <= 1
        assert pump.stats(0.0)[1] > 0
        assert pump.stats(0.0)[1] <= pump.MAX_PENDING // 2 + self.FRAME

    def test_stereo_conversion_interleaves(self) -> None:
        pump, ch, data = self._pump(channels=2)
        t = 0.0
        for _ in range((pump.PRIME + self.FRAME - 1) // self.FRAME + 2):
            pump.push(_frame_pcm(), now=t)
            t += self.FRAME / 44100
        assert len(data) == 1
        assert len(data[0]) == pump.CHUNK * 4  # duplicated to stereo
        mono = (_frame_pcm() * 10)[: pump.CHUNK * 2]
        expect = bytearray()
        for k in range(0, len(mono), 2):
            expect += mono[k : k + 2] * 2
        assert data[0] == bytes(expect)

    def test_starvation_resyncs_and_reprimes(self) -> None:
        pump, ch, _ = self._pump()
        t = 0.0
        for _ in range(20):  # steady flow
            pump.push(_frame_pcm(), now=t)
            t += self.FRAME / 44100
        plays_before = len(ch.played)
        queues_before = len(ch.queued)
        t += 1.0  # long stall: mixer starved far past everything queued
        pump.push(_frame_pcm(), now=t)  # triggers resync
        # push until the pump re-primes and plays again; note pending may
        # hold leftovers from before the stall, so PRIME completes early
        for _ in range(20):
            t += self.FRAME / 44100
            pump.push(_frame_pcm(), now=t)
            if len(ch.played) > plays_before:
                break
        assert len(ch.played) == plays_before + 1  # re-prime uses play()
        assert len(ch.queued) == queues_before  # and never queue()


class TestTextInputDisabled:
    def test_init_disables_text_input(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """中文 IME 会劫持字母键/方向键——前端初始化必须关闭文本输入。"""
        import pygame

        calls = []
        monkeypatch.setattr(pygame.key, "stop_text_input", lambda: calls.append(1))
        n = NES(ROM_PATH)  # windowed (dummy driver)
        n.close()
        assert calls, "NES init must call pygame.key.stop_text_input()"

    def test_maximize_keeps_text_input_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import pygame

        calls = []
        monkeypatch.setattr(pygame.key, "stop_text_input", lambda: calls.append(1))
        n = NES(ROM_PATH)
        before = len(calls)
        pygame.event.post(pygame.event.Event(pygame.WINDOWMAXIMIZED))
        n._handle_events()  # 重建显示后必须再次关闭
        n.close()
        assert len(calls) > before


class TestRomLoader:
    """O 键文件对话框与拖拽载入卡带（无卡带分发模式）。"""

    @staticmethod
    def _synthetic_rom(tmp_path: Path) -> Path:
        from tests.test_regression import TestBlarggDriver

        rom = tmp_path / "syn.nes"
        TestBlarggDriver._build_pass_rom(rom)
        return rom

    def test_no_rom_opens_loader_mode(self) -> None:
        n = NES(None)  # 无卡带启动
        assert n._cart_loaded is False
        n._present_no_cart()  # 引导屏可渲染
        n.close()

    def test_o_key_opens_dialog_and_loads(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        n = NES(None)
        rom = self._synthetic_rom(tmp_path)
        monkeypatch.setattr(n, "_open_rom_dialog", lambda: str(rom))
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_o))
        n._handle_events()
        n.close()
        assert n._cart_loaded is True
        assert n._osd_text is not None and "syn.nes" in n._osd_text

    def test_dropfile_loads(self, tmp_path: Path) -> None:
        n = NES(None)
        rom = self._synthetic_rom(tmp_path)
        pygame.event.post(pygame.event.Event(pygame.DROPFILE, file=str(rom)))
        n._handle_events()
        n.close()
        assert n._cart_loaded is True

    def test_dropfile_bad_file_reports(self, tmp_path: Path) -> None:
        n = NES(None)
        bad = tmp_path / "bad.nes"
        bad.write_bytes(b"junk")

        def _noop_box(title: str, text: str) -> None:
            pass

        n._message_box = _noop_box  # 无头环境不弹真框
        pygame.event.post(pygame.event.Event(pygame.DROPFILE, file=str(bad)))
        n._handle_events()
        n.close()
        assert n._cart_loaded is False
        assert n._osd_text is not None and "载入失败" in n._osd_text


class TestMenuActions:
    """菜单动作分发：与快捷键共用同一路径。"""

    @staticmethod
    def _dispatch(n: NES, action: Action, **extra: object) -> None:
        n._dispatch_menu(int(action), extra)

    def test_pause_toggles_and_osd(self) -> None:
        n = NES(ROM_PATH)
        assert n._paused is False
        self._dispatch(n, Action.PAUSE)
        assert n._paused is True
        assert n._osd_text is not None and "暂停" in n._osd_text
        self._dispatch(n, Action.PAUSE)
        assert n._paused is False
        n.close()

    def test_reset_action(self) -> None:
        n = NES(ROM_PATH)
        self._dispatch(n, Action.RESET)
        assert n._osd_text is not None and "复位" in n._osd_text
        n.close()

    def test_mute_toggles_volume(self) -> None:
        n = NES(ROM_PATH)
        self._dispatch(n, Action.MUTE)
        assert n._muted is True
        self._dispatch(n, Action.MUTE)
        assert n._muted is False
        n.close()

    def test_region_switch_resets_and_rebuilds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        n = NES(ROM_PATH)
        rebuilds: list[int] = []
        monkeypatch.setattr(n._menu, "rebuild", lambda *a, **k: rebuilds.append(1))
        self._dispatch(n, Action.TIMING_PAL, region="pal")
        assert n._session.region == "pal"
        assert rebuilds
        n.close()

    def test_lang_switch_rebuilds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        n = NES(ROM_PATH)
        rebuilds: list[int] = []
        monkeypatch.setattr(n._menu, "rebuild", lambda *a, **k: rebuilds.append(1))
        self._dispatch(n, Action.LANG_EN, lang="en")
        assert n._lang == "en"
        assert rebuilds
        self._dispatch(n, Action.LANG_ZH, lang="zh")
        assert n._lang == "zh"
        n.close()

    def test_scale_switch(self) -> None:
        n = NES(ROM_PATH)
        self._dispatch(n, Action.SCALE_2)
        assert n._scale == 2
        assert n._screen is not None
        assert n._screen.get_size() == (512, 480)
        n.close()

    def test_help_dialogs_route_through_message_box(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        n = NES(ROM_PATH)
        boxes: list[tuple[str, str]] = []
        monkeypatch.setattr(n, "_message_box", lambda t, x: boxes.append((t, x)))
        self._dispatch(n, Action.KEYS_HELP)
        self._dispatch(n, Action.ABOUT)
        assert len(boxes) == 2
        assert boxes[0][0] == "按键说明"
        assert "FamilyBox" in boxes[1][0]
        n.close()
