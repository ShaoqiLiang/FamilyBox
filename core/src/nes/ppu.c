/* PPU timing + full-frame renderer */
#include "fb_debug.h"
#include "nes_internal.h"
#include <string.h>

/* 64-entry NES palette as RGB */
static const uint8_t NES_PAL[64][3] = {
    {84, 84, 84},    {0, 30, 116},    {8, 16, 144},    {48, 0, 136},    {68, 0, 100},    {92, 0, 48},
    {84, 4, 0},      {60, 24, 0},     {32, 42, 0},     {8, 58, 0},      {0, 64, 0},      {0, 60, 0},
    {0, 50, 60},     {0, 0, 0},       {0, 0, 0},       {0, 0, 0},       {152, 150, 152}, {8, 76, 196},
    {48, 50, 236},   {92, 30, 228},   {136, 20, 176},  {160, 20, 100},  {152, 34, 32},   {120, 60, 0},
    {84, 90, 0},     {40, 114, 0},    {8, 124, 0},     {0, 118, 40},    {0, 102, 120},   {0, 0, 0},
    {0, 0, 0},       {0, 0, 0},       {236, 238, 236}, {76, 154, 236},  {120, 124, 236}, {176, 98, 236},
    {228, 84, 236},  {236, 88, 180},  {236, 106, 100}, {212, 136, 32},  {160, 170, 0},   {116, 196, 0},
    {76, 208, 32},   {56, 204, 108},  {56, 180, 204},  {60, 60, 60},    {0, 0, 0},       {0, 0, 0},
    {236, 238, 236}, {168, 204, 236}, {188, 188, 236}, {212, 178, 236}, {236, 174, 236}, {236, 174, 212},
    {236, 180, 176}, {228, 196, 144}, {204, 210, 120}, {180, 222, 120}, {168, 226, 144}, {152, 226, 180},
    {160, 214, 228}, {160, 162, 160}, {0, 0, 0},       {0, 0, 0}};

void ppu_reset(Nes *n)
{
    Ppu *p = &n->ppu;
    memset(p, 0, sizeof(*p));
    p->scanline = n->timing.prerender_scanline;
    p->even_frame = 1;
}

static int show_bg(const Ppu *p) { return (p->mask & 0x08) != 0; }
static int show_sp(const Ppu *p) { return (p->mask & 0x10) != 0; }
static int show_left_bg(const Ppu *p) { return (p->mask & 0x02) != 0; }
static int show_left_sp(const Ppu *p) { return (p->mask & 0x04) != 0; }
static int bg_pattern(const Ppu *p) { return (p->ctrl & 0x10) ? 0x1000 : 0; }
static int sp_pattern(const Ppu *p) { return (p->ctrl & 0x08) ? 0x1000 : 0; }
static int sp_height(const Ppu *p) { return (p->ctrl & 0x20) ? 16 : 8; }

static void inc_hori(Nes *n)
{
    Ppu *p = &n->ppu;
    if ((p->v & 0x001F) == 31)
    {
        p->v &= (uint16_t)~0x001F;
        p->v ^= 0x0400;
    }
    else
    {
        p->v++;
    }
}

static void inc_vert(Nes *n)
{
    Ppu *p = &n->ppu;
    if ((p->v & 0x7000) != 0x7000)
    {
        p->v = (uint16_t)(p->v + 0x1000);
    }
    else
    {
        p->v &= (uint16_t)~0x7000;
        int y = (p->v & 0x03E0) >> 5;
        if (y == 29)
        {
            y = 0;
            p->v ^= 0x0800;
        }
        else if (y == 31)
        {
            y = 0;
        }
        else
        {
            y++;
        }
        p->v = (uint16_t)((p->v & ~0x03E0) | (y << 5));
    }
}

static void copy_hori(Nes *n)
{
    Ppu *p = &n->ppu;
    p->v = (uint16_t)((p->v & ~0x041F) | (p->t & 0x041F));
}

