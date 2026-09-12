/* MOS 6502 CPU core */
#include "nes_internal.h"

void cpu_reset(Nes* n) {
    Cpu* c = &n->cpu;
    uint8_t lo = cpu_read(n, 0xFFFC);
    uint8_t hi = cpu_read(n, 0xFFFD);
    c->r.pc = (uint16_t)((hi << 8) | lo);
    c->r.sp = 0xFD;
    c->r.p = F_U | F_I;
    c->stall = 0;
    c->nmi_pending = 0;
    c->irq_pending = 0;
}

void cpu_trigger_nmi(Nes* n) {
    n->cpu.nmi_pending = 1;
}

static void set_zn(Nes* n, uint8_t v) {
    n->cpu.r.p = (uint8_t)((n->cpu.r.p & ~(F_Z | F_N)) | (v == 0 ? F_Z : 0) | (v & 0x80 ? F_N : 0));
}

static void set_flag(Nes* n, int flag, int cond) {
    if (cond) n->cpu.r.p = (uint8_t)(n->cpu.r.p | flag);
    else n->cpu.r.p = (uint8_t)(n->cpu.r.p & ~flag);
}

static void push8(Nes* n, uint8_t v) {
    cpu_write(n, (uint16_t)(0x100 + n->cpu.r.sp), v);
    n->cpu.r.sp = (uint8_t)(n->cpu.r.sp - 1);
}

static void push16(Nes* n, uint16_t v) {
    push8(n, (uint8_t)(v >> 8));
    push8(n, (uint8_t)(v & 0xFF));
}

static uint8_t pull8(Nes* n) {
    n->cpu.r.sp = (uint8_t)(n->cpu.r.sp + 1);
    return cpu_read(n, (uint16_t)(0x100 + n->cpu.r.sp));
}

static uint16_t pull16(Nes* n) {
    uint8_t lo = pull8(n);
    uint8_t hi = pull8(n);
    return (uint16_t)((hi << 8) | lo);
}

static uint8_t fetch8(Nes* n) {
    uint8_t v = cpu_read(n, n->cpu.r.pc);
    n->cpu.r.pc = (uint16_t)(n->cpu.r.pc + 1);
    return v;
}

static uint16_t fetch16(Nes* n) {
    uint8_t lo = fetch8(n);
    uint8_t hi = fetch8(n);
    return (uint16_t)((hi << 8) | lo);
}

/* addressing — return effective addr; *page_cross set when applicable */
static uint16_t am_imm(Nes* n) { return n->cpu.r.pc++; }
static uint16_t am_zp(Nes* n) { return fetch8(n); }
static uint16_t am_zpx(Nes* n) { return (uint16_t)((fetch8(n) + n->cpu.r.x) & 0xFF); }
static uint16_t am_zpy(Nes* n) { return (uint16_t)((fetch8(n) + n->cpu.r.y) & 0xFF); }
static uint16_t am_abs(Nes* n) { return fetch16(n); }

static uint16_t am_abx(Nes* n, int* pcross) {
    uint16_t base = fetch16(n);
    uint16_t addr = (uint16_t)(base + n->cpu.r.x);
    if (pcross) *pcross = ((base & 0xFF00) != (addr & 0xFF00));
    return addr;
}

static uint16_t am_aby(Nes* n, int* pcross) {
    uint16_t base = fetch16(n);
    uint16_t addr = (uint16_t)(base + n->cpu.r.y);
    if (pcross) *pcross = ((base & 0xFF00) != (addr & 0xFF00));
    return addr;
}

static uint16_t am_izx(Nes* n) {
    uint8_t z = (uint8_t)(fetch8(n) + n->cpu.r.x);
    uint8_t lo = cpu_read(n, z);
    uint8_t hi = cpu_read(n, (uint8_t)(z + 1));
    return (uint16_t)((hi << 8) | lo);
}

static uint16_t am_izy(Nes* n, int* pcross) {
    uint8_t z = fetch8(n);
    uint8_t lo = cpu_read(n, z);
    uint8_t hi = cpu_read(n, (uint8_t)(z + 1));
    uint16_t base = (uint16_t)((hi << 8) | lo);
    uint16_t addr = (uint16_t)(base + n->cpu.r.y);
    if (pcross) *pcross = ((base & 0xFF00) != (addr & 0xFF00));
    return addr;
}

