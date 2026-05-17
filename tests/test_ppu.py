"""Tests for the PPU module.

Covers:
- PPUCTRL / PPUMASK / PPUSTATUS data structures
- SpriteData dataclass and properties
- PPU register reads and writes (double-write latch, VBlank clear, etc.)
- PPU timing (scanline / cycle state machine, VBlank enter/exit)
- NMI triggering
- PPUDATA delayed read
- Background rendering (known tile data -> expected pixel)
- Sprite rendering (including flipping, priority, sprite 0 hit)
"""

from typing import cast

from familybox.ppu.ppu import PPU, PPUMASK, PPUCTRL, PPUSTATUS, SpriteData
from familybox.ppu.renderer import Renderer
from familybox.types import NES_PALETTE


def _renderer(ppu: PPU) -> Renderer:
    """Get the pure-Python renderer from a PPU (tests force it via conftest)."""
    return cast(Renderer, ppu._renderer)


# ---------------------------------------------------------------------------
# Mock PPU bus
# ---------------------------------------------------------------------------


class MockPPUBus:
    """A dict-backed mock PPU bus for testing."""

    def __init__(self) -> None:
        self._memory: dict[int, int] = {}

    def read(self, addr: int) -> int:
        return self._memory.get(addr & 0x3FFF, 0)

    def write(self, addr: int, value: int) -> None:
        self._memory[addr & 0x3FFF] = value & 0xFF

    # Unused by PPU but present in the PPUBusInterface Protocol.
    def read_register(self, addr: int) -> int:  # pragma: no cover
        return 0

    def write_register(self, addr: int, value: int) -> None:  # pragma: no cover
        pass


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _nes_rgb(palette_index: int) -> int:
    """Convert NES palette index to the same RGB integer the renderer uses."""
    r, g, b = NES_PALETTE[palette_index & 0x3F]
    return (r << 16) | (g << 8) | b


def _advance_to(ppu: PPU, scanline: int, cycle: int) -> None:
    """Tick the PPU until it reaches (*scanline*, *cycle*)."""
    while not (ppu._scanline == scanline and ppu._cycle == cycle):
        ppu.tick()


# ---------------------------------------------------------------------------
# PPUCTRL tests
# ---------------------------------------------------------------------------


class TestPPUCTRL:
    def test_default_values(self) -> None:
        ctrl = PPUCTRL()
        assert ctrl.nametable_addr == 0x2000
        assert ctrl.vram_increment == 1
        assert ctrl.sprite_pattern_addr == 0
        assert ctrl.bg_pattern_addr == 0
        assert ctrl.sprite_size == 8
        assert ctrl.nmi_enabled is False

    def test_decode_nametable(self) -> None:
        for bits, expected in [(0, 0x2000), (1, 0x2400), (2, 0x2800), (3, 0x2C00)]:
            ctrl = PPU._decode_ctrl(bits)
            assert ctrl.nametable_addr == expected

    def test_decode_vram_increment(self) -> None:
        assert PPU._decode_ctrl(0).vram_increment == 1
        assert PPU._decode_ctrl(0x04).vram_increment == 32

    def test_decode_pattern_tables(self) -> None:
        ctrl = PPU._decode_ctrl(0x08)
        assert ctrl.sprite_pattern_addr == 0x1000
        ctrl = PPU._decode_ctrl(0x10)
        assert ctrl.bg_pattern_addr == 0x1000

    def test_decode_sprite_size(self) -> None:
        assert PPU._decode_ctrl(0).sprite_size == 8
        assert PPU._decode_ctrl(0x20).sprite_size == 16

    def test_decode_nmi_enabled(self) -> None:
        assert PPU._decode_ctrl(0).nmi_enabled is False
        assert PPU._decode_ctrl(0x80).nmi_enabled is True


# ---------------------------------------------------------------------------
# PPUMASK tests
# ---------------------------------------------------------------------------


class TestPPUMASK:
    def test_default_values(self) -> None:
        mask = PPUMASK()
        assert mask.greyscale is False
        assert mask.show_left_bg is False
        assert mask.show_left_sprites is False
        assert mask.show_bg is False
        assert mask.show_sprites is False
        assert mask.emphasize_red is False
        assert mask.emphasize_green is False
        assert mask.emphasize_blue is False

    def test_decode_show_bg(self) -> None:
        mask = PPU._decode_mask(0x08)
        assert mask.show_bg is True

    def test_decode_show_sprites(self) -> None:
        mask = PPU._decode_mask(0x10)
        assert mask.show_sprites is True

    def test_decode_greyscale(self) -> None:
        mask = PPU._decode_mask(0x01)
        assert mask.greyscale is True

    def test_decode_emphasize(self) -> None:
        mask = PPU._decode_mask(0x20)
        assert mask.emphasize_red is True
        mask = PPU._decode_mask(0x40)
        assert mask.emphasize_green is True
        mask = PPU._decode_mask(0x80)
        assert mask.emphasize_blue is True


