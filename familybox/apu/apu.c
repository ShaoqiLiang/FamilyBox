/* APU: pulse x2, triangle, noise + frame counter + sample output */
#include "nes_internal.h"
#include <string.h>

static const int LENGTH_TABLE[32] = {10, 254, 20, 2,  40, 4,  80, 6,  160, 8,  60, 10, 14, 12, 26, 14,
                                     12, 16,  24, 18, 48, 20, 96, 22, 192, 24, 72, 26, 16, 28, 32, 30};

static const int DUTY_TABLE[4][8] = {
    {0, 1, 0, 0, 0, 0, 0, 0}, {0, 1, 1, 0, 0, 0, 0, 0}, {0, 1, 1, 1, 1, 0, 0, 0}, {1, 0, 0, 1, 1, 1, 1, 1}};

static const int TRI_TABLE[32] = {15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5,  4,  3,  2,  1,  0,
                                  0,  1,  2,  3,  4,  5,  6, 7, 8, 9, 10, 11, 12, 13, 14, 15};

static const int NOISE_PERIOD[16] = {4, 8, 16, 32, 64, 96, 128, 160, 202, 254, 380, 508, 762, 1016, 2034, 4068};

void apu_reset(Nes *n)
{
    Apu *a = &n->apu;
    memset(a, 0, sizeof(*a));
    a->noise.shift_reg = 1;
    a->sample_rate = 44100;
    a->cycles_per_sample = 1789773.0 / 44100.0;
    a->sample_timer = 0.0;
}

static void pulse_write(PulseCh *c, int reg, uint8_t v)
{
    switch (reg)
    {
    case 0:
        c->duty = (v >> 6) & 3;
        c->envelope_loop = (v & 0x20) != 0;
        c->constant_volume = (v & 0x10) != 0;
        c->volume = v & 0x0F;
        break;
    case 1:
        c->sweep_enabled = (v & 0x80) != 0;
        c->sweep_period = (v >> 4) & 7;
        c->sweep_negate = (v & 0x08) != 0;
        c->sweep_shift = v & 7;
        c->sweep_reload = 1;
        break;
    case 2:
        c->timer_period = (c->timer_period & 0x700) | v;
        break;
    case 3:
        c->timer_period = (c->timer_period & 0xFF) | ((v & 7) << 8);
        if (c->enabled)
            c->length_counter = LENGTH_TABLE[(v >> 3) & 0x1F];
        c->envelope_start = 1;
        c->duty_index = 0;
        break;
    }
}

static void pulse_quarter(PulseCh *c)
{
    if (c->envelope_start)
    {
        c->envelope_start = 0;
        c->envelope_decay = 15;
        c->envelope_divider = c->volume;
    }
    else if (c->envelope_divider > 0)
    {
        c->envelope_divider--;
    }
    else
    {
        c->envelope_divider = c->volume;
        if (c->envelope_decay > 0)
            c->envelope_decay--;
        else if (c->envelope_loop)
            c->envelope_decay = 15;
    }
}

static void pulse_half(PulseCh *c)
{
    if (!c->envelope_loop && c->length_counter > 0)
        c->length_counter--;
    if (c->sweep_divider == 0 && c->sweep_enabled && c->sweep_shift > 0 && c->timer_period >= 8)
    {
        int change = c->timer_period >> c->sweep_shift;
        if (c->sweep_negate)
            c->timer_period = c->timer_period - change;
        else
            c->timer_period = c->timer_period + change;
        /* Oversize periods mute the channel on real hardware; do not wrap. */
    }
    if (c->sweep_divider == 0 || c->sweep_reload)
    {
        c->sweep_divider = c->sweep_period;
        c->sweep_reload = 0;
    }
    else
    {
        c->sweep_divider--;
    }
}

static int pulse_out(PulseCh *c)
{
    if (!c->enabled || c->length_counter == 0)
        return 0;
    if (c->timer_period < 8 || c->timer_period > 0x7FF)
        return 0;
    int env = c->constant_volume ? c->volume : c->envelope_decay;
    return DUTY_TABLE[c->duty][c->duty_index] ? env : 0;
}

/* The waveform timers are clocked on the APU clock (CPU/2), so each timer
   step lasts (period + 1) * 2 CPU cycles. The channel state stores CPU
   cycles remaining until the next step fires. */