/* JMP ($xxFF) page-wrap bug */
static uint16_t am_ind(Nes* n) {
    uint16_t ptr = fetch16(n);
    uint8_t lo = cpu_read(n, ptr);
    uint16_t hi_addr = (uint16_t)((ptr & 0xFF00) | ((ptr + 1) & 0x00FF));
    uint8_t hi = cpu_read(n, hi_addr);
    return (uint16_t)((hi << 8) | lo);
}

static void branch(Nes* n, int cond, int* cycles) {
    int8_t off = (int8_t)fetch8(n);
    if (cond) {
        uint16_t old = n->cpu.r.pc;
        n->cpu.r.pc = (uint16_t)(n->cpu.r.pc + off);
        (*cycles)++;
        if ((old & 0xFF00) != (n->cpu.r.pc & 0xFF00)) (*cycles)++;
    }
}

static void adc(Nes* n, uint8_t m) {
    uint16_t sum = (uint16_t)(n->cpu.r.a + m + (n->cpu.r.p & F_C));
    set_flag(n, F_C, sum > 0xFF);
    set_flag(n, F_V, (~(n->cpu.r.a ^ m) & (n->cpu.r.a ^ sum) & 0x80) != 0);
    n->cpu.r.a = (uint8_t)(sum & 0xFF);
    set_zn(n, n->cpu.r.a);
}

static void sbc(Nes* n, uint8_t m) { adc(n, (uint8_t)(m ^ 0xFF)); }

static void cmp_reg(Nes* n, uint8_t reg, uint8_t m) {
    uint16_t t = (uint16_t)(reg - m);
    set_flag(n, F_C, reg >= m);
    set_zn(n, (uint8_t)(t & 0xFF));
}

static void asl_mem(Nes* n, uint16_t addr) {
    uint8_t v = cpu_read(n, addr);
    set_flag(n, F_C, v & 0x80);
    v = (uint8_t)(v << 1);
    cpu_write(n, addr, v);
    set_zn(n, v);
}

static void lsr_mem(Nes* n, uint16_t addr) {
    uint8_t v = cpu_read(n, addr);
    set_flag(n, F_C, v & 0x01);
    v = (uint8_t)(v >> 1);
    cpu_write(n, addr, v);
    set_zn(n, v);
}

static void rol_mem(Nes* n, uint16_t addr) {
    uint8_t v = cpu_read(n, addr);
    int c = (n->cpu.r.p & F_C) != 0;
    set_flag(n, F_C, v & 0x80);
    v = (uint8_t)((v << 1) | (c ? 1 : 0));
    cpu_write(n, addr, v);
    set_zn(n, v);
}

static void ror_mem(Nes* n, uint16_t addr) {
    uint8_t v = cpu_read(n, addr);
    int c = (n->cpu.r.p & F_C) != 0;
    set_flag(n, F_C, v & 0x01);
    v = (uint8_t)((v >> 1) | (c ? 0x80 : 0));
    cpu_write(n, addr, v);
    set_zn(n, v);
}

static void handle_nmi(Nes* n) {
    push16(n, n->cpu.r.pc);
    push8(n, (uint8_t)(n->cpu.r.p & ~F_B));
    n->cpu.r.p = (uint8_t)(n->cpu.r.p | F_I);
    uint8_t lo = cpu_read(n, 0xFFFA);
    uint8_t hi = cpu_read(n, 0xFFFB);
    n->cpu.r.pc = (uint16_t)((hi << 8) | lo);
    n->cpu.nmi_pending = 0;
}

