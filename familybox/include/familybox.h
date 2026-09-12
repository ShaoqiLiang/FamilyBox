/* FamilyBox public C API — Python only talks to these symbols. */
#ifndef FAMILYBOX_H
#define FAMILYBOX_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
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

typedef struct Nes Nes;

FB_API Nes* nes_create(void);
FB_API void nes_destroy(Nes* nes);
/* 0 = ok, negative = error */
FB_API int nes_load_rom(Nes* nes, const char* path);
FB_API void nes_reset(Nes* nes);
FB_API void nes_set_buttons(Nes* nes, uint8_t buttons);
/* Run one full frame. rgb: 256*240*3 bytes. pcm: int16 samples.
   Returns number of PCM samples written (>=0), or -1 on error. */
FB_API int nes_run_frame(Nes* nes, uint8_t* rgb, int16_t* pcm, int max_samples);
FB_API void nes_get_debug(Nes* nes, uint16_t* pc, uint8_t* a, uint8_t* x,
                          uint8_t* y, uint8_t* p);
FB_API void nes_dump_palette(Nes* n, uint8_t* out32);
FB_API uint8_t nes_peek_ppu(Nes* n, uint16_t addr);
FB_API uint8_t nes_get_ppuctrl(Nes* n);
FB_API uint8_t nes_get_ppumask(Nes* n);
FB_API uint16_t nes_get_v(Nes* n);
FB_API uint8_t nes_get_status(Nes* n);
FB_API void nes_dump_oam(Nes* n, uint8_t* out256);
FB_API uint8_t nes_peek_cpu(Nes* n, uint16_t addr);
FB_API int nes_ctrl_log(Nes* n, uint8_t* out, int max);
FB_API void nes_get_v_samples(Nes* n, uint16_t* out4);
FB_API uint16_t nes_get_t(Nes* n);
FB_API int nes_get_s0_hits(Nes* n);
FB_API void nes_reset_s0_hits(Nes* n);
FB_API int nes_debug_enabled(void);
FB_API int nes_get_scroll_writes(Nes* n);
/* Copy write-log entries. Each entry: kind,u8 value,u16 addr,i16 sl,i16 cy = 8 bytes.
   Returns number of entries copied. */
FB_API int nes_wrlog_copy(Nes* n, uint8_t* out, int max_entries);
FB_API int nes_get_nmi_count(Nes* n);
FB_API int nes_get_last_s0_sl(Nes* n);

#ifdef __cplusplus
}
#endif

#endif /* FAMILYBOX_H */
