#ifndef UTILITIES_ALARM_VOLUME_H
#define UTILITIES_ALARM_VOLUME_H
#include <stdbool.h>
#include <stdint.h>
/* Shared alarm preference. Missing means50%; callers distinguish missing from
 * malformed/unreadable and never write the default implicitly. Zero is mute.
 * Percentage is linear digital PCM gain, not measured acoustic loudness. */
#define ALARM_VOLUME_KEY "alarm_volume"
#define ALARM_VOLUME_DEFAULT 50u
#define ALARM_VOLUME_MAX 100u
#define ALARM_VOLUME_PCM_PEAK 32767
static inline bool alarm_volume_decode(const uint8_t* bytes,uint32_t size,unsigned* out){
 if(!bytes||!out||size!=1||bytes[0]>ALARM_VOLUME_MAX)return false;
 *out=bytes[0];return true;
}
#endif
