/* iNES ROM + Mapper 0 + Controller */
#define _CRT_SECURE_NO_WARNINGS
#include "nes_internal.h"
#include "fb_debug.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int cart_load(Nes* n, const char* path) {
    FILE* f = fopen(path, "rb");
    if (!f) return -1;

    uint8_t header[16];
    if (fread(header, 1, 16, f) != 16) {
        fclose(f);
        return -2;
    }
    if (header[0] != 'N' || header[1] != 'E' || header[2] != 'S' || header[3] != 0x1A) {
        fclose(f);
        return -3;
    }

    int prg_banks = header[4];
    int chr_banks = header[5];
    int mapper = (header[6] >> 4) | (header[7] & 0xF0);
    int mirroring = (header[6] & 0x01) ? 1 : 0; /* 1=vertical */
    int has_trainer = header[6] & 0x04;

    cart_free(n);

    n->cart.prg_size = prg_banks * 16384;
    n->cart.chr_size = chr_banks * 8192;
    n->cart.mirroring = mirroring;
    n->cart.mapper = mapper;

    if (n->cart.prg_size <= 0) {
        fclose(f);
        return -4;
    }
    n->cart.prg = (uint8_t*)malloc((size_t)n->cart.prg_size);
    if (!n->cart.prg) {
        fclose(f);
        return -5;
    }

    if (has_trainer) {
        uint8_t trainer[512];
        if (fread(trainer, 1, 512, f) != 512) {
            fclose(f);
            return -6;
        }
    }

    if (fread(n->cart.prg, 1, (size_t)n->cart.prg_size, f) != (size_t)n->cart.prg_size) {
        fclose(f);
        return -7;
    }

    if (n->cart.chr_size > 0) {
        n->cart.chr = (uint8_t*)malloc((size_t)n->cart.chr_size);
        if (!n->cart.chr) {
            fclose(f);
            return -8;
        }
        if (fread(n->cart.chr, 1, (size_t)n->cart.chr_size, f) != (size_t)n->cart.chr_size) {
            fclose(f);
            return -9;
        }
        n->cart.chr_is_ram = 0; /* CHR ROM — ignore PPU writes */
    } else {
        /* CHR RAM */
        n->cart.chr_size = 8192;
        n->cart.chr = (uint8_t*)calloc(1, 8192);
        if (!n->cart.chr) {
            fclose(f);
            return -10;
        }
        n->cart.chr_is_ram = 1;
    }

    fclose(f);
    n->ppu_mem.chr = n->cart.chr;
    n->ppu_mem.chr_size = n->cart.chr_size;
    n->ppu_mem.mirroring = mirroring;
    n->loaded = 1;
    return 0;
}

void cart_free(Nes* n) {
    free(n->cart.prg);
    free(n->cart.chr);
    n->cart.prg = NULL;
    n->cart.chr = NULL;
    n->cart.prg_size = 0;
    n->cart.chr_size = 0;
    n->ppu_mem.chr = NULL;
    n->loaded = 0;
}

/* ---- Mapper 0 ---- */
static uint8_t mapper0_cpu_read(Nes* n, uint16_t addr) {
    if (!n->cart.prg) return 0;
    int idx = (addr - 0x8000) % n->cart.prg_size;
    return n->cart.prg[idx];
}

static void mapper0_cpu_write(Nes* n, uint16_t addr, uint8_t v) {
    (void)n;
    (void)addr;
    (void)v;
}

/* ---- Controller ---- */
void controller_write(Nes* n, uint8_t v) {
    int s = v & 1;
    /* Latch on rising strobe and while strobe is held high.
       On falling edge (1->0) re-latch so the last sample is used. */
    if (s || n->pad.strobe) {
        n->pad.shift = n->pad.buttons;
    }
    n->pad.strobe = s;
}

uint8_t controller_read(Nes* n) {
    uint8_t v = n->pad.shift & 1;
    if (!n->pad.strobe) {
        n->pad.shift = (uint8_t)((n->pad.shift >> 1) | 0x80);
    }
    return v;
}

/* ---- CPU bus ---- */
uint8_t cpu_read(Nes* n, uint16_t addr) {
    addr &= 0xFFFF;
    if (addr >= 0x8000) return mapper0_cpu_read(n, addr);
    if (addr < 0x2000) return n->ram[addr & 0x7FF];
    if (addr < 0x4000) return ppu_reg_read(n, 0x2000 + (addr & 7));
    if (addr == 0x4016) return controller_read(n);
    if (addr == 0x4015) return apu_reg_read(n, addr);
    return 0;
}

void cpu_write(Nes* n, uint16_t addr, uint8_t v) {
    addr &= 0xFFFF;
    v &= 0xFF;
    if (addr < 0x2000) {
        n->ram[addr & 0x7FF] = v;
    } else if (addr < 0x4000) {
        ppu_reg_write(n, 0x2000 + (addr & 7), v);
    } else if (addr == 0x4014) {
        /* OAM DMA */
        uint16_t base = (uint16_t)(v << 8);
        for (int i = 0; i < 256; i++) {
            uint8_t b = cpu_read(n, (uint16_t)(base + i));
            n->ppu.oam[n->ppu.oam_addr] = b;
            n->ppu.oam_addr = (uint8_t)(n->ppu.oam_addr + 1);
        }
        n->cpu.stall += 513;
    } else if (addr == 0x4016) {
        controller_write(n, v);
    } else if (addr < 0x4018) {
        apu_reg_write(n, addr, v);
    } else {
        mapper0_cpu_write(n, addr, v);
    }
}