# ---------------------------------------------------------------------------
# PPUSTATUS tests
# ---------------------------------------------------------------------------


class TestPPUSTATUS:
    def test_default_values(self) -> None:
        status = PPUSTATUS()
        assert status.sprite_overflow is False
        assert status.sprite_zero_hit is False
        assert status.vblank is False


# ---------------------------------------------------------------------------
# SpriteData tests
# ---------------------------------------------------------------------------


class TestSpriteData:
    def test_default(self) -> None:
        s = SpriteData()
        assert s.y == 0
        assert s.tile == 0
        assert s.attr == 0
        assert s.x == 0

    def test_palette(self) -> None:
        assert SpriteData(attr=0x00).palette == 0
        assert SpriteData(attr=0x01).palette == 1
        assert SpriteData(attr=0x03).palette == 3

    def test_flip_h(self) -> None:
        assert SpriteData(attr=0x00).flip_h is False
        assert SpriteData(attr=0x40).flip_h is True

    def test_flip_v(self) -> None:
        assert SpriteData(attr=0x00).flip_v is False
        assert SpriteData(attr=0x80).flip_v is True

    def test_priority(self) -> None:
        assert SpriteData(attr=0x00).priority == 0  # in front
        assert SpriteData(attr=0x20).priority == 1  # behind bg


# ---------------------------------------------------------------------------
# PPU register read/write tests
# ---------------------------------------------------------------------------


class TestPPURegisters:
    def test_ppustatus_returns_vblank_and_clears(self) -> None:
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu._status.vblank = True
        ppu._write_toggle = True

        value = ppu.read_register(0x2002)
        assert value & 0x80  # bit 7 set
        assert ppu._status.vblank is False
        assert ppu._write_toggle is False

    def test_ppustatus_no_vblank(self) -> None:
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu._status.vblank = False
        value = ppu.read_register(0x2002)
        assert value == 0

    def test_oamdata_read(self) -> None:
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu._oam[5] = 0xAB
        ppu._oam_addr = 5
        assert ppu.read_register(0x2004) == 0xAB

    def test_ppudata_read_below_3f00(self) -> None:
        """Reads below $3F00 should be delayed by one read."""
        bus = MockPPUBus()
        ppu = PPU(bus)
        bus.write(0x1234, 0x42)
        ppu._vram_addr = 0x1234

        # First read returns buffer (initially 0), buffer becomes 0x42
        assert ppu.read_register(0x2007) == 0
        assert ppu._data_buffer == 0x42

        # Second read returns 0x42
        bus.write(0x1235, 0x99)
        ppu._vram_addr = 0x1235
        assert ppu.read_register(0x2007) == 0x42

    def test_ppudata_read_palette_immediate(self) -> None:
        """Reads from palette range ($3F00-$3FFF) should return immediately."""
        bus = MockPPUBus()
        ppu = PPU(bus)
        bus.write(0x3F00, 0x11)
        ppu._vram_addr = 0x3F00
        assert ppu.read_register(0x2007) == 0x11

    def test_write_ppuctrl(self) -> None:
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu.write_register(0x2000, 0x80)
        assert ppu._ctrl.nmi_enabled is True

    def test_write_ppumask(self) -> None:
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu.write_register(0x2001, 0x18)
        assert ppu._ctrl.bg_pattern_addr == 0  # not yet
        mask = ppu._mask
        assert mask.show_bg is True
        assert mask.show_sprites is True

    def test_write_oamaddr(self) -> None:
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu.write_register(0x2003, 0x10)
        assert ppu._oam_addr == 0x10

    def test_write_oamdata(self) -> None:
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu._oam_addr = 0
        ppu.write_register(0x2004, 0xFF)
        assert ppu._oam[0] == 0xFF
        assert ppu._oam_addr == 1

    def test_write_ppuscroll_first(self) -> None:
        """First PPUSCROLL write sets coarse X and fine X."""
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu.write_register(0x2005, 0xFA)  # fine_x=2, coarse_x=31
        assert ppu._fine_x == 2
        assert (ppu._temp_addr & 0x001F) == 31
        assert ppu._write_toggle is True

    def test_write_ppuscroll_second(self) -> None:
        """Second PPUSCROLL write sets coarse Y and fine Y."""
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu.write_register(0x2005, 0xFA)  # first write
        ppu.write_register(0x2005, 0xFB)  # second write: coarse_y=31, fine_y=3
        assert ppu._write_toggle is False
        coarse_y = (ppu._temp_addr >> 5) & 0x1F
        fine_y = (ppu._temp_addr >> 12) & 0x07
        assert coarse_y == 31
        assert fine_y == 3

    def test_write_ppuaddr_first(self) -> None:
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu.write_register(0x2006, 0x3F)
        assert (ppu._temp_addr >> 8) == 0x3F
        assert ppu._write_toggle is True

    def test_write_ppuaddr_second(self) -> None:
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu.write_register(0x2006, 0x3F)
        ppu.write_register(0x2006, 0x00)
        assert ppu._vram_addr == 0x3F00
        assert ppu._write_toggle is False

    def test_write_ppudata(self) -> None:
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu._vram_addr = 0x2000
        ppu.write_register(0x2007, 0x42)
        assert bus.read(0x2000) == 0x42
        assert ppu._vram_addr == 0x2001  # increment by 1

    def test_write_ppudata_increment_32(self) -> None:
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu._ctrl.vram_increment = 32
        ppu._vram_addr = 0x2000
        ppu.write_register(0x2007, 0x42)
        assert ppu._vram_addr == 0x2020

    def test_read_register_ignored_addr(self) -> None:
        """Reads from $2000, $2001, $2003, $2005, $2006 should return 0."""
        bus = MockPPUBus()
        ppu = PPU(bus)
        for addr in (0x2000, 0x2001, 0x2003, 0x2005, 0x2006):
            assert ppu.read_register(addr) == 0


