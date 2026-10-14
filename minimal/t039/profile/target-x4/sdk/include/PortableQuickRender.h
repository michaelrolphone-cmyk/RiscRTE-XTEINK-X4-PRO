#pragma once
#include "PortableQuickActions.h"
#include "RiscDisplayOutputV1.h"
#ifdef __cplusplus
extern "C" {
#endif
/* Overlay on a fresh complete app image every frame. No retained pixels.
 * 240x240 RGB565 little endian only. Tight and padded/unaligned surfaces work;
 * active rows need stride>=480 and size>=(239*stride+480), with overflow checks.
 * A valid closed controller is a no-op. Time is a bounded caller-owned label
 * (up to eight ASCII characters); NULL shows --:--. Battery 0 is valid.
 * Panels move in Q8 and have the source's 22px bottom fade; compositing uses
 * one 480-byte scanline, not a second full-frame buffer. */
bool pqa_render(risc_display_surface_v1 *surface, const pqa_state *state,
                const char *time_label, bool battery_valid, uint8_t battery_percent);
#ifdef PORTABLE_RASTER_SNAPSHOT
/* Private opt-in replay helper. Coordinates and validation still describe the
 * full surface; only the requested physical rows are modified. */
bool pqa_render_rows(risc_display_surface_v1 *surface, const pqa_state *state,
                     const char *time_label, bool battery_valid, uint8_t battery_percent,
                     unsigned first_row, unsigned row_count);
#endif
/* Same licensed masks for the capability-selected paper client. The callback
 * accepts logical pixels; no allocation or provider access occurs here. */
void pqa_paper_icon(unsigned index,int x,int y,int size,bool black,
                    void (*pixel)(int,int,uint32_t,unsigned));
#ifdef __cplusplus
}
#endif
