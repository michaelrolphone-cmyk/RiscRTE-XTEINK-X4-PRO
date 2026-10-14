#ifndef UTILITIES_ALARM_OUTPUT_V1_H
#define UTILITIES_ALARM_OUTPUT_V1_H
/* Consumer-only copies of twatch_caps.h haptic.effect@1 and audio.output@1.
 * Source RiscRTE-T-Watch-S3 9cfa2aa4d572a290b41cf040a27cbec9d78bb35c.
 * This does not promote board-local declarations into a Runtime-owned ABI.
 * Integration REQUIRES independently verified partial-start and safe-close
 * backend semantics; a successful PCM enqueue is not proof of wire drain. */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
typedef struct {
    uint32_t api_version, struct_size;
    void *context;
    bool (*effect)(void *context, uint8_t effect_id);
    bool (*stop)(void *context);
} twatch_haptic_api_v1;
typedef struct {
    uint32_t api_version, struct_size;
    void *context;
    bool (*open)(void *context, uint32_t rate_hz, uint8_t channels);
    bool (*write)(void *context, const int16_t *pcm, size_t frames);
    bool (*set_gain)(void *context, uint16_t level, uint16_t maximum);
    bool (*silence)(void *context);
    bool (*close)(void *context);
} twatch_audio_out_api_v1;
#endif
