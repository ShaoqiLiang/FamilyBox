/*
 * renderer_c.c — Fast PPU renderer for FamilyBox NES emulator.
 *
 * Renders one scanline (256 pixels) of background and sprites directly
 * into an RGB byte buffer, bypassing Python function-call overhead.
 *
 * Compile:
 *   Windows (MSVC):  cl /O2 /LD renderer_c.c /Fe:renderer_c.dll
 *   Windows (MinGW): gcc -O2 -shared -o renderer_c.dll renderer_c.c
 *   Linux:           gcc -O2 -shared -fPIC -o renderer_c.so renderer_c.c
 *   macOS:           gcc -O2 -shared -fPIC -o renderer_c.dylib renderer_c.c
 */

//   *
//   * @Author: ShaoqiLiang
//   * @Date: 2026-05-16 22:07:49
//   * @LastEditors: ShaoqiLiang
//   *

#include <string.h>

/* NES standard palette: 64 RGB triplets */
static const unsigned char NES_PALETTE[64][3] = {
    {84,84,84},   {0,30,116},   {8,16,144},   {48,0,136},
    {68,0,100},   {92,0,48},    {84,4,0},     {60,24,0},
    {32,42,0},    {8,58,0},     {0,64,0},     {0,60,0},
    {0,50,60},    {0,0,0},      {0,0,0},      {0,0,0},
    {152,150,152},{8,76,196},   {48,50,236},  {92,30,228},
    {136,20,176},{160,20,100},  {152,34,32},  {120,60,0},
    {84,90,0},   {40,114,0},   {8,124,0},    {0,118,40},
    {0,102,120}, {0,0,0},      {0,0,0},      {0,0,0},
    {236,238,236},{76,154,236}, {120,124,236},{176,98,236},
    {228,84,236},{236,88,180},  {236,106,100},{212,136,32},
    {160,170,0}, {116,196,0},  {76,208,32},  {56,204,108},
    {56,180,204},{60,60,60},   {0,0,0},      {0,0,0},
    {236,238,236},{168,204,236},{188,188,236},{212,178,236},
    {236,174,236},{236,174,212},{236,180,176},{228,196,144},
    {204,210,120},{180,222,120},{168,226,144},{152,226,180},
    {160,214,228},{160,162,160},{0,0,0},      {0,0,0}
};

/* Inline bus read: dispatches address to the correct buffer */
static inline unsigned char bus_read(
    int addr,
    const unsigned char *chr_rom,
    const unsigned char *nametable,
    const unsigned char *palette,
    int mirroring
) {
    addr &= 0x3FFF;
    if (addr < 0x2000) {
        return chr_rom[addr];
    }
    if (addr < 0x3F00) {
        /* Nametable mirroring */
        int a = (addr - 0x2000) % 0x1000;
        int idx;
        if (mirroring == 1) { /* Vertical */
            idx = (a % 0x400) | ((a / 0x800) * 0x400);
        } else { /* Horizontal */
            int table = a / 0x400;
            int offset = a % 0x400;
            idx = (table / 2) * 0x400 + offset;
        }
        return nametable[idx];
    }
    /* Palette mirroring */
    {
        int a = (addr - 0x3F00) % 0x20;
        if (a % 4 == 0) a = 0;
        return palette[a];
    }
}

