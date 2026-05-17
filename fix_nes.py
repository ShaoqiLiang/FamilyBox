"""Fix nes.py: final fix - warmup PPU to VBlank before running CPU."""
from pathlib import Path

nes_path = Path("familybox/nes.py")
content = nes_path.read_text(encoding="utf-8")

# ------------------------------------------------------------
# 1. Fix _warmup_ppu: stop at first VBlank, don't consume it
# ------------------------------------------------------------
old_warmup = """    def _warmup_ppu(self) -> None:
        \"\"\"Advance PPU for 2 frames so CPU sees VBlank on boot.\"\"\"
        for _ in range(524):  # 2 frames = 524 scanlines
            self._ppu.tick_scanlines(1)
        # After warmup, PPU is at scanline 261, VBlank was just cleared.
        # Next tick_scanlines in _run_frame will push to scanline 0 and
        # eventually to 241 where CPU will see VBlank."""

new_warmup = """    def _warmup_ppu(self) -> None:
        \"\"\"Advance PPU to first VBlank so CPU sees it on boot.\"\"\"
        for _ in range(262):
            self._ppu.tick_scanlines(1)
            if self._ppu._status.vblank:
                break"""

content = content.replace(old_warmup, new_warmup)

# ------------------------------------------------------------
# 2. Update run(): warmup PPU, then run frames normally
# ------------------------------------------------------------
old_run = """        self.reset()

        # Warmup: run 2 frames so PPU and CPU synchronize
        for _ in range(2):
            self._run_frame()

        while self._running:"""

new_run = """        self.reset()
        self._warmup_ppu()

        while self._running:"""

content = content.replace(old_run, new_run)

nes_path.write_text(content, encoding="utf-8")
print("Done - final fix applied")