# ---------------------------------------------------------------------------
# PPU timing tests
# ---------------------------------------------------------------------------


class TestPPUTiming:
    def test_initial_state(self) -> None:
        bus = MockPPUBus()
        ppu = PPU(bus)
        assert ppu._scanline == 261
        assert ppu._cycle == 0
        assert ppu._frame == 0

    def test_cycle_advances(self) -> None:
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu.tick()
        assert ppu._cycle == 1

    def test_scanline_wraps(self) -> None:
        """After 341 cycles the scanline should advance."""
        bus = MockPPUBus()
        ppu = PPU(bus)
        # Pre-render scanline 261, cycle 0 -> advance through 341 cycles
        for _ in range(341):
            ppu.tick()
        assert ppu._scanline == 0
        assert ppu._cycle == 0

    def test_frame_wraps(self) -> None:
        """After a full frame (262 scanlines * 341 cycles) the frame counter increments."""
        bus = MockPPUBus()
        ppu = PPU(bus)
        total = 262 * 341
        for _ in range(total):
            ppu.tick()
        assert ppu._frame == 1
        assert ppu._scanline == 261  # back to pre-render

    def test_vblank_set_at_scanline_241_cycle_1(self) -> None:
        bus = MockPPUBus()
        ppu = PPU(bus)
        _advance_to(ppu, 241, 1)
        assert ppu._status.vblank is True

    def test_vblank_cleared_at_scanline_261_cycle_1(self) -> None:
        bus = MockPPUBus()
        ppu = PPU(bus)
        # Set vblank first
        _advance_to(ppu, 241, 1)
        assert ppu._status.vblank is True
        # Advance to pre-render clear
        _advance_to(ppu, 261, 1)
        assert ppu._status.vblank is False

    def test_sprite_zero_hit_cleared_at_scanline_241(self) -> None:
        """Sprite zero hit is cleared at VBlank entry (scanline 241)."""
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu._status.sprite_zero_hit = True
        _advance_to(ppu, 241, 1)
        assert ppu._status.sprite_zero_hit is False

    def test_sprite_overflow_cleared_at_scanline_261(self) -> None:
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu._status.sprite_overflow = True
        _advance_to(ppu, 261, 1)
        assert ppu._status.sprite_overflow is False

    def test_scanline_cycles_0_to_261(self) -> None:
        """Verify the scanline range is 0-261 (262 total)."""
        bus = MockPPUBus()
        ppu = PPU(bus)
        seen: set[int] = set()
        # One full frame
        for _ in range(262 * 341 + 1):
            seen.add(ppu._scanline)
            ppu.tick()
        assert min(seen) == 0
        assert max(seen) == 261


# ---------------------------------------------------------------------------
# NMI tests
# ---------------------------------------------------------------------------