/* Render one scanline into the framebuffer (RGB byte buffer) */
void render_scanline(
    unsigned char *framebuffer,      /* 256*3 bytes output (RGB) */
    const unsigned char *oam,        /* 256 bytes */
    const unsigned char *nametable,  /* 2048 bytes */
    const unsigned char *palette,    /* 32 bytes */
    const unsigned char *chr_rom,    /* up to 8192 bytes */
    int scanline,                    /* 0-239 */
    int vram_addr,                   /* 15-bit */
    int fine_x,                      /* 0-7 */
    int bg_pattern_addr,             /* 0 or 0x1000 */
    int sprite_pattern_addr,         /* 0 or 0x1000 */
    int sprite_size,                 /* 8 or 16 */
    int show_bg,
    int show_sprites,
    int show_left_bg,                /* 1 = show BG in left 8px */
    int show_left_sprites,           /* 1 = show sprites in left 8px */
    int mirroring,                   /* 0=H, 1=V */
    int *sprite_zero_hit_out         /* output: set to 1 if sprite 0 hit */
) {
    int x;
    int y = scanline;
    int fb_off = y * 256 * 3;

    for (x = 0; x < 256; x++) {
        unsigned int bg_color = 0;
        int bg_color_index = 0;
        unsigned int sprite_color = 0;
        int sprite_priority = 0;
        int sprite_idx = -1;
        unsigned int final_color;
        const unsigned char *c;

        /* ---- Background pixel ---- */
        if (show_bg) {
            /* Left 8px clipping: when show_left_bg is off, x=0..7 are transparent */
            if (!show_left_bg && x < 8) {
                /* bg_color_index stays 0 -- transparent */
            } else {
                int abs_x = (x + fine_x) & 0x1FF;
                int abs_y = (y + ((vram_addr >> 12) & 0x07)) & 0x1FF;
                int coarse_x = abs_x >> 3;
                int coarse_y = abs_y >> 3;
                int fx = abs_x & 0x07;
                int fy = abs_y & 0x07;
                int nt_addr, tile_index, pattern_addr, lo, hi, bit;
                int attr_addr, attr_byte, shift, palette_index, palette_addr;
                unsigned char pal_idx;

                nt_addr = 0x2000
                    | (vram_addr & 0x0C00)
                    | ((coarse_y % 30) << 5)
                    | (coarse_x % 32);

                tile_index = bus_read(nt_addr, chr_rom, nametable, palette, mirroring);

                pattern_addr = bg_pattern_addr + tile_index * 16;
                lo = bus_read(pattern_addr + fy, chr_rom, nametable, palette, mirroring);
                hi = bus_read(pattern_addr + fy + 8, chr_rom, nametable, palette, mirroring);
                bit = 7 - fx;
                bg_color_index = ((lo >> bit) & 1) | (((hi >> bit) & 1) << 1);

                attr_addr = 0x23C0
                    | (vram_addr & 0x0C00)
                    | (((coarse_y % 30) >> 2) << 3)
                    | ((coarse_x % 32) >> 2);
                attr_byte = bus_read(attr_addr, chr_rom, nametable, palette, mirroring);
                shift = ((coarse_y & 2) << 1) | (coarse_x & 2);
                palette_index = (attr_byte >> shift) & 0x03;

                palette_addr = 0x3F00 + palette_index * 4 + bg_color_index;
                pal_idx = bus_read(palette_addr, chr_rom, nametable, palette, mirroring);
                c = NES_PALETTE[pal_idx & 0x3F];
                bg_color = ((unsigned int)c[0] << 16) | ((unsigned int)c[1] << 8) | c[2];
            }
        }

        /* ---- Sprite pixel ---- */
        if (show_sprites) {
            /* Left 8px clipping: when show_left_sprites is off, x=0..7 have no sprites */
            if (!show_left_sprites && x < 8) {
                /* sprite_idx stays -1 -- no sprite */
            } else {
            int i;
            for (i = 0; i < 64; i++) {
                int base = i << 2;
                int sy = oam[base];
                int stile = oam[base + 1];
                int sattr = oam[base + 2];
                int sx = oam[base + 3];
                int start_y, rel_y, rel_x;
                int table, tile, pattern_addr, lo, hi, bit, color_index;
                int palette_addr;
                unsigned char pal_idx;

                start_y = (sy + 1) & 0xFF;
                rel_y = (y - start_y) & 0xFF;
                if (rel_y >= sprite_size) continue;

                if (x < sx || x >= sx + 8) continue;

                rel_x = x - sx;

                if (sattr & 0x80) rel_y = sprite_size - 1 - rel_y;
                if (sattr & 0x40) rel_x = 7 - rel_x;

                if (sprite_size == 16) {
                    tile = stile & 0xFE;
                    table = (stile & 1) * 0x1000;
                    if (rel_y >= 8) { tile += 1; rel_y -= 8; }
                } else {
                    table = sprite_pattern_addr;
                    tile = stile;
                }

                pattern_addr = table + tile * 16 + rel_y;
                lo = bus_read(pattern_addr, chr_rom, nametable, palette, mirroring);
                hi = bus_read(pattern_addr + 8, chr_rom, nametable, palette, mirroring);
                bit = 7 - rel_x;
                color_index = ((lo >> bit) & 1) | (((hi >> bit) & 1) << 1);

                if (color_index == 0) continue;

                palette_addr = 0x3F10 + (sattr & 0x03) * 4 + color_index;
                pal_idx = bus_read(palette_addr, chr_rom, nametable, palette, mirroring);
                c = NES_PALETTE[pal_idx & 0x3F];
                sprite_color = ((unsigned int)c[0] << 16) | ((unsigned int)c[1] << 8) | c[2];
                sprite_priority = (sattr >> 5) & 1;
                sprite_idx = i;
                break;
            }
            }  /* end else (not clipped) */
        }

        /* ---- Compositing ---- */
        if (sprite_idx < 0) {
            final_color = bg_color;
        } else if (bg_color_index == 0) {
            final_color = sprite_color;
        } else if (sprite_priority) {
            final_color = bg_color;
        } else {
            final_color = sprite_color;
        }

        /* Sprite 0 hit: both sprite 0 and BG are non-transparent.
         * Cannot fire at x < 8 when either left-edge clip is off. */
        if (sprite_idx == 0 && bg_color_index != 0
            && (x >= 8 || (show_left_bg && show_left_sprites))) {
            *sprite_zero_hit_out = 1;
        }

        framebuffer[fb_off]     = (unsigned char)((final_color >> 16) & 0xFF);
        framebuffer[fb_off + 1] = (unsigned char)((final_color >> 8) & 0xFF);
        framebuffer[fb_off + 2] = (unsigned char)(final_color & 0xFF);
        fb_off += 3;
    }
}