static void pulse_tick_timer(PulseCh *c, int cycles)
{
    int remaining = cycles;
    while (remaining > 0)
    {
        if (c->timer > remaining)
        {
            c->timer -= remaining;
            break;
        }
        remaining -= c->timer;
        c->timer = (c->timer_period + 1) * 2;
        c->duty_index = (c->duty_index + 1) & 7;
    }
}

static void tri_tick_timer(TriangleCh *t, int cycles)
{
    int remaining = cycles;
    while (remaining > 0)
    {
        if (t->timer > remaining)
        {
            t->timer -= remaining;
            break;
        }
        remaining -= t->timer;
        t->timer = (t->timer_period + 1) * 2;
        if (t->length_counter > 0 && t->linear_counter > 0)
        {
            t->sequence_index = (t->sequence_index + 1) & 31;
        }
    }
}

static void noise_tick_timer(NoiseCh *nch, int cycles)
{
    int remaining = cycles;
    while (remaining > 0)
    {
        if (nch->timer > remaining)
        {
            nch->timer -= remaining;
            break;
        }
        remaining -= nch->timer;
        nch->timer = (nch->timer_period + 1) * 2;
        int bit0 = nch->shift_reg & 1;
        int bit1 = (nch->shift_reg >> (nch->mode ? 6 : 1)) & 1;
        int fb = bit0 ^ bit1;
        nch->shift_reg = (uint16_t)((nch->shift_reg >> 1) | (fb << 14));
    }
}

static void tri_quarter(TriangleCh *t)
{
    if (t->linear_reload_flag)
        t->linear_counter = t->linear_counter_reload;
    else if (t->linear_counter > 0)
        t->linear_counter--;
    if (!t->linear_control)
        t->linear_reload_flag = 0;
}

static void tri_half(TriangleCh *t)
{
    if (!t->linear_control && t->length_counter > 0)
        t->length_counter--;
}

static int tri_out(TriangleCh *t)
{
    if (!t->enabled || t->length_counter == 0 || t->linear_counter == 0)
        return 0;
    return TRI_TABLE[t->sequence_index];
}

static void noise_quarter(NoiseCh *c)
{
    if (c->envelope_start)
    {
        c->envelope_start = 0;
        c->envelope_decay = 15;
        c->envelope_divider = c->volume;
    }
    else if (c->envelope_divider > 0)
    {
        c->envelope_divider--;
    }
    else
    {
        c->envelope_divider = c->volume;
        if (c->envelope_decay > 0)
            c->envelope_decay--;
        else if (c->envelope_loop)
            c->envelope_decay = 15;
    }
}

static void noise_half(NoiseCh *c)
{
    if (!c->envelope_loop && c->length_counter > 0)
        c->length_counter--;
}

static int noise_out(NoiseCh *c)
{
    if (!c->enabled || c->length_counter == 0)
        return 0;
    if (c->shift_reg & 1)
        return 0;
    return c->constant_volume ? c->volume : c->envelope_decay;
}

void apu_reg_write(Nes *n, uint16_t addr, uint8_t v)
{
    Apu *a = &n->apu;
    if (addr >= 0x4000 && addr <= 0x4003)
        pulse_write(&a->pulse1, addr & 3, v);
    else if (addr >= 0x4004 && addr <= 0x4007)
        pulse_write(&a->pulse2, addr & 3, v);
    else if (addr == 0x4008)
    {
        a->tri.linear_control = (v & 0x80) != 0;
        a->tri.linear_counter_reload = v & 0x7F;
    }
    else if (addr == 0x400A)
    {
        a->tri.timer_period = (a->tri.timer_period & 0x700) | v;
    }
    else if (addr == 0x400B)
    {
        a->tri.timer_period = (a->tri.timer_period & 0xFF) | ((v & 7) << 8);
        if (a->tri.enabled)
            a->tri.length_counter = LENGTH_TABLE[(v >> 3) & 0x1F];
        a->tri.linear_reload_flag = 1;
    }
    else if (addr == 0x400C)
    {
        a->noise.envelope_loop = (v & 0x20) != 0;
        a->noise.constant_volume = (v & 0x10) != 0;
        a->noise.volume = v & 0x0F;
    }
    else if (addr == 0x400E)
    {
        a->noise.mode = (v & 0x80) != 0;
        a->noise.timer_period = NOISE_PERIOD[v & 0x0F];
    }
    else if (addr == 0x400F)
    {
        if (a->noise.enabled)
            a->noise.length_counter = LENGTH_TABLE[(v >> 3) & 0x1F];
        a->noise.envelope_start = 1;
    }
    else if (addr == 0x4015)
    {
        a->pulse1.enabled = (v & 0x01) != 0;
        a->pulse2.enabled = (v & 0x02) != 0;
        a->tri.enabled = (v & 0x04) != 0;
        a->noise.enabled = (v & 0x08) != 0;
        if (!(v & 0x01))
            a->pulse1.length_counter = 0;
        if (!(v & 0x02))
            a->pulse2.length_counter = 0;
        if (!(v & 0x04))
            a->tri.length_counter = 0;
        if (!(v & 0x08))
            a->noise.length_counter = 0;
    }
    else if (addr == 0x4017)
    {
        a->frame_mode = (v >> 7) & 1;
        a->irq_inhibit = (v & 0x40) != 0;
        a->frame_counter = 0;
        a->frame_step = 0;
    }
}

