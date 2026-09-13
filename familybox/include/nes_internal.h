/* Internal types shared across the C core. */
#ifndef NES_INTERNAL_H
#define NES_INTERNAL_H

#include <stddef.h>
#include <stdint.h>

#define CPU_RAM_SIZE 0x800
#define NT_RAM_SIZE  0x800
#define PALETTE_SIZE 0x20
#define OAM_SIZE     0x100
#define SCREEN_W     256
#define SCREEN_H     240
#define FRAME_RGB    (SCREEN_W * SCREEN_H * 3)

/* ---- Flags ---- */
#define F_C          0x01
#define F_Z          0x02
#define F_I          0x04
#define F_D          0x08
#define F_B          0x10
#define F_U          0x20
#define F_V          0x40
#define F_N          0x80

typedef struct
{
    uint8_t a, x, y, sp, p;
    uint16_t pc;
} CpuRegs;

typedef struct
{
    CpuRegs r;
    int stall;
    uint64_t cycles;
    int nmi_pending;
    int irq_pending;
} Cpu;

typedef struct
{
    uint8_t nametable[NT_RAM_SIZE];
    uint8_t palette[PALETTE_SIZE];
    /* pattern tables: CHR ROM/RAM */
    uint8_t *chr;
    int chr_size;
    int mirroring; /* 0=H, 1=V */
} PpuMem;

typedef struct
{
    /* $2000 */
    uint8_t ctrl;
    /* $2001 */
    uint8_t mask;
    /* $2002 bits live in status */
    uint8_t status; /* bit7 vblank, bit6 s0hit, bit5 overflow */
    uint8_t oam_addr;
    uint8_t oam[OAM_SIZE];

    uint16_t v; /* current VRAM addr */
    uint16_t t; /* temporary VRAM addr */
    uint8_t x;  /* fine X */
    uint8_t data_buffer;
    int w; /* write toggle */

    int scanline; /* -1=261 pre-render, 0-239 visible, 240 post, 241-260 vblank */
    int cycle;    /* 0-340 */
    int frame;
    int even_frame;

    int nmi_occurred;
    int nmi_output;

    uint16_t render_v; /* loopy v snapshotted at start of each visible line */
    uint8_t framebuffer[FRAME_RGB];
} Ppu;

/* APU channel state */
typedef struct
{
    int enabled;
    int duty;
    int length_counter;
    int constant_volume;
    int volume;
    int envelope;
    int envelope_loop;
    int envelope_start;
    int envelope_divider;
    int envelope_decay;
    int sweep_enabled;
    int sweep_period;
    int sweep_negate;
    int sweep_shift;
    int sweep_reload;
    int sweep_divider;
    int timer;
    int timer_period;
    int duty_index;
} PulseCh;

typedef struct
{
    int enabled;
    int length_counter;
    int linear_counter;
    int linear_counter_reload;
    int linear_control;
    int linear_reload_flag;
    int timer;
    int timer_period;
    int sequence_index;
} TriangleCh;

typedef struct
{
    int enabled;
    int length_counter;
    int constant_volume;
    int volume;
    int envelope;
    int envelope_loop;
    int envelope_start;
    int envelope_divider;
    int envelope_decay;
    int mode; /* 0=short feedback, 1=long */
    int timer;
    int timer_period;
    uint16_t shift_reg;
} NoiseCh;

typedef struct
{
    PulseCh pulse1, pulse2;
    TriangleCh tri;
    NoiseCh noise;
    int frame_counter;
    int frame_mode; /* 0=4-step, 1=5-step */
    int frame_step;
    int irq_inhibit;
    double sample_timer;
    double cycles_per_sample;
    int sample_rate;
} Apu;

typedef struct
{
    uint8_t buttons; /* latched bit0=A ... bit7=Right */
    uint8_t strobe;
    uint8_t shift;
} Controller;

typedef struct
{
    uint8_t *prg;
    int prg_size;
    uint8_t *chr;
    int chr_size;
    int mirroring;
    int mapper;
    int chr_is_ram;       /* 1 if CHR is RAM (writable), 0 if ROM */
    uint8_t wram[0x2000]; /* $6000-$7FFF PRG RAM (battery-backed on some boards) */
} Cart;

typedef struct Nes
{
    Cpu cpu;
    Ppu ppu;
    PpuMem ppu_mem;
    Apu apu;
    Controller pad;
    Cart cart;
    uint8_t ram[CPU_RAM_SIZE];
    int loaded;
    /* debug: last PPUCTRL write values */
    uint8_t ctrl_log[32];
    int ctrl_log_n;
    /* debug: v sampled at start of scanlines 0, 20, 40, 100 */
    uint16_t v_samples[4];
    int s0_hit_count;
    int scroll_writes;
    /* detailed write ring: kind, addr, value, scanline, cycle */
    /* kind: 0=ctrl, 1=mask, 2=status_read, 3=oam, 4=scroll2005, 5=addr2006, 6=data2007 */
    struct
    {
        uint8_t kind;
        uint8_t value;
        uint16_t addr;
        int16_t scanline;
        int16_t cycle;
    } wrlog[128];
    int wrlog_n;
    int wrlog_full;
    int nmi_count;
    int last_s0_scanline;
} Nes;

/* bus.c */
uint8_t cpu_read(Nes *n, uint16_t addr);
void cpu_write(Nes *n, uint16_t addr, uint8_t v);
uint8_t ppu_read(Nes *n, uint16_t addr);
void ppu_write(Nes *n, uint16_t addr, uint8_t v);
uint8_t ppu_reg_read(Nes *n, uint16_t addr);
void ppu_reg_write(Nes *n, uint16_t addr, uint8_t v);
void apu_reg_write(Nes *n, uint16_t addr, uint8_t v);
uint8_t apu_reg_read(Nes *n, uint16_t addr);

/* cpu.c */
void cpu_reset(Nes *n);
int cpu_tick(Nes *n);
void cpu_trigger_nmi(Nes *n);

/* ppu.c */
void ppu_reset(Nes *n);
/* Advance by *ppu_dots* PPU cycles (341 per scanline). Returns 1 if NMI fired. */
int ppu_step(Nes *n, int ppu_dots);
void render_frame(Nes *n);

/* apu.c */
void apu_reset(Nes *n);
void apu_tick(Nes *n, int cpu_cycles, int16_t *pcm, int max_samples, int *out_count);

/* cart.c */
int cart_load(Nes *n, const char *path);
void cart_free(Nes *n);

/* controller.c */
void controller_write(Nes *n, uint8_t v);
uint8_t controller_read(Nes *n);

#endif /* NES_INTERNAL_H */