static void copy_vert(Nes *n)
{
    Ppu *p = &n->ppu;
    p->v = (uint16_t)((p->v & ~0x7BE0) | (p->t & 0x7BE0));
}

static void put_pixel(Nes *n, int x, int y, uint8_t pal_idx)
{
    const uint8_t *c = NES_PAL[pal_idx & 0x3F];
    int off = (y * SCREEN_W + x) * 3;
    n->ppu.framebuffer[off] = c[0];
    n->ppu.framebuffer[off + 1] = c[1];
    n->ppu.framebuffer[off + 2] = c[2];
}

static void render_scanline(Nes *n, int y)
{
    Ppu *p = &n->ppu;
    uint8_t bg_pix[256];
    memset(bg_pix, 0, sizeof(bg_pix));

    uint8_t backdrop = ppu_read(n, 0x3F00);

    if (show_bg(p))
    {
        /* Use v snapshotted at scanline start so mid-line $2006 writes
           do not rewrite the line currently being drawn. */
        uint16_t vv = p->render_v;
        int fine_x = p->x;

        int start_tile = 0;
        if (fine_x > 0)
        {
            start_tile = -1;
            if ((vv & 0x001F) == 0)
            {
                vv = (uint16_t)((vv & ~0x001F) | 0x001F);
                vv ^= 0x0400;
            }
            else
            {
                vv = (uint16_t)(vv - 1);
            }
        }

        for (int tile_x = start_tile; tile_x < 33; tile_x++)
        {
            uint16_t nt = (uint16_t)(0x2000 | (vv & 0x0FFF));
            uint8_t tile = ppu_read(n, nt);
            uint16_t pat = (uint16_t)(bg_pattern(p) + tile * 16);
            int fine_y = (vv >> 12) & 7;
            uint8_t lo = ppu_read(n, (uint16_t)(pat + fine_y));
            uint8_t hi = ppu_read(n, (uint16_t)(pat + fine_y + 8));

            uint16_t at = (uint16_t)(0x23C0 | (vv & 0x0C00) | ((vv >> 4) & 0x38) | ((vv >> 2) & 0x07));
            uint8_t attr = ppu_read(n, at);
            int shift = ((vv >> 4) & 4) | (vv & 2);
            uint8_t pal = (uint8_t)((attr >> shift) & 0x03);

            for (int px = 0; px < 8; px++)
            {
                int sx = tile_x * 8 + px - fine_x;
                if (sx < 0 || sx >= 256)
                    continue;
                int bit = 7 - px;
                uint8_t ci = (uint8_t)(((lo >> bit) & 1) | (((hi >> bit) & 1) << 1));
                if (!show_left_bg(p) && sx < 8)
                {
                    bg_pix[sx] = 0;
                    put_pixel(n, sx, y, backdrop);
                    continue;
                }
                bg_pix[sx] = ci;
                uint16_t paddr = (ci == 0) ? (uint16_t)0x3F00 : (uint16_t)(0x3F00 + pal * 4 + ci);
                put_pixel(n, sx, y, ppu_read(n, paddr));
            }

            /* increment local vv only */
            if ((vv & 0x001F) == 31)
            {
                vv = (uint16_t)((vv & ~0x001F) ^ 0x0400);
            }
            else
            {
                vv = (uint16_t)(vv + 1);
            }
        }
    }
    else
    {
        for (int x = 0; x < 256; x++)
            put_pixel(n, x, y, backdrop);
    }

    if (show_sp(p))
    {
        int height = sp_height(p);
        uint8_t sp_claimed[256];
        memset(sp_claimed, 0, sizeof(sp_claimed));

        for (int i = 0; i < 64; i++)
        {
            int sy = p->oam[i * 4];
            int tile = p->oam[i * 4 + 1];
            int attr = p->oam[i * 4 + 2];
            int sx = p->oam[i * 4 + 3];
            int start_y = (sy + 1) & 0xFF;
            int rel = y - start_y;
            if (rel < 0 || rel >= height)
                continue;

            if (attr & 0x80)
                rel = height - 1 - rel;
            uint16_t pat;
            int row = rel;
            if (height == 16)
            {
                int t = tile & 0xFE;
                int table = (tile & 1) * 0x1000;
                if (rel >= 8)
                {
                    t++;
                    row = rel - 8;
                }
                pat = (uint16_t)(table + t * 16 + row);
            }
            else
            {
                pat = (uint16_t)(sp_pattern(p) + tile * 16 + row);
            }
            uint8_t lo = ppu_read(n, pat);
            uint8_t hi = ppu_read(n, (uint16_t)(pat + 8));

            for (int px = 0; px < 8; px++)
            {
                int x = sx + px;
                if (x < 0 || x >= 256)
                    continue;
                if (!show_left_sp(p) && x < 8)
                    continue;
                int bit = (attr & 0x40) ? px : (7 - px);
                uint8_t ci = (uint8_t)(((lo >> bit) & 1) | (((hi >> bit) & 1) << 1));
                if (ci == 0)
                    continue;
                if (sp_claimed[x])
                    continue;
                sp_claimed[x] = 1;

                if (i == 0 && bg_pix[x] != 0 && show_bg(p) && x != 255)
                {
                    if (x >= 8 || (show_left_bg(p) && show_left_sp(p)))
                    {
                        if (!(p->status & 0x40))
                        {
                            FB_TRACE("s0hit first sl=%d x=%d bgci=%d\n", y, x, bg_pix[x]);
                            n->last_s0_scanline = y;
                        }
                        p->status |= 0x40;
                        n->s0_hit_count++;
                    }
                }

                if ((attr & 0x20) && bg_pix[x] != 0)
                {
                    continue;
                }
                uint16_t paddr = (uint16_t)(0x3F10 + (attr & 3) * 4 + ci);
                put_pixel(n, x, y, ppu_read(n, paddr));
            }
        }
    }
}