uint8_t apu_reg_read(Nes *n, uint16_t addr)
{
    if (addr != 0x4015)
        return 0;
    Apu *a = &n->apu;
    uint8_t v = 0;
    if (a->pulse1.length_counter > 0)
        v |= 0x01;
    if (a->pulse2.length_counter > 0)
        v |= 0x02;
    if (a->tri.length_counter > 0)
        v |= 0x04;
    if (a->noise.length_counter > 0)
        v |= 0x08;
    return v;
}

static float mix_sample(int p1, int p2, int t, int n)
{
    float pulse_out = 0.0f;
    if (p1 + p2 > 0)
    {
        pulse_out = 95.88f / ((8128.0f / (p1 + p2)) + 100.0f);
    }
    float tnd_out = 0.0f;
    float tnd = t / 8227.0f + n / 12241.0f;
    if (tnd > 0.0f)
    {
        tnd_out = 159.79f / ((1.0f / tnd) + 100.0f);
    }
    return pulse_out + tnd_out;
}

static void frame_quarter(Apu *a)
{
    pulse_quarter(&a->pulse1);
    pulse_quarter(&a->pulse2);
    tri_quarter(&a->tri);
    noise_quarter(&a->noise);
}

static void frame_half(Apu *a)
{
    pulse_half(&a->pulse1);
    pulse_half(&a->pulse2);
    tri_half(&a->tri);
    noise_half(&a->noise);
}

void apu_tick(Nes *n, int cpu_cycles, int16_t *pcm, int max_samples, int *out_count)
{
    Apu *a = &n->apu;
    *out_count = 0;

    a->frame_counter += cpu_cycles;
    int *steps4 = (int[]){7457, 14913, 22371, 29829};
    int *steps5 = (int[]){7457, 14913, 22371, 29829, 37281};
    int *steps = a->frame_mode ? steps5 : steps4;
    int max_steps = a->frame_mode ? 5 : 4;

    while (a->frame_step < max_steps && a->frame_counter >= steps[a->frame_step])
    {
        int half = (a->frame_mode == 0 && (a->frame_step == 1 || a->frame_step == 3)) ||
                   (a->frame_mode == 1 && (a->frame_step == 0 || a->frame_step == 2));
        frame_quarter(a);
        if (half)
            frame_half(a);
        a->frame_step++;
        if (a->frame_step >= max_steps)
        {
            a->frame_counter = 0;
            a->frame_step = 0;
        }
    }

    pulse_tick_timer(&a->pulse1, cpu_cycles);
    pulse_tick_timer(&a->pulse2, cpu_cycles);
    tri_tick_timer(&a->tri, cpu_cycles);
    noise_tick_timer(&a->noise, cpu_cycles);

    /* Produce ALL samples owed for these cycles */
    a->sample_timer += cpu_cycles;
    while (a->sample_timer >= a->cycles_per_sample)
    {
        a->sample_timer -= a->cycles_per_sample;
        if (!pcm || *out_count >= max_samples)
        {
            /* drop if no buffer space, but keep timer accurate */
            continue;
        }
        int p1 = pulse_out(&a->pulse1);
        int p2 = pulse_out(&a->pulse2);
        int t = tri_out(&a->tri);
        int nz = noise_out(&a->noise);
        int v = 0;
        if (p1 || p2 || t || nz)
        {
            float s = mix_sample(p1, p2, t, nz);
            float bipolar = s * 2.0f - 0.12f;
            v = (int)(bipolar * 28000.0f);
            if (v > 32767)
                v = 32767;
            if (v < -32768)
                v = -32768;
        }
        pcm[(*out_count)++] = (int16_t)v;
    }
}