class TestNMI:
    def test_nmi_triggered_when_enabled(self) -> None:
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu.write_register(0x2000, 0x80)  # nmi_enabled = True
        _advance_to(ppu, 241, 1)
        # tick() should have returned True for the NMI cycle
        # We advanced past it, so check the state
        assert ppu._status.vblank is True
        assert ppu._nmi_occurred is True

    def test_nmi_not_triggered_when_disabled(self) -> None:
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu.write_register(0x2000, 0x00)  # nmi_enabled = False
        # Walk to scanline 241, cycle 1 and collect NMI return values
        nmi_count = 0
        while not (ppu._scanline == 241 and ppu._cycle == 2):
            if ppu.tick():
                nmi_count += 1
        assert nmi_count == 0
        assert ppu._status.vblank is True

    def test_nmi_triggered_on_tick(self) -> None:
        """Verify that tick() returns True on the exact VBlank cycle when NMI is enabled."""
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu.write_register(0x2000, 0x80)
        # Advance to just before scanline 241, cycle 1
        _advance_to(ppu, 241, 0)
        nmi = ppu.tick()  # This should be the cycle 1 transition
        assert nmi is True

    def test_reading_ppustatus_does_not_clear_nmi_occurred(self) -> None:
        """Reading PPUSTATUS clears vblank but not nmi_occurred."""
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu._status.vblank = True
        ppu._nmi_occurred = True
        ppu.read_register(0x2002)
        assert ppu._status.vblank is False
        assert ppu._nmi_occurred is True


# ---------------------------------------------------------------------------
# OAM tests
# ---------------------------------------------------------------------------


class TestOAM:
    def test_get_oam_sprite(self) -> None:
        bus = MockPPUBus()
        ppu = PPU(bus)
        # Write sprite 0: y=10, tile=5, attr=0x60, x=20
        ppu._oam[0] = 10
        ppu._oam[1] = 5
        ppu._oam[2] = 0x60
        ppu._oam[3] = 20
        s = ppu.get_oam_sprite(0)
        assert s.y == 10
        assert s.tile == 5
        assert s.attr == 0x60
        assert s.x == 20
        assert s.flip_h is True
        assert s.flip_v is False
        assert s.palette == 0

    def test_get_oam_sprite_index(self) -> None:
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu._oam[8] = 100  # sprite 2, byte 0
        s = ppu.get_oam_sprite(2)
        assert s.y == 100


# ---------------------------------------------------------------------------
# Renderer tests
# ---------------------------------------------------------------------------