int cpu_tick(Nes* n) {
    Cpu* c = &n->cpu;
    if (c->stall > 0) {
        c->stall--;
        c->cycles++;
        return 1;
    }
    if (c->nmi_pending) {
        handle_nmi(n);
        c->cycles += 7;
        return 7;
    }

    uint8_t op = fetch8(n);
    int cycles = 2;
    int pcross = 0;
    uint16_t addr = 0;
    CpuRegs* r = &c->r;

    switch (op) {
        /* --- Official 6502 opcodes --- */
        case 0x69: addr = am_imm(n); adc(n, cpu_read(n, addr)); cycles = 2; break;
        case 0x65: addr = am_zp(n); adc(n, cpu_read(n, addr)); cycles = 3; break;
        case 0x75: addr = am_zpx(n); adc(n, cpu_read(n, addr)); cycles = 4; break;
        case 0x6D: addr = am_abs(n); adc(n, cpu_read(n, addr)); cycles = 4; break;
        case 0x7D: addr = am_abx(n, &pcross); adc(n, cpu_read(n, addr)); cycles = 4 + pcross; break;
        case 0x79: addr = am_aby(n, &pcross); adc(n, cpu_read(n, addr)); cycles = 4 + pcross; break;
        case 0x61: addr = am_izx(n); adc(n, cpu_read(n, addr)); cycles = 6; break;
        case 0x71: addr = am_izy(n, &pcross); adc(n, cpu_read(n, addr)); cycles = 5 + pcross; break;

        case 0x29: addr = am_imm(n); r->a &= cpu_read(n, addr); set_zn(n, r->a); cycles = 2; break;
        case 0x25: addr = am_zp(n); r->a &= cpu_read(n, addr); set_zn(n, r->a); cycles = 3; break;
        case 0x35: addr = am_zpx(n); r->a &= cpu_read(n, addr); set_zn(n, r->a); cycles = 4; break;
        case 0x2D: addr = am_abs(n); r->a &= cpu_read(n, addr); set_zn(n, r->a); cycles = 4; break;
        case 0x3D: addr = am_abx(n, &pcross); r->a &= cpu_read(n, addr); set_zn(n, r->a); cycles = 4 + pcross; break;
        case 0x39: addr = am_aby(n, &pcross); r->a &= cpu_read(n, addr); set_zn(n, r->a); cycles = 4 + pcross; break;
        case 0x21: addr = am_izx(n); r->a &= cpu_read(n, addr); set_zn(n, r->a); cycles = 6; break;
        case 0x31: addr = am_izy(n, &pcross); r->a &= cpu_read(n, addr); set_zn(n, r->a); cycles = 5 + pcross; break;

        case 0x0A: set_flag(n, F_C, r->a & 0x80); r->a = (uint8_t)(r->a << 1); set_zn(n, r->a); cycles = 2; break;
        case 0x06: addr = am_zp(n); asl_mem(n, addr); cycles = 5; break;
        case 0x16: addr = am_zpx(n); asl_mem(n, addr); cycles = 6; break;
        case 0x0E: addr = am_abs(n); asl_mem(n, addr); cycles = 6; break;
        case 0x1E: addr = am_abx(n, NULL); asl_mem(n, addr); cycles = 7; break;

        case 0x90: branch(n, !(r->p & F_C), &cycles); break; /* BCC */
        case 0xB0: branch(n, (r->p & F_C) != 0, &cycles); break; /* BCS */
        case 0xF0: branch(n, (r->p & F_Z) != 0, &cycles); break; /* BEQ */
        case 0x30: branch(n, (r->p & F_N) != 0, &cycles); break; /* BMI */
        case 0xD0: branch(n, !(r->p & F_Z), &cycles); break; /* BNE */
        case 0x10: branch(n, !(r->p & F_N), &cycles); break; /* BPL */
        case 0x50: branch(n, !(r->p & F_V), &cycles); break; /* BVC */
        case 0x70: branch(n, (r->p & F_V) != 0, &cycles); break; /* BVS */

        case 0x24: {
            addr = am_zp(n);
            uint8_t m = cpu_read(n, addr);
            set_flag(n, F_Z, (r->a & m) == 0);
            set_flag(n, F_V, m & 0x40);
            set_flag(n, F_N, m & 0x80);
            cycles = 3;
            break;
        }
        case 0x2C: {
            addr = am_abs(n);
            uint8_t m = cpu_read(n, addr);
            set_flag(n, F_Z, (r->a & m) == 0);
            set_flag(n, F_V, m & 0x40);
            set_flag(n, F_N, m & 0x80);
            cycles = 4;
            break;
        }

        case 0x18: set_flag(n, F_C, 0); cycles = 2; break; /* CLC */
        case 0xD8: set_flag(n, F_D, 0); cycles = 2; break; /* CLD */
        case 0x58: set_flag(n, F_I, 0); cycles = 2; break; /* CLI */
        case 0xB8: set_flag(n, F_V, 0); cycles = 2; break; /* CLV */
        case 0x38: set_flag(n, F_C, 1); cycles = 2; break; /* SEC */
        case 0xF8: set_flag(n, F_D, 1); cycles = 2; break; /* SED */
        case 0x78: set_flag(n, F_I, 1); cycles = 2; break; /* SEI */

        case 0xC9: addr = am_imm(n); cmp_reg(n, r->a, cpu_read(n, addr)); cycles = 2; break;
        case 0xC5: addr = am_zp(n); cmp_reg(n, r->a, cpu_read(n, addr)); cycles = 3; break;
        case 0xD5: addr = am_zpx(n); cmp_reg(n, r->a, cpu_read(n, addr)); cycles = 4; break;
        case 0xCD: addr = am_abs(n); cmp_reg(n, r->a, cpu_read(n, addr)); cycles = 4; break;
        case 0xDD: addr = am_abx(n, &pcross); cmp_reg(n, r->a, cpu_read(n, addr)); cycles = 4 + pcross; break;
        case 0xD9: addr = am_aby(n, &pcross); cmp_reg(n, r->a, cpu_read(n, addr)); cycles = 4 + pcross; break;
        case 0xC1: addr = am_izx(n); cmp_reg(n, r->a, cpu_read(n, addr)); cycles = 6; break;
        case 0xD1: addr = am_izy(n, &pcross); cmp_reg(n, r->a, cpu_read(n, addr)); cycles = 5 + pcross; break;

        case 0xE0: addr = am_imm(n); cmp_reg(n, r->x, cpu_read(n, addr)); cycles = 2; break;
        case 0xE4: addr = am_zp(n); cmp_reg(n, r->x, cpu_read(n, addr)); cycles = 3; break;
        case 0xEC: addr = am_abs(n); cmp_reg(n, r->x, cpu_read(n, addr)); cycles = 4; break;

        case 0xC0: addr = am_imm(n); cmp_reg(n, r->y, cpu_read(n, addr)); cycles = 2; break;
        case 0xC4: addr = am_zp(n); cmp_reg(n, r->y, cpu_read(n, addr)); cycles = 3; break;
        case 0xCC: addr = am_abs(n); cmp_reg(n, r->y, cpu_read(n, addr)); cycles = 4; break;

        case 0xC6: addr = am_zp(n); { uint8_t v = (uint8_t)(cpu_read(n, addr) - 1); cpu_write(n, addr, v); set_zn(n, v); } cycles = 5; break;
        case 0xD6: addr = am_zpx(n); { uint8_t v = (uint8_t)(cpu_read(n, addr) - 1); cpu_write(n, addr, v); set_zn(n, v); } cycles = 6; break;
        case 0xCE: addr = am_abs(n); { uint8_t v = (uint8_t)(cpu_read(n, addr) - 1); cpu_write(n, addr, v); set_zn(n, v); } cycles = 6; break;
        case 0xDE: addr = am_abx(n, NULL); { uint8_t v = (uint8_t)(cpu_read(n, addr) - 1); cpu_write(n, addr, v); set_zn(n, v); } cycles = 7; break;

        case 0xCA: r->x = (uint8_t)(r->x - 1); set_zn(n, r->x); cycles = 2; break; /* DEX */
        case 0x88: r->y = (uint8_t)(r->y - 1); set_zn(n, r->y); cycles = 2; break; /* DEY */

        case 0x49: addr = am_imm(n); r->a ^= cpu_read(n, addr); set_zn(n, r->a); cycles = 2; break;
        case 0x45: addr = am_zp(n); r->a ^= cpu_read(n, addr); set_zn(n, r->a); cycles = 3; break;
        case 0x55: addr = am_zpx(n); r->a ^= cpu_read(n, addr); set_zn(n, r->a); cycles = 4; break;
        case 0x4D: addr = am_abs(n); r->a ^= cpu_read(n, addr); set_zn(n, r->a); cycles = 4; break;
        case 0x5D: addr = am_abx(n, &pcross); r->a ^= cpu_read(n, addr); set_zn(n, r->a); cycles = 4 + pcross; break;
        case 0x59: addr = am_aby(n, &pcross); r->a ^= cpu_read(n, addr); set_zn(n, r->a); cycles = 4 + pcross; break;
        case 0x41: addr = am_izx(n); r->a ^= cpu_read(n, addr); set_zn(n, r->a); cycles = 6; break;
        case 0x51: addr = am_izy(n, &pcross); r->a ^= cpu_read(n, addr); set_zn(n, r->a); cycles = 5 + pcross; break;

        case 0xE6: addr = am_zp(n); { uint8_t v = (uint8_t)(cpu_read(n, addr) + 1); cpu_write(n, addr, v); set_zn(n, v); } cycles = 5; break;
        case 0xF6: addr = am_zpx(n); { uint8_t v = (uint8_t)(cpu_read(n, addr) + 1); cpu_write(n, addr, v); set_zn(n, v); } cycles = 6; break;
        case 0xEE: addr = am_abs(n); { uint8_t v = (uint8_t)(cpu_read(n, addr) + 1); cpu_write(n, addr, v); set_zn(n, v); } cycles = 6; break;
        case 0xFE: addr = am_abx(n, NULL); { uint8_t v = (uint8_t)(cpu_read(n, addr) + 1); cpu_write(n, addr, v); set_zn(n, v); } cycles = 7; break;

        case 0xE8: r->x = (uint8_t)(r->x + 1); set_zn(n, r->x); cycles = 2; break; /* INX */
        case 0xC8: r->y = (uint8_t)(r->y + 1); set_zn(n, r->y); cycles = 2; break; /* INY */

        case 0x4C: r->pc = fetch16(n); cycles = 3; break; /* JMP abs */
        case 0x6C: r->pc = am_ind(n); cycles = 5; break; /* JMP ind */

        case 0x20: {
            uint16_t target = fetch16(n);
            push16(n, (uint16_t)(r->pc - 1));
            r->pc = target;
            cycles = 6;
            break;
        }
        case 0x60: r->pc = (uint16_t)(pull16(n) + 1); cycles = 6; break; /* RTS */
        case 0x40: {
            r->p = pull8(n);
            r->p = (uint8_t)((r->p | F_U) & ~F_B);
            r->pc = pull16(n);
            cycles = 6;
            break;
        }

        case 0xA9: r->a = fetch8(n); set_zn(n, r->a); cycles = 2; break;
        case 0xA5: addr = am_zp(n); r->a = cpu_read(n, addr); set_zn(n, r->a); cycles = 3; break;
        case 0xB5: addr = am_zpx(n); r->a = cpu_read(n, addr); set_zn(n, r->a); cycles = 4; break;
        case 0xAD: addr = am_abs(n); r->a = cpu_read(n, addr); set_zn(n, r->a); cycles = 4; break;
        case 0xBD: addr = am_abx(n, &pcross); r->a = cpu_read(n, addr); set_zn(n, r->a); cycles = 4 + pcross; break;
        case 0xB9: addr = am_aby(n, &pcross); r->a = cpu_read(n, addr); set_zn(n, r->a); cycles = 4 + pcross; break;
        case 0xA1: addr = am_izx(n); r->a = cpu_read(n, addr); set_zn(n, r->a); cycles = 6; break;
        case 0xB1: addr = am_izy(n, &pcross); r->a = cpu_read(n, addr); set_zn(n, r->a); cycles = 5 + pcross; break;

        case 0xA2: r->x = fetch8(n); set_zn(n, r->x); cycles = 2; break;
        case 0xA6: addr = am_zp(n); r->x = cpu_read(n, addr); set_zn(n, r->x); cycles = 3; break;
        case 0xB6: addr = am_zpy(n); r->x = cpu_read(n, addr); set_zn(n, r->x); cycles = 4; break;
        case 0xAE: addr = am_abs(n); r->x = cpu_read(n, addr); set_zn(n, r->x); cycles = 4; break;
        case 0xBE: addr = am_aby(n, &pcross); r->x = cpu_read(n, addr); set_zn(n, r->x); cycles = 4 + pcross; break;

        case 0xA0: r->y = fetch8(n); set_zn(n, r->y); cycles = 2; break;
        case 0xA4: addr = am_zp(n); r->y = cpu_read(n, addr); set_zn(n, r->y); cycles = 3; break;
        case 0xB4: addr = am_zpx(n); r->y = cpu_read(n, addr); set_zn(n, r->y); cycles = 4; break;
        case 0xAC: addr = am_abs(n); r->y = cpu_read(n, addr); set_zn(n, r->y); cycles = 4; break;
        case 0xBC: addr = am_abx(n, &pcross); r->y = cpu_read(n, addr); set_zn(n, r->y); cycles = 4 + pcross; break;

        case 0x4A: set_flag(n, F_C, r->a & 0x01); r->a = (uint8_t)(r->a >> 1); set_zn(n, r->a); cycles = 2; break;
        case 0x46: addr = am_zp(n); lsr_mem(n, addr); cycles = 5; break;
        case 0x56: addr = am_zpx(n); lsr_mem(n, addr); cycles = 6; break;
        case 0x4E: addr = am_abs(n); lsr_mem(n, addr); cycles = 6; break;
        case 0x5E: addr = am_abx(n, NULL); lsr_mem(n, addr); cycles = 7; break;

        case 0xEA: cycles = 2; break; /* NOP */

        case 0x09: addr = am_imm(n); r->a |= cpu_read(n, addr); set_zn(n, r->a); cycles = 2; break;
        case 0x05: addr = am_zp(n); r->a |= cpu_read(n, addr); set_zn(n, r->a); cycles = 3; break;
        case 0x15: addr = am_zpx(n); r->a |= cpu_read(n, addr); set_zn(n, r->a); cycles = 4; break;
        case 0x0D: addr = am_abs(n); r->a |= cpu_read(n, addr); set_zn(n, r->a); cycles = 4; break;
        case 0x1D: addr = am_abx(n, &pcross); r->a |= cpu_read(n, addr); set_zn(n, r->a); cycles = 4 + pcross; break;
        case 0x19: addr = am_aby(n, &pcross); r->a |= cpu_read(n, addr); set_zn(n, r->a); cycles = 4 + pcross; break;
        case 0x01: addr = am_izx(n); r->a |= cpu_read(n, addr); set_zn(n, r->a); cycles = 6; break;
        case 0x11: addr = am_izy(n, &pcross); r->a |= cpu_read(n, addr); set_zn(n, r->a); cycles = 5 + pcross; break;

        case 0x48: push8(n, r->a); cycles = 3; break; /* PHA */
        case 0x08: push8(n, (uint8_t)(r->p | F_B | F_U)); cycles = 3; break; /* PHP */
        case 0x68: r->a = pull8(n); set_zn(n, r->a); cycles = 4; break; /* PLA */
        case 0x28: r->p = (uint8_t)((pull8(n) | F_U) & ~F_B); cycles = 4; break; /* PLP */

        case 0x2A: {
            int c = (r->p & F_C) != 0;
            set_flag(n, F_C, r->a & 0x80);
            r->a = (uint8_t)((r->a << 1) | (c ? 1 : 0));
            set_zn(n, r->a);
            cycles = 2;
            break;
        }
        case 0x26: addr = am_zp(n); rol_mem(n, addr); cycles = 5; break;
        case 0x36: addr = am_zpx(n); rol_mem(n, addr); cycles = 6; break;
        case 0x2E: addr = am_abs(n); rol_mem(n, addr); cycles = 6; break;
        case 0x3E: addr = am_abx(n, NULL); rol_mem(n, addr); cycles = 7; break;

        case 0x6A: {
            int c = (r->p & F_C) != 0;
            set_flag(n, F_C, r->a & 0x01);
            r->a = (uint8_t)((r->a >> 1) | (c ? 0x80 : 0));
            set_zn(n, r->a);
            cycles = 2;
            break;
        }
        case 0x66: addr = am_zp(n); ror_mem(n, addr); cycles = 5; break;
        case 0x76: addr = am_zpx(n); ror_mem(n, addr); cycles = 6; break;
        case 0x6E: addr = am_abs(n); ror_mem(n, addr); cycles = 6; break;
        case 0x7E: addr = am_abx(n, NULL); ror_mem(n, addr); cycles = 7; break;

        case 0xE9: addr = am_imm(n); sbc(n, cpu_read(n, addr)); cycles = 2; break;
        case 0xE5: addr = am_zp(n); sbc(n, cpu_read(n, addr)); cycles = 3; break;
        case 0xF5: addr = am_zpx(n); sbc(n, cpu_read(n, addr)); cycles = 4; break;
        case 0xED: addr = am_abs(n); sbc(n, cpu_read(n, addr)); cycles = 4; break;
        case 0xFD: addr = am_abx(n, &pcross); sbc(n, cpu_read(n, addr)); cycles = 4 + pcross; break;
        case 0xF9: addr = am_aby(n, &pcross); sbc(n, cpu_read(n, addr)); cycles = 4 + pcross; break;
        case 0xE1: addr = am_izx(n); sbc(n, cpu_read(n, addr)); cycles = 6; break;
        case 0xF1: addr = am_izy(n, &pcross); sbc(n, cpu_read(n, addr)); cycles = 5 + pcross; break;

        case 0x85: addr = am_zp(n); cpu_write(n, addr, r->a); cycles = 3; break;
        case 0x95: addr = am_zpx(n); cpu_write(n, addr, r->a); cycles = 4; break;
        case 0x8D: addr = am_abs(n); cpu_write(n, addr, r->a); cycles = 4; break;
        case 0x9D: addr = am_abx(n, NULL); cpu_write(n, addr, r->a); cycles = 5; break;
        case 0x99: addr = am_aby(n, NULL); cpu_write(n, addr, r->a); cycles = 5; break;
        case 0x81: addr = am_izx(n); cpu_write(n, addr, r->a); cycles = 6; break;
        case 0x91: addr = am_izy(n, NULL); cpu_write(n, addr, r->a); cycles = 6; break;

        case 0x86: addr = am_zp(n); cpu_write(n, addr, r->x); cycles = 3; break;
        case 0x96: addr = am_zpy(n); cpu_write(n, addr, r->x); cycles = 4; break;
        case 0x8E: addr = am_abs(n); cpu_write(n, addr, r->x); cycles = 4; break;

        case 0x84: addr = am_zp(n); cpu_write(n, addr, r->y); cycles = 3; break;
        case 0x94: addr = am_zpx(n); cpu_write(n, addr, r->y); cycles = 4; break;
        case 0x8C: addr = am_abs(n); cpu_write(n, addr, r->y); cycles = 4; break;

        case 0xAA: r->x = r->a; set_zn(n, r->x); cycles = 2; break; /* TAX */
        case 0xA8: r->y = r->a; set_zn(n, r->y); cycles = 2; break; /* TAY */
        case 0xBA: r->x = r->sp; set_zn(n, r->x); cycles = 2; break; /* TSX */
        case 0x8A: r->a = r->x; set_zn(n, r->a); cycles = 2; break; /* TXA */
        case 0x9A: r->sp = r->x; cycles = 2; break; /* TXS */
        case 0x98: r->a = r->y; set_zn(n, r->a); cycles = 2; break; /* TYA */

        case 0x00: /* BRK */
            fetch8(n);
            push16(n, r->pc);
            push8(n, (uint8_t)(r->p | F_B | F_U));
            r->p = (uint8_t)(r->p | F_I);
            {
                uint8_t lo = cpu_read(n, 0xFFFE);
                uint8_t hi = cpu_read(n, 0xFFFF);
                r->pc = (uint16_t)((hi << 8) | lo);
            }
            cycles = 7;
            break;

        default:
            /* Unofficial opcodes. SMB and many games execute multi-byte
               NOPs; treating them as 1-byte implied desyncs PC. */
            switch (op) {
                /* 1-byte NOP */
                case 0x1A:
                case 0x3A:
                case 0x5A:
                case 0x7A:
                case 0xDA:
                case 0xFA:
                    cycles = 2;
                    break;
                /* 2-byte NOP immediate */
                case 0x80:
                case 0x82:
                case 0x89:
                case 0xC2:
                case 0xE2:
                    fetch8(n);
                    cycles = 2;
                    break;
                /* 2-byte NOP zp */
                case 0x04:
                case 0x44:
                case 0x64:
                    am_zp(n);
                    cycles = 3;
                    break;
                /* 2-byte NOP zp,X */
                case 0x14:
                case 0x34:
                case 0x54:
                case 0x74:
                case 0xD4:
                case 0xF4:
                    am_zpx(n);
                    cycles = 4;
                    break;
                /* 3-byte NOP abs */
                case 0x0C:
                    am_abs(n);
                    cycles = 4;
                    break;
                /* 3-byte NOP abs,X */
                case 0x1C:
                case 0x3C:
                case 0x5C:
                case 0x7C:
                case 0xDC:
                case 0xFC:
                    am_abx(n, &pcross);
                    cycles = 4 + pcross;
                    break;
                default:
                    /* unknown — 2-cycle NOP, 1 byte */
                    cycles = 2;
                    break;
            }
            break;
    }

    c->cycles += (uint64_t)cycles;
    return cycles;
}
