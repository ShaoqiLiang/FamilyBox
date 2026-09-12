/* Public API + frame orchestration */
#include "familybox.h"
#include "nes_internal.h"
#include "fb_debug.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* NTSC: 341 PPU dots per scanline, ~113.667 CPU cycles per scanline. */
#define PPU_DOTS_PER_SCANLINE 341
#define SCANLINES_PER_FRAME 262

Nes* nes_create(void) {
    Nes* n = (Nes*)calloc(1, sizeof(Nes));
    if (!n) return NULL;
    apu_reset(n);
    ppu_reset(n);
    FB_DBG("core created (debug=%d)\n", FB_DEBUG_ENABLED);
    return n;
}

void nes_destroy(Nes* n) {
    if (!n) return;
    cart_free(n);
    free(n);
}

int nes_load_rom(Nes* n, const char* path) {
    if (!n || !path) return -1;
    return cart_load(n, path);
}

void nes_reset(Nes* n) {
    if (!n) return;
    memset(n->ram, 0, sizeof(n->ram));
    memset(n->ppu_mem.nametable, 0, sizeof(n->ppu_mem.nametable));
    memset(n->ppu_mem.palette, 0, sizeof(n->ppu_mem.palette));
    memset(n->ppu.oam, 0, sizeof(n->ppu.oam));
    ppu_reset(n);
    apu_reset(n);
    cpu_reset(n);
}

void nes_set_buttons(Nes* n, uint8_t buttons) {
    if (!n) return;
    n->pad.buttons = buttons;
    if (n->pad.strobe) {
        n->pad.shift = buttons;
    }
}

void nes_get_debug(Nes* n, uint16_t* pc, uint8_t* a, uint8_t* x, uint8_t* y, uint8_t* p) {
    if (!n) return;
    if (pc) *pc = n->cpu.r.pc;
    if (a) *a = n->cpu.r.a;
    if (x) *x = n->cpu.r.x;
    if (y) *y = n->cpu.r.y;
    if (p) *p = n->cpu.r.p;
}

void nes_dump_palette(Nes* n, uint8_t* out32) {
    if (!n || !out32) return;
    memcpy(out32, n->ppu_mem.palette, 32);
}

uint8_t nes_peek_ppu(Nes* n, uint16_t addr) {
    if (!n) return 0;
    return ppu_read(n, addr);
}

uint8_t nes_get_ppuctrl(Nes* n) { return n ? n->ppu.ctrl : 0; }
uint8_t nes_get_ppumask(Nes* n) { return n ? n->ppu.mask : 0; }
uint16_t nes_get_v(Nes* n) { return n ? n->ppu.v : 0; }

uint8_t nes_get_status(Nes* n) { return n ? n->ppu.status : 0; }

void nes_dump_oam(Nes* n, uint8_t* out256) {
    if (!n || !out256) return;
    memcpy(out256, n->ppu.oam, 256);
}

uint8_t nes_peek_cpu(Nes* n, uint16_t addr) {
    if (!n) return 0;
    return cpu_read(n, addr);
}

int nes_ctrl_log(Nes* n, uint8_t* out, int max) {
    if (!n || !out || max <= 0) return 0;
    int m = n->ctrl_log_n < max ? n->ctrl_log_n : max;
    memcpy(out, n->ctrl_log, (size_t)m);
    n->ctrl_log_n = 0;
    return m;
}

void nes_get_v_samples(Nes* n, uint16_t* out4) {
    if (!n || !out4) return;
    memcpy(out4, n->v_samples, sizeof(n->v_samples));
}

uint16_t nes_get_t(Nes* n) { return n ? n->ppu.t : 0; }

int nes_get_s0_hits(Nes* n) { return n ? n->s0_hit_count : 0; }

void nes_reset_s0_hits(Nes* n) {
    if (n) n->s0_hit_count = 0;
}

int nes_debug_enabled(void) { return FB_DEBUG_ENABLED; }

int nes_get_scroll_writes(Nes* n) { return n ? n->scroll_writes : 0; }

int nes_get_nmi_count(Nes* n) { return n ? n->nmi_count : 0; }

int nes_get_last_s0_sl(Nes* n) { return n ? n->last_s0_scanline : -1; }

int nes_wrlog_copy(Nes* n, uint8_t* out, int max_entries) {
    if (!n || !out || max_entries <= 0) return 0;
    int m = n->wrlog_n < max_entries ? n->wrlog_n : max_entries;
    for (int i = 0; i < m; i++) {
        out[i * 8 + 0] = n->wrlog[i].kind;
        out[i * 8 + 1] = n->wrlog[i].value;
        out[i * 8 + 2] = (uint8_t)(n->wrlog[i].addr & 0xFF);
        out[i * 8 + 3] = (uint8_t)(n->wrlog[i].addr >> 8);
        out[i * 8 + 4] = (uint8_t)(n->wrlog[i].scanline & 0xFF);
        out[i * 8 + 5] = (uint8_t)((n->wrlog[i].scanline >> 8) & 0xFF);
        out[i * 8 + 6] = (uint8_t)(n->wrlog[i].cycle & 0xFF);
        out[i * 8 + 7] = (uint8_t)((n->wrlog[i].cycle >> 8) & 0xFF);
    }
    n->wrlog_n = 0;
    n->wrlog_full = 0;
    return m;
}

