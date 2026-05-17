"""NES system top-level coordinator.

Assembles all components (CPU, PPU, APU, Bus, Mapper, Controller),
coordinates the main loop, frame execution, event handling, and
screen presentation.
"""

#  *
#  * @Author: ShaoqiLiang
#  * @Date: 2026-05-16 22:07:49
#  * @LastEditors: ShaoqiLiang
#  *

import array
from typing import cast

import pygame

from familybox.apu.apu import APU
from familybox.bus.cpu_bus import CPUBus
from familybox.bus.ppu_bus import PPUBus
from familybox.cartridge.rom import ROMLoader
from familybox.cpu.cpu import CPU
from familybox.input.controller import Joystick
from familybox.ppu.ppu import PPU
from familybox.types import NESButton, PPUBusInterface


class NES:
    """NES system top-level class that coordinates all components."""

    def __init__(self, rom_path: str, headless: bool = False) -> None:
        # Load ROM
        loader = ROMLoader(rom_path)
        self._header, self._mapper = loader.load()

        # Create components
        self._controller: Joystick = Joystick()
        self._apu: APU = APU()
        self._ppu_bus: PPUBus = PPUBus(self._mapper, self._header.mirroring)
        # PPUBus provides read/write; PPU provides read_register/write_register.
        # PPUBusInterface bundles both roles, so cast at the boundaries.
        self._ppu: PPU = PPU(cast(PPUBusInterface, self._ppu_bus))
        self._cpu_bus: CPUBus = CPUBus(
            cast(PPUBusInterface, self._ppu),
            self._apu,
            self._mapper,
            self._controller,
        )
        self._cpu: CPU = CPU(self._cpu_bus)

        # Pre-allocated pixel buffer for _present()
        self._pixel_buf: bytearray = bytearray(256 * 240 * 3)

        # pygame initialisation
        self._headless: bool = headless
        if not headless:
            pygame.init()
            self._screen: pygame.Surface = pygame.display.set_mode((256, 240))
            pygame.display.set_caption("FamilyBox -Auth:ShaoqiLiang")
            self._clock: pygame.time.Clock = pygame.time.Clock()
            self._audio_buffer_size: int = 4096
            pygame.mixer.init(
                frequency=44100,
                size=-16,
                channels=1,
                buffer=self._audio_buffer_size,
            )

        self._running: bool = True

    def reset(self) -> None:
        """Reset CPU, PPU, and APU to initial state."""
        self._cpu.reset()
        self._ppu.reset()
        self._apu.reset()

    def run(self) -> None:
        """Run the main emulation loop."""
        self.reset()
        self._warmup_ppu()

        while self._running:
            self._run_frame()
            if not self._headless:
                self._handle_events()
                self._audio_output()
                self._present()
                self._clock.tick(60)

    def _run_frame(self) -> None:
        """Execute one full frame (262 scanlines)."""
        cycles_per_scanline: int = 113  # ~113.667 CPU cycles per scanline

        for _scanline in range(262):
            # Batch PPU: advance one full scanline FIRST so CPU sees VBlank
            if self._ppu.tick_scanlines(1):
                self._cpu.trigger_nmi()

            # Run CPU for one scanline (~113 cycles)
            cycles: int = 0
            while cycles < cycles_per_scanline:
                cpu_cycles: int = self._cpu.tick()
                cycles += cpu_cycles

            # Batch APU: advance by total CPU cycles used this scanline
            self._apu.tick(cycles)

    def _warmup_ppu(self) -> None:
        """Advance PPU to first VBlank so CPU sees it on boot."""
        for _ in range(262):
            self._ppu.tick_scanlines(1)
            if self._ppu._status.vblank:
                break

    def _audio_output(self) -> None:
        """Retrieve APU samples and play them via pygame.mixer."""
        samples = self._apu.get_sample_buffer()
        if not samples:
            return
        pcm = array.array(
            "h", (max(-32768, min(32767, int(s * 32767))) for s in samples)
        )
        sound = pygame.mixer.Sound(buffer=pcm)
        sound.play()

    def _handle_events(self) -> None:
        """Process pygame events (QUIT, KEYDOWN, KEYUP)."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._running = False
            elif event.type == pygame.KEYDOWN:
                self._handle_key(event.key, True)
            elif event.type == pygame.KEYUP:
                self._handle_key(event.key, False)

    def _handle_key(self, key: int, pressed: bool) -> None:
        """Map keyboard key to NES controller button."""
        key_map: dict[int, NESButton] = {
            pygame.K_z: NESButton.A,
            pygame.K_x: NESButton.B,
            pygame.K_RSHIFT: NESButton.SELECT,
            pygame.K_RETURN: NESButton.START,
            pygame.K_UP: NESButton.UP,
            pygame.K_DOWN: NESButton.DOWN,
            pygame.K_LEFT: NESButton.LEFT,
            pygame.K_RIGHT: NESButton.RIGHT,
        }
        if key in key_map:
            self._controller.set_button(key_map[key], pressed)

    def _present(self) -> None:
        """Render the framebuffer to the pygame screen."""
        renderer = self._ppu._renderer
        # Fast path: C renderer returns RGB bytes directly
        if hasattr(renderer, "get_framebuffer_bytes"):
            pixels = renderer.get_framebuffer_bytes()
        else:
            framebuffer = renderer.get_framebuffer()
            pixels = self._pixel_buf
            for i in range(61440):
                color = framebuffer[i]
                off = i * 3
                pixels[off] = (color >> 16) & 0xFF
                pixels[off + 1] = (color >> 8) & 0xFF
                pixels[off + 2] = color & 0xFF
            pixels = bytes(pixels)
        surface = pygame.image.frombuffer(pixels, (256, 240), "RGB")
        self._screen.blit(surface, (0, 0))
        pygame.display.flip()