/* ---- PPU bus ---- */
static int mirror_nt(Nes* n, uint16_t addr) {
    int a = (addr - 0x2000) % 0x1000;
    int table = a / 0x400; /* 0..3 */
    int offset = a % 0x400;
    if (n->ppu_mem.mirroring == 1) {
        /* Vertical mirroring (iNES flag=1): $2000=$2800, $2400=$2C00 */
        return ((table & 1) * 0x400) + offset;
    }
    /* Horizontal mirroring (flag=0): $2000=$2400, $2800=$2C00 */
    return ((table >> 1) * 0x400) + offset;
}

static int mirror_pal(int addr) {
    /* $3F00-$3F0F are unique; $3F10-$3F1F mirror $3F00-$3F0F.
       $3F04/$3F08/$3F0C are NOT mirrors of $3F00 — they are separate
       palette RAM bytes (unused for BG color 0 during rendering). */
    int a = (addr - 0x3F00) % 0x20;
    if (a >= 0x10) {
        a -= 0x10;
    }
    return a;
}

uint8_t ppu_read(Nes* n, uint16_t addr) {
    addr &= 0x3FFF;
    if (addr < 0x2000) {
        if (!n->ppu_mem.chr) return 0;
        int idx = addr % n->ppu_mem.chr_size;
        return n->ppu_mem.chr[idx];
    }
    if (addr < 0x3F00) {
        return n->ppu_mem.nametable[mirror_nt(n, addr)];
    }
    return n->ppu_mem.palette[mirror_pal(addr)];
}

void ppu_write(Nes* n, uint16_t addr, uint8_t v) {
    addr &= 0x3FFF;
    v &= 0xFF;
    if (addr < 0x2000) {
        /* CHR ROM is not writable; only CHR RAM accepts writes */
        if (n->cart.chr_is_ram && n->ppu_mem.chr) {
            int idx = addr % n->ppu_mem.chr_size;
            n->ppu_mem.chr[idx] = v;
        }
    } else if (addr < 0x3F00) {
        n->ppu_mem.nametable[mirror_nt(n, addr)] = v;
    } else {
        n->ppu_mem.palette[mirror_pal(addr)] = v;
    }
}

uint8_t ppu_reg_read(Nes* n, uint16_t addr) {
    Ppu* p = &n->ppu;
    switch (addr & 7) {
        case 2: {
            uint8_t v = p->status;
            p->status = (uint8_t)(p->status & ~0x80); /* clear vblank */
            p->w = 0;
            return v;
        }
        case 4:
            return p->oam[p->oam_addr];
        case 7: {
            uint8_t v = ppu_read(n, p->v);
            if (p->v < 0x3F00) {
                uint8_t buffered = p->data_buffer;
                p->data_buffer = v;
                p->v = (uint16_t)((p->v + ((p->ctrl & 0x04) ? 32 : 1)) & 0x7FFF);
                return buffered;
            }
            p->v = (uint16_t)((p->v + ((p->ctrl & 0x04) ? 32 : 1)) & 0x7FFF);
            return v;
        }
        default:
            return 0;
    }
}

static void wrlog_add(Nes* n, uint8_t kind, uint16_t addr, uint8_t v) {
#ifdef FB_DEBUG
    if (n->wrlog_n < 128) {
        int i = n->wrlog_n++;
        n->wrlog[i].kind = kind;
        n->wrlog[i].value = v;
        n->wrlog[i].addr = addr;
        n->wrlog[i].scanline = (int16_t)n->ppu.scanline;
        n->wrlog[i].cycle = (int16_t)n->ppu.cycle;
    } else {
        n->wrlog_full = 1;
    }
    FB_TRACE("wr kind=%d addr=%04X v=%02X sl=%d cy=%d\n",
             kind, addr, v, n->ppu.scanline, n->ppu.cycle);
#else
    (void)n; (void)kind; (void)addr; (void)v;
#endif
}

void ppu_reg_write(Nes* n, uint16_t addr, uint8_t v) {
    Ppu* p = &n->ppu;
    switch (addr & 7) {
        case 0: {
            int old_nmi = (p->ctrl & 0x80) != 0;
            p->ctrl = v;
            if (n->ctrl_log_n < 32) {
                n->ctrl_log[n->ctrl_log_n++] = v;
            }
            wrlog_add(n, 0, addr, v);
            p->t = (uint16_t)((p->t & 0xF3FF) | ((v & 0x03) << 10));
            if (!old_nmi && (p->ctrl & 0x80) && p->nmi_occurred) {
                p->nmi_output = 1;
            }
            break;
        }
        case 1:
            p->mask = v;
            wrlog_add(n, 1, addr, v);
            break;
        case 3:
            p->oam_addr = v;
            break;
        case 4:
            p->oam[p->oam_addr] = v;
            p->oam_addr = (uint8_t)(p->oam_addr + 1);
            break;
        case 5:
            n->scroll_writes++;
            wrlog_add(n, 4, addr, v);
            if (!p->w) {
                p->t = (uint16_t)((p->t & 0xFFE0) | (v >> 3));
                p->x = (uint8_t)(v & 0x07);
            } else {
                p->t = (uint16_t)((p->t & 0x8C1F) | ((v & 0xF8) << 2) | ((v & 0x07) << 12));
            }
            p->w = !p->w;
            break;
        case 6:
            n->scroll_writes++;
            wrlog_add(n, 5, addr, v);
            if (!p->w) {
                p->t = (uint16_t)((p->t & 0x80FF) | ((v & 0x3F) << 8));
            } else {
                p->t = (uint16_t)((p->t & 0xFF00) | v);
                p->v = p->t;
            }
            p->w = !p->w;
            break;
        case 7:
            wrlog_add(n, 6, p->v, v);
            ppu_write(n, p->v, v);
            p->v = (uint16_t)((p->v + ((p->ctrl & 0x04) ? 32 : 1)) & 0x7FFF);
            break;
        default:
            break;
    }
}