class TestRenderer:
    def test_framebuffer_size(self) -> None:
        bus = MockPPUBus()
        ppu = PPU(bus)
        fb = _renderer(ppu).get_framebuffer()
        assert len(fb) == 256 * 240

    def test_framebuffer_default_black(self) -> None:
        bus = MockPPUBus()
        ppu = PPU(bus)
        fb = _renderer(ppu).get_framebuffer()
        assert all(pixel == 0 for pixel in fb)

    def test_nes_color(self) -> None:
        """_nes_color should produce the correct RGB integer."""
        r, g, b = NES_PALETTE[0]
        assert Renderer._nes_color(0) == (r << 16) | (g << 8) | b

    def test_bg_pixel_transparent_when_bg_disabled(self) -> None:
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu._mask.show_bg = False
        assert _renderer(ppu)._get_bg_pixel(0, 0) == 0

    def test_bg_pixel_reads_tile(self) -> None:
        """Verify a known tile produces the expected colour."""
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu._mask.show_bg = True
        ppu._mask.show_left_bg = True
        ppu._ctrl.bg_pattern_addr = 0
        ppu._vram_addr = 0
        ppu._fine_x = 0

        # Tile 0 at nametable $2000, coarse_x=0, coarse_y=0
        bus.write(0x2000, 0x01)  # tile index 1

        # Pattern table tile 1, row 0: lo=0xFF, hi=0x00 -> all foreground colour 1
        bus.write(0x0010, 0xFF)  # tile 1 * 16 + 0
        bus.write(0x0018, 0x00)  # tile 1 * 16 + 0 + 8

        # Attribute table: palette 0 at $23C0
        bus.write(0x23C0, 0x00)

        # Palette: entry 1 = some known colour
        bus.write(0x3F01, 0x05)  # NES palette index 5

        color = _renderer(ppu)._get_bg_pixel(0, 0)
        assert color == _nes_rgb(5)

    def test_bg_pixel_zero_is_transparent(self) -> None:
        """Colour index 0 from the pattern should map to universal background."""
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu._mask.show_bg = True
        ppu._mask.show_left_bg = True
        ppu._ctrl.bg_pattern_addr = 0
        ppu._vram_addr = 0
        ppu._fine_x = 0

        # Tile 0 with all-zero pattern -> colour index 0
        bus.write(0x2000, 0x00)
        bus.write(0x0000, 0x00)
        bus.write(0x0008, 0x00)
        bus.write(0x23C0, 0x00)

        # Universal background colour
        bus.write(0x3F00, 0x0A)

        color = _renderer(ppu)._get_bg_pixel(0, 0)
        assert color == _nes_rgb(0x0A)

    def test_sprite_pixel_transparent_when_sprites_disabled(self) -> None:
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu._mask.show_sprites = False
        color, prio = _renderer(ppu)._get_sprite_pixel(0, 0)
        assert color == 0

    def test_sprite_pixel_reads_oam(self) -> None:
        """Set up a sprite at (10, 20) and verify the pixel at that location."""
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu._mask.show_sprites = True
        ppu._ctrl.sprite_pattern_addr = 0
        ppu._ctrl.sprite_size = 8

        # Sprite 0: y=20, tile=2, attr=0x00, x=10
        # Note: sprite Y in OAM is the Y position minus 1 (sprite.y + 1 == screen y)
        ppu._oam[0] = 19  # screen y = 20 (19 + 1)
        ppu._oam[1] = 2  # tile index
        ppu._oam[2] = 0x00  # no flip, priority 0, palette 0
        ppu._oam[3] = 10  # x position

        # Pattern for tile 2, row 0: lo=0xFF, hi=0x00 -> colour index 1
        bus.write(0x0020, 0xFF)  # tile 2 * 16 + 0
        bus.write(0x0028, 0x00)  # tile 2 * 16 + 0 + 8

        # Sprite palette 0, entry 1
        bus.write(0x3F11, 0x12)  # NES palette index 18

        color, prio = _renderer(ppu)._get_sprite_pixel(10, 20)
        assert color == _nes_rgb(0x12)
        assert prio == 0

    def test_sprite_flip_h(self) -> None:
        """Horizontal flip should mirror the pixel within the tile."""
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu._mask.show_sprites = True
        ppu._ctrl.sprite_pattern_addr = 0
        ppu._ctrl.sprite_size = 8

        # Sprite 0 at (10, 20), flipped horizontally
        ppu._oam[0] = 19
        ppu._oam[1] = 2
        ppu._oam[2] = 0x40  # flip_h
        ppu._oam[3] = 10

        # Pattern: lo=0x01 (only bit 0 set -> pixel 7 in normal, pixel 0 when flipped)
        bus.write(0x0020, 0x01)
        bus.write(0x0028, 0x00)

        bus.write(0x3F11, 0x12)

        # With flip_h at rel_x=0: rel_x becomes 7, bit=0, lo bit 0 = 1 -> non-transparent
        color, _ = _renderer(ppu)._get_sprite_pixel(10, 20)
        assert color == _nes_rgb(0x12)

    def test_sprite_flip_v(self) -> None:
        """Vertical flip should mirror rows."""
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu._mask.show_sprites = True
        ppu._ctrl.sprite_pattern_addr = 0
        ppu._ctrl.sprite_size = 8

        # Sprite at (10, 20), flipped vertically
        ppu._oam[0] = 19
        ppu._oam[1] = 2
        ppu._oam[2] = 0x80  # flip_v
        ppu._oam[3] = 10

        # Row 7 pattern (flip_v maps screen row 0 -> tile row 7)
        bus.write(0x0027, 0xFF)  # tile 2 * 16 + 7
        bus.write(0x002F, 0x00)  # tile 2 * 16 + 7 + 8

        bus.write(0x3F11, 0x12)

        color, _ = _renderer(ppu)._get_sprite_pixel(10, 20)
        assert color == _nes_rgb(0x12)

    def test_sprite_priority_behind_bg(self) -> None:
        """Sprite with priority=1 should appear behind background."""
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu._mask.show_bg = True
        ppu._mask.show_sprites = True
        ppu._mask.show_left_bg = True
        ppu._mask.show_left_sprites = True
        ppu._ctrl.bg_pattern_addr = 0
        ppu._ctrl.sprite_pattern_addr = 0
        ppu._ctrl.sprite_size = 8
        ppu._vram_addr = 0
        ppu._fine_x = 0

        # Background: non-transparent
        bus.write(0x2000, 0x01)  # tile 1
        bus.write(0x0010, 0xFF)
        bus.write(0x0018, 0x00)
        bus.write(0x23C0, 0x00)
        bus.write(0x3F01, 0x05)

        # Sprite at (0, 0), priority=1 (behind bg), non-transparent
        ppu._oam[0] = 0xFF  # y=255, so sprite covers y=0 (0xFF+1 wraps to 0)
        ppu._oam[1] = 2
        ppu._oam[2] = 0x20  # priority=1
        ppu._oam[3] = 0
        # Wait - y=0xFF means screen y = 0 (0xFF+1=0x100, but screen wraps)
        # Actually sprite Y = 0xFF means the sprite starts at screen y = 0 (0xFF+1 mod 256)
        # No - the sprite Y in OAM is directly the Y position on screen + 1 offset
        # Let me use a clearer setup: sprite at screen y=0 -> OAM y = 0xFF (offset -1)
        # Actually the standard is: sprite appears at OAM_y + 1 on screen
        # So OAM_y = 0xFF -> screen y = 0

        # Better: just set OAM y = 0 for screen y = 1, and render at y = 1
        ppu._oam[0] = 0  # sprite starts at screen y = 1
        # Then render at y = 1
        # Let me simplify this test

        bus.write(0x0020, 0xFF)
        bus.write(0x0028, 0x00)
        bus.write(0x3F11, 0x12)

        # Render pixel at (0, 0)
        _renderer(ppu).render_pixel(0, 0)
        fb = _renderer(ppu).get_framebuffer()
        # Since sprite covers (0, 0) but has priority=1 (behind bg),
        # and bg is non-transparent, bg colour should win
        bg_color = _nes_rgb(5)
        assert fb[0] == bg_color

    def test_render_pixel_bg_in_front_of_transparent_sprite(self) -> None:
        """When sprite pixel is transparent, bg should be used."""
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu._mask.show_bg = True
        ppu._mask.show_sprites = True
        ppu._mask.show_left_bg = True
        ppu._ctrl.bg_pattern_addr = 0
        ppu._ctrl.sprite_pattern_addr = 0
        ppu._ctrl.sprite_size = 8
        ppu._vram_addr = 0
        ppu._fine_x = 0

        # Background non-transparent
        bus.write(0x2000, 0x01)
        bus.write(0x0010, 0xFF)
        bus.write(0x0018, 0x00)
        bus.write(0x23C0, 0x00)
        bus.write(0x3F01, 0x05)

        # No sprites -> sprite returns transparent
        _renderer(ppu).render_pixel(0, 0)
        fb = _renderer(ppu).get_framebuffer()
        assert fb[0] == _nes_rgb(5)