/* CPU cycles for one scanline: 113 or 114 to average ~113.667 */
static int cpu_cycles_for_scanline(int sl) {
    return 113 + ((sl % 3) == 2 ? 1 : 0);
}

int nes_run_frame(Nes* n, uint8_t* rgb, int16_t* pcm, int max_samples) {
    if (!n || !n->loaded) return -1;

    int total_samples = 0;

    for (int sl = 0; sl < SCANLINES_PER_FRAME; sl++) {
        int budget = cpu_cycles_for_scanline(sl);
        int dots_done = 0;
        int cpu_used = 0;

        while (dots_done < PPU_DOTS_PER_SCANLINE) {
            int step = 3;
            if (dots_done + step > PPU_DOTS_PER_SCANLINE) {
                step = PPU_DOTS_PER_SCANLINE - dots_done;
            }
            if (dots_done == 0) {
                if (n->ppu.scanline == 0) n->v_samples[0] = n->ppu.v;
                if (n->ppu.scanline == 20) n->v_samples[1] = n->ppu.v;
                if (n->ppu.scanline == 40) n->v_samples[2] = n->ppu.v;
                if (n->ppu.scanline == 100) n->v_samples[3] = n->ppu.v;
            }
            if (ppu_step(n, step)) {
                cpu_trigger_nmi(n);
#ifdef FB_DEBUG
                n->nmi_count++;
                FB_TRACE("NMI sl=%d cy=%d pc=%04X\n", n->ppu.scanline, n->ppu.cycle, n->cpu.r.pc);
#endif
            }
            dots_done += step;

            if (cpu_used < budget) {
                int c = cpu_tick(n);
                if (c <= 0) c = 1;
                cpu_used += c;
                int produced = 0;
                int remain = max_samples - total_samples;
                if (pcm && remain > 0) {
                    apu_tick(n, c, pcm + total_samples, remain, &produced);
                } else {
                    apu_tick(n, c, NULL, 0, &produced);
                }
                total_samples += produced;
            }
        }
    }

#if FB_DEBUG_ENABLED
    if (n->ppu.frame % 60 == 0) {
        uint8_t* oam = n->ppu.oam;
        uint8_t* pal = n->ppu_mem.palette;
        int nz = 0;
        if (rgb) {
            for (int i = 0; i < FRAME_RGB; i += 3) {
                if (rgb[i] | rgb[i + 1] | rgb[i + 2]) nz++;
            }
        }
        FB_DBG("t=%lums frame=%d pc=%04X A=%02X X=%02X Y=%02X P=%02X\n",
               fb_now_ms(), n->ppu.frame, n->cpu.r.pc, n->cpu.r.a,
               n->cpu.r.x, n->cpu.r.y, n->cpu.r.p);
        FB_DBG("  ctrl=%02X mask=%02X status=%02X v=%04X t=%04X fineX=%d sl=%d\n",
               n->ppu.ctrl, n->ppu.mask, n->ppu.status, n->ppu.v, n->ppu.t, n->ppu.x,
               n->ppu.scanline);
        FB_DBG("  v@0/20/40/100=%04X/%04X/%04X/%04X  s0hits=%d last_s0_sl=%d nmi=%d\n",
               n->v_samples[0], n->v_samples[1], n->v_samples[2], n->v_samples[3],
               n->s0_hit_count, n->last_s0_scanline, n->nmi_count);
        FB_DBG("  oam0=%02X %02X %02X %02X  pal0-3=%02X %02X %02X %02X  fb_nz=%d\n",
               oam[0], oam[1], oam[2], oam[3], pal[0], pal[1], pal[2], pal[3], nz);
        FB_DBG("  scroll_writes=%d wrlog=%d%s  ram073F/0740/0778=%02X %02X %02X\n",
               n->scroll_writes, n->wrlog_n, n->wrlog_full ? "+" : "",
               n->ram[0x73F], n->ram[0x740], n->ram[0x778]);
        FB_DBG("  nt0[0..7]=%02X %02X %02X %02X %02X %02X %02X %02X\n",
               n->ppu_mem.nametable[0], n->ppu_mem.nametable[1],
               n->ppu_mem.nametable[2], n->ppu_mem.nametable[3],
               n->ppu_mem.nametable[4], n->ppu_mem.nametable[5],
               n->ppu_mem.nametable[6], n->ppu_mem.nametable[7]);
        int start = n->wrlog_n > 8 ? n->wrlog_n - 8 : 0;
        for (int i = start; i < n->wrlog_n; i++) {
            FB_DBG("  wr[%d] kind=%d addr=%04X v=%02X sl=%d cy=%d\n",
                   i, n->wrlog[i].kind, n->wrlog[i].addr, n->wrlog[i].value,
                   n->wrlog[i].scanline, n->wrlog[i].cycle);
        }
        n->wrlog_n = 0;
        n->wrlog_full = 0;
    }
#endif

    if (rgb) {
        memcpy(rgb, n->ppu.framebuffer, FRAME_RGB);
    }
    return total_samples;
}
