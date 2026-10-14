#pragma once
/* NOVA-7 quick actions: pure input/animation state, no runtime or storage I/O. */
#include <stdbool.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define PQA_OPEN_Q8 (240 * 256)
#define PQA_TOP_EDGE 36
#define PQA_ANIMATION_STEP_MS 8u

typedef enum {
    PQA_NONE = 0,
    PQA_BRIGHTNESS_PREVIEW = 1u << 0,
    PQA_BRIGHTNESS_COMMIT = 1u << 1,
    PQA_VOLUME_COMMIT = 1u << 2,
    PQA_SILENT = 1u << 3,
    PQA_TORCH = 1u << 4,
    PQA_WIFI = 1u << 5,
    PQA_AIRPLANE = 1u << 6,
    PQA_BLUETOOTH = 1u << 7,
    PQA_DND = 1u << 8,
    PQA_USB_TRANSFER = 1u << 9,
    PQA_CLEAN_REFRESH = 1u << 10,
    PQA_TONE_PREVIEW = 1u << 11,
    PQA_TONE_COMMIT = 1u << 12
} pqa_action;
typedef enum { PQA_PASS, PQA_RESERVED, PQA_CONSUMED, PQA_REPLAY } pqa_route;
typedef enum {
    PQA_IDLE, PQA_TOP_PENDING, PQA_PASS_THROUGH, PQA_PANEL_PENDING,
    PQA_PANEL_DRAG, PQA_BRIGHTNESS_DRAG, PQA_VOLUME_DRAG, PQA_TORCH_TAP, PQA_TONE_DRAG
} pqa_gesture;
enum { PQA_ERROR_BRIGHTNESS = 1u, PQA_ERROR_VOLUME = 2u,
       PQA_ERROR_SAVE = 4u, PQA_ERROR_WIFI = 8u, PQA_ERROR_RADIO=16u, PQA_ERROR_DND=32u, PQA_ERROR_USB=64u, PQA_ERROR_TONE=128u };

typedef struct {
    /* Controller scratch/proposed values; adapter owns persisted preferences.
     * Levels are 0..100 percent, sliders choose ten-point steps. Brightness
     * user choices have a 10% floor. Unknown values never become fake states. */
    uint8_t brightness, volume, last_nonzero_volume;
#ifdef PORTABLE_PAPER_TRANSITIONS
    uint8_t last_nonzero_brightness, applied_brightness;
    bool applied_brightness_valid;
#endif
    bool brightness_valid, volume_valid, torch;
    /* Retaining paper selects a discrete 480x800 sheet and large 2-column controls. */
    bool paper, torch_valid;
#ifdef PORTABLE_RESIDENT_SHELL_HOST
    bool audio_controls; /* false omits controls for absent sound hardware */
    bool clean_refresh_valid;
#endif
#ifdef PORTABLE_FRONTLIGHT_TONE
    uint8_t tone, applied_tone, saved_tone, action_tone;
    bool tone_controls, tone_valid, applied_tone_valid;
#endif
    bool dnd_valid, dnd_enabled;
    bool radio_controls,radios_valid,wifi_enabled,bluetooth_enabled,airplane;
    uint8_t error_flags;
    int32_t position_q8, target_q8, velocity_q8;
    pqa_gesture gesture;
    pqa_route route;
    bool neutral_gate, clock_valid;
    uint32_t pending;
    /* Snapshots for pending actions; commits dominate previews until taken.
     * action_volume applies to VOLUME_COMMIT and SILENT. */
    uint8_t action_brightness, action_volume;
    bool action_torch, action_dnd;
    uint32_t start_ms, last_ms, animation_ms, animation_remainder_ms;
    uint32_t start_id;
    int16_t start_x, start_y, last_x, last_y;
    int32_t start_position_q8, release_velocity_q8;
    uint8_t saved_brightness, saved_volume, saved_last_nonzero_volume;
    int8_t pressed_tile;
    bool handle_pressed, moved;
} pqa_state;

void pqa_init(pqa_state *s);
#ifdef PORTABLE_RESIDENT_SHELL_HOST
bool pqa_paper_tile(const pqa_state *s,unsigned tile,int *x,int *y);
/* Slider IDs: brightness=0, volume=1, tone=2. Zero means unavailable. */
int pqa_paper_slider_y(const pqa_state *s,unsigned slider);
bool pqa_paper_compact_sliders(const pqa_state *s);
#endif
/* Set externally confirmed levels when idle. It is also safe for an adapter to
 * restore rejected values directly after draining the matching action. */
void pqa_set_levels(pqa_state *s, bool brightness_valid, unsigned brightness,
                    bool volume_valid, unsigned volume);
/* valid=false means cancellation/input loss, not a release. count>1 or an ID
 * replacement cancels and gates until a valid neutral sample (count==0).
 * A closed gesture starts only with allow_open and y<36. Every other gesture
 * passes through. RESERVED is consumed temporarily. REPLAY returns false:
 * adapter must replay start_{ms,id,x,y} as a down before this sample if it held
 * it; on a top-edge tap's release this preserves the ordinary app tap.
 * Once an outside-area app contact starts it can never open the panel.
 * Input coordinates are screen pixels, even while the panel moves.
 * Pending actions remain until pqa_take_action; inspect action_* snapshots.
 */
bool pqa_input(pqa_state *s, uint32_t now_ms, bool valid, unsigned count,
               uint32_t id, int x, int y, bool allow_open);
bool pqa_animate(pqa_state *s, uint32_t now_ms);
bool pqa_visible(const pqa_state *s);
bool pqa_capture(const pqa_state *s);
uint32_t pqa_take_action(pqa_state *s);
/* Discard an in-progress slider; brightness emits PREVIEW of the saved value.
 * Close also shuts torch off (emits TORCH), preserving committed preferences.
 * Both gate contacts until a valid neutral sample. Useful for modal preemption. */
void pqa_cancel_input(pqa_state *s);
void pqa_close(pqa_state *s);
void pqa_cancel(pqa_state *s); /* immediate close, for modal preemption */

#ifdef __cplusplus
}
#endif