# ---------------------------------------------------------------------------
# Sprite 0 hit tests
# ---------------------------------------------------------------------------


class TestSpriteZeroHit:
    def test_sprite_zero_hit_set_when_both_opaque(self) -> None:
        """Sprite 0 hit should be set when both sprite 0 and bg are non-transparent."""
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu._mask.show_bg = True
        ppu._mask.show_sprites = True
        ppu._mask.show_left_bg = True
        ppu._mask.show_left_sprites = True
        ppu._ctrl.bg_pattern_addr = 0
        ppu._ctrl.sprite_pattern_addr = 0
        ppu._ctrl.sprite_size = 8
        ppu._vram_addr = 0
        ppu._fine_x = 0

        # Background at (0, 0): non-transparent
        bus.write(0x2000, 0x01)
        bus.write(0x0010, 0xFF)
        bus.write(0x0018, 0x00)
        bus.write(0x23C0, 0x00)
        bus.write(0x3F01, 0x05)

        # Sprite 0 at (0, 0): non-transparent, in front of bg
        ppu._oam[0] = 0xFF  # screen y = 0 (0xFF + 1 wraps)
        ppu._oam[1] = 0
        ppu._oam[2] = 0x00  # priority=0 (in front), palette=0
        ppu._oam[3] = 0
        bus.write(0x0000, 0xFF)  # tile 0, row 0
        bus.write(0x0008, 0x01)  # non-transparent bit 1
        bus.write(0x3F11, 0x12)

        _renderer(ppu).render_pixel(0, 0)
        assert ppu._status.sprite_zero_hit is True

    def test_sprite_zero_hit_not_set_when_sprite_transparent(self) -> None:
        """Sprite 0 hit should NOT be set when sprite 0 pixel is transparent."""
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu._mask.show_bg = True
        ppu._mask.show_sprites = True
        ppu._mask.show_left_bg = True
        ppu._mask.show_left_sprites = True
        ppu._ctrl.bg_pattern_addr = 0
        ppu._ctrl.sprite_pattern_addr = 0
        ppu._ctrl.sprite_size = 8
        ppu._vram_addr = 0
        ppu._fine_x = 0

        # Background non-transparent
        bus.write(0x2000, 0x01)
        bus.write(0x0010, 0xFF)
        bus.write(0x0018, 0x00)
        bus.write(0x23C0, 0x00)
        bus.write(0x3F01, 0x05)

        # Sprite 0 transparent (all-zero pattern)
        ppu._oam[0] = 0xFF
        ppu._oam[1] = 0
        ppu._oam[2] = 0x00
        ppu._oam[3] = 0
        bus.write(0x0000, 0x00)
        bus.write(0x0008, 0x00)

        _renderer(ppu).render_pixel(0, 0)
        assert ppu._status.sprite_zero_hit is False

    def test_sprite_zero_hit_not_set_when_bg_transparent(self) -> None:
        """Sprite 0 hit should NOT be set when background is transparent."""
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu._mask.show_bg = True
        ppu._mask.show_sprites = True
        ppu._mask.show_left_bg = True
        ppu._mask.show_left_sprites = True
        ppu._ctrl.bg_pattern_addr = 0
        ppu._ctrl.sprite_pattern_addr = 0
        ppu._ctrl.sprite_size = 8
        ppu._vram_addr = 0
        ppu._fine_x = 0

        # Background transparent (colour index 0, tile 0)
        bus.write(0x2000, 0x00)
        bus.write(0x0000, 0x00)
        bus.write(0x0008, 0x00)
        bus.write(0x23C0, 0x00)
        bus.write(0x3F00, 0x01)

        # Sprite 0 non-transparent -- use tile 1 to avoid overwriting bg pattern
        ppu._oam[0] = 0xFF
        ppu._oam[1] = 1
        ppu._oam[2] = 0x00
        ppu._oam[3] = 0
        bus.write(0x0010, 0xFF)
        bus.write(0x0018, 0x00)
        bus.write(0x3F11, 0x12)

        _renderer(ppu).render_pixel(0, 0)
        assert ppu._status.sprite_zero_hit is False


