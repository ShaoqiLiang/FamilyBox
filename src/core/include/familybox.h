/* FamilyBox public C API — Python only talks to these symbols.
   Frozen ABI contract (design doc doc/find/architecture-design.md §4):
   entries may be ADDED in new versions, existing signatures NEVER change.
   Bump FB_CORE_ABI_VERSION whenever the surface changes so the Python
   binding can reject stale DLLs at load time. */
#ifndef FAMILYBOX_H
#define FAMILYBOX_H

#include <stdint.h>

#ifdef __cplusplus
extern "C"
{
#endif

#ifdef _WIN32
#ifdef FAMILYBOX_CORE_BUILD
#define FB_API __declspec(dllexport)
#else
#define FB_API __declspec(dllimport)
#endif
#else
#define FB_API
#endif

/* v1: initial freeze — nes_* surface as shipped in develop260912/13.
   v2: + nes_set_timing (region-aware video timing, NTSC/PAL). */
#define FB_CORE_ABI_VERSION 2

    typedef struct Nes Nes;

    /* ABI handshake: must equal FB_CORE_ABI_VERSION of this header. */
    FB_API int32_t nes_abi_version(void);

    FB_API Nes *nes_create(void);
    FB_API void nes_destroy(Nes *nes);
    /* 0 = ok, negative = error */
    FB_API int nes_load_rom(Nes *nes, const char *path);
    FB_API void nes_reset(Nes *nes);
    /* Video timing standard: 0 = NTSC (262 lines, 60.0988 fps, 1.789773 MHz),
       1 = PAL (312 lines, 50.007 fps, 1.662607 MHz). Applies immediately;
       call before nes_reset for a clean frame boundary. */
    FB_API void nes_set_timing(Nes *nes, int region);
    FB_API void nes_set_buttons(Nes *nes, uint8_t buttons);
    /* Run one full frame. rgb: 256*240*3 bytes, may be NULL. pcm: int16 samples.
       Returns number of PCM samples written (>=0), or -1 on error. */
    FB_API int nes_run_frame(Nes *nes, uint8_t *rgb, int16_t *pcm, int max_samples);
    /* Zero-copy video: pointer to the core-internal completed frame
       (256*240*3 bytes, RGB). The view is only valid until the next
       nes_run_frame/nes_reset on this handle; copy if retaining. */
    FB_API const uint8_t *nes_video(Nes *nes);
    FB_API void nes_get_debug(Nes *nes, uint16_t *pc, uint8_t *a, uint8_t *x, uint8_t *y, uint8_t *p);
    FB_API void nes_dump_palette(Nes *n, uint8_t *out32);
    FB_API uint8_t nes_peek_ppu(Nes *n, uint16_t addr);
    FB_API uint8_t nes_get_ppuctrl(Nes *n);
    FB_API uint8_t nes_get_ppumask(Nes *n);
    FB_API uint16_t nes_get_v(Nes *n);
    FB_API uint8_t nes_get_status(Nes *n);
    FB_API void nes_dump_oam(Nes *n, uint8_t *out256);
    FB_API uint8_t nes_peek_cpu(Nes *n, uint16_t addr);
    FB_API int nes_ctrl_log(Nes *n, uint8_t *out, int max);
    FB_API void nes_get_v_samples(Nes *n, uint16_t *out4);
    FB_API uint16_t nes_get_t(Nes *n);
    FB_API int nes_get_s0_hits(Nes *n);
    FB_API void nes_reset_s0_hits(Nes *n);
    FB_API int nes_debug_enabled(void);
    FB_API int nes_get_scroll_writes(Nes *n);
    /* Copy write-log entries. Each entry: kind,u8 value,u16 addr,i16 sl,i16 cy = 8 bytes.
       Returns number of entries copied. */
    FB_API int nes_wrlog_copy(Nes *n, uint8_t *out, int max_entries);
    FB_API int nes_get_nmi_count(Nes *n);
    FB_API int nes_get_last_s0_sl(Nes *n);

#ifdef __cplusplus
}
#endif

#endif /* FAMILYBOX_H */
