#pragma once
#include <stdbool.h>
/* Explicit application-local lifecycle hooks, not Runtime exports or a new
 * audio provider. The application alone owns its audio grant/stream. Stop is
 * idempotent, closes only its own stream, and never starts/resumes playback or
 * capture. A false result means retain the invocation with no normal I/O.
 * A healthy stream may coexist with ordinary service storage only on a Runtime
 * that preserves the distinction between active and failed/closing I2S. */
bool portable_audio_suspend(void);
bool portable_audio_services_safe(void);
#ifdef PORTABLE_AUDIO_CONTINUOUS_CAPTURE
/* App-local opt-in: active capture suppresses touch-inactivity sleep. */
bool portable_audio_capture_active(void);
/* Resume only an already requested capture after temporary alarm suspension.
 * Called after the alarm path is settled; explicit stop/exit clears intent. */
void portable_audio_capture_resume(void);
#endif