# ---------------------------------------------------------------------------
# Reset test
# ---------------------------------------------------------------------------


class TestPPUReset:
    def test_reset_clears_all_state(self) -> None:
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu.write_register(0x2000, 0xFF)
        ppu.write_register(0x2001, 0xFF)
        ppu._status.vblank = True
        ppu._status.sprite_zero_hit = True
        ppu._status.sprite_overflow = True
        ppu._vram_addr = 0x3FFF
        ppu._temp_addr = 0x1234
        ppu._write_toggle = True
        ppu._fine_x = 7
        ppu._data_buffer = 0xFF
        ppu._scanline = 100
        ppu._cycle = 200
        ppu._frame = 999
        ppu._nmi_occurred = True

        ppu.reset()

        assert ppu._ctrl == PPUCTRL()
        assert ppu._mask == PPUMASK()
        assert ppu._status == PPUSTATUS()
        assert ppu._vram_addr == 0
        assert ppu._temp_addr == 0
        assert ppu._write_toggle is False
        assert ppu._fine_x == 0
        assert ppu._data_buffer == 0
        assert ppu._scanline == 261
        assert ppu._cycle == 0
        assert ppu._frame == 0
        assert ppu._even_frame is True
        assert ppu._nmi_occurred is False


# ---------------------------------------------------------------------------
# Renderer colour helper
# ---------------------------------------------------------------------------


class TestRendererColor:
    def test_nes_color_all_palette_entries(self) -> None:
        """Verify every palette entry produces a valid RGB integer."""
        for i in range(64):
            color = Renderer._nes_color(i)
            r = (color >> 16) & 0xFF
            g = (color >> 8) & 0xFF
            b = color & 0xFF
            assert (r, g, b) == NES_PALETTE[i]

    def test_nes_color_wraps(self) -> None:
        """Palette index above 63 should wrap."""
        assert Renderer._nes_color(64) == Renderer._nes_color(0)
        assert Renderer._nes_color(128) == Renderer._nes_color(0)


# ---------------------------------------------------------------------------
# Left-edge clipping tests
# ---------------------------------------------------------------------------


