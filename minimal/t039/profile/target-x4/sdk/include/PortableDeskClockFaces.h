#pragma once
/* Pure app-owned face rasterizer. No hardware, allocation, clock or sleep API.
 * Stable face IDs are defined once in PortableDeskClock.h. */
#include "PortableDeskClock.h"
#ifdef __cplusplus
extern "C" {
#endif
#define PORTABLE_DESK_MIN_DIMENSION 240
#define PORTABLE_DESK_MAX_DIMENSION 2048

typedef struct {
    void *context;
    int width, height;
    /* All calls are positive-area rectangles entirely inside the surface.
     * Return false to stop delivery immediately; caller must discard that frame.
     * The callback/context remain owned by the caller and are never retained. */
    bool (*fill_rect)(void *context, int x, int y, int width, int height, bool black);
} portable_desk_canvas;

/* Clear to white, then draw one face. The caller adds date and AM/PM text
 * afterwards, and owns orientation, qualified local time and present completion.
 * Unknown face IDs use Segments, as in Reader. Invalid time (including an
 * out-of-range hour/minute) displays --:-- for every face. No implicit modulo
 * repair. Canvas errors return false without any callback. On callback failure
 * returns false with a partial, non-presentable frame. Otherwise returns true.
 * Dimensions are independently bounded to [240,2048]. Rendering has no state:
 * identical inputs rebuild identical old/new frames after deep-sleep RAM loss. */
bool portable_desk_draw_face(const portable_desk_canvas *canvas, unsigned face,
                             int hour24, int minute, bool use12_hour, bool valid);
#ifdef __cplusplus
}
#endif