void render_frame(Nes *n)
{
    /* Frame is rendered incrementally during ppu_step on visible lines. */
    (void)n;
}

/* Advance the PPU by exactly *ppu_dots* PPU cycles (341 per scanline).
   Returns 1 if an NMI should be raised for the CPU this step. */
int ppu_step(Nes *n, int ppu_dots)
{
    Ppu *p = &n->ppu;
    int nmi = 0;

    for (int i = 0; i < ppu_dots; i++)
    {
        if (p->nmi_output)
        {
            nmi = 1;
            p->nmi_output = 0;
        }

        int visible = (p->scanline >= 0 && p->scanline < 240);
        int prerender = (p->scanline == n->timing.prerender_scanline);

        if (p->scanline == 0 && p->cycle == 0)
        {
            memset(p->framebuffer, 0, sizeof(p->framebuffer));
        }

        if (visible && p->cycle == 0)
        {
            p->render_v = p->v;
        }

        int rendering = (p->mask & 0x18) != 0;

        if (visible && p->cycle == 256)
        {
            render_scanline(n, p->scanline);
            if (rendering)
            {
                inc_vert(n);
            }
        }

        if ((visible || prerender) && p->cycle == 257 && rendering)
        {
            copy_hori(n);
        }

        if (prerender && p->cycle >= 280 && p->cycle <= 304 && rendering)
        {
            copy_vert(n);
        }

        if (prerender && p->cycle == 1)
        {
            p->status = (uint8_t)(p->status & ~0xE0);
            p->nmi_occurred = 0;
        }

        if (p->scanline == 241 && p->cycle == 1)
        {
            p->status |= 0x80;
            p->nmi_occurred = 1;
            if (p->ctrl & 0x80)
            {
                nmi = 1;
            }
        }

        p->cycle++;
        if (p->cycle > 340)
        {
            p->cycle = 0;
            p->scanline++;
            if (p->scanline > n->timing.prerender_scanline)
            {
                p->scanline = 0;
                p->frame++;
                p->even_frame = !p->even_frame;
            }
        }
    }
    return nmi;
}