class TestLeftEdgeClipping:
    def test_bg_clipped_when_show_left_bg_false(self) -> None:
        """BG pixel at x < 8 should be transparent when show_left_bg is False."""
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu._mask.show_bg = True
        ppu._mask.show_left_bg = False
        ppu._ctrl.bg_pattern_addr = 0
        ppu._vram_addr = 0
        ppu._fine_x = 0

        # Set up a non-transparent tile at nametable $2000
        bus.write(0x2000, 0x01)
        bus.write(0x0010, 0xFF)
        bus.write(0x0018, 0x00)
        bus.write(0x23C0, 0x00)
        bus.write(0x3F01, 0x05)

        r = _renderer(ppu)
        # x=0 (in left 8px) should be transparent
        color = r._get_bg_pixel(0, 0)
        assert color == 0
        assert r._bg_color_index == 0

        # x=7 (still in left 8px) should be transparent
        color = r._get_bg_pixel(7, 0)
        assert color == 0
        assert r._bg_color_index == 0

    def test_bg_not_clipped_when_show_left_bg_true(self) -> None:
        """BG pixel at x < 8 should render normally when show_left_bg is True."""
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu._mask.show_bg = True
        ppu._mask.show_left_bg = True
        ppu._ctrl.bg_pattern_addr = 0
        ppu._vram_addr = 0
        ppu._fine_x = 0

        bus.write(0x2000, 0x01)
        bus.write(0x0010, 0xFF)
        bus.write(0x0018, 0x00)
        bus.write(0x23C0, 0x00)
        bus.write(0x3F01, 0x05)

        r = _renderer(ppu)
        color = r._get_bg_pixel(0, 0)
        assert color == _nes_rgb(5)
        assert r._bg_color_index != 0

    def test_sprite_clipped_when_show_left_sprites_false(self) -> None:
        """Sprite pixel at x < 8 should not render when show_left_sprites is False."""
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu._mask.show_sprites = True
        ppu._mask.show_left_sprites = False
        ppu._ctrl.sprite_pattern_addr = 0
        ppu._ctrl.sprite_size = 8

        # Sprite 0 at x=3, y=0
        ppu._oam[0] = 0xFF  # screen y = 0
        ppu._oam[1] = 2
        ppu._oam[2] = 0x00
        ppu._oam[3] = 3  # x = 3 (in left 8px)

        bus.write(0x0020, 0xFF)
        bus.write(0x0028, 0x00)
        bus.write(0x3F11, 0x12)

        r = _renderer(ppu)
        # x=3 is in left 8px, sprite should be clipped
        color, prio = r._get_sprite_pixel(3, 0)
        assert color == 0
        assert r._sprite_index == -1

        # Move sprite to x=10 (outside left 8px)
        ppu._oam[3] = 10
        color, prio = r._get_sprite_pixel(10, 0)
        assert color == _nes_rgb(0x12)
        assert r._sprite_index == 0

    def test_sprite_zero_hit_blocked_by_left_clipping(self) -> None:
        """Sprite zero hit should not fire at x < 8 when BG clipping is active."""
        bus = MockPPUBus()
        ppu = PPU(bus)
        ppu._mask.show_bg = True
        ppu._mask.show_sprites = True
        ppu._mask.show_left_bg = False  # clip BG on left
        ppu._mask.show_left_sprites = True
        ppu._ctrl.bg_pattern_addr = 0
        ppu._ctrl.sprite_pattern_addr = 0
        ppu._ctrl.sprite_size = 8
        ppu._vram_addr = 0
        ppu._fine_x = 0

        # BG: non-transparent tile at x=0
        bus.write(0x2000, 0x01)
        bus.write(0x0010, 0xFF)
        bus.write(0x0018, 0x00)
        bus.write(0x23C0, 0x00)
        bus.write(0x3F01, 0x05)

        # Sprite 0 at (0, 0): non-transparent
        ppu._oam[0] = 0xFF
        ppu._oam[1] = 0
        ppu._oam[2] = 0x00
        ppu._oam[3] = 0
        bus.write(0x0000, 0xFF)
        bus.write(0x0008, 0x01)
        bus.write(0x3F11, 0x12)

        _renderer(ppu).render_pixel(0, 0)
        # BG is clipped, so bg_color_index == 0, sprite_zero_hit should not fire
        assert ppu._status.sprite_zero_hit is False


# ---------------------------------------------------------------------------
# tick_scanlines sprite_zero_hit test
# ---------------------------------------------------------------------------


class TestTickScanlinesSpriteZeroHit:
    def test_tick_scanlines_clears_sprite_zero_hit_at_241(self) -> None:
        """tick_scanlines should clear sprite_zero_hit at scanline 241."""
        bus = MockPPUBus()
        ppu = PPU(bus, use_fast_renderer=False)
        ppu._status.sprite_zero_hit = True
        # Advance from initial scanline 261 to scanline 241
        while ppu._scanline != 241:
            ppu.tick_scanlines(1)
        # At scanline 241, sprite_zero_hit should be cleared
        ppu.tick_scanlines(1)
        assert ppu._status.sprite_zero_hit is False
