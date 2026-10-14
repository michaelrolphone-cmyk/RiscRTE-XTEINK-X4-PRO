#pragma once
/* Ordinary cooperative provider, never a Runtime policy or background task.
 * All output is copied. Input record bytes are consumed before return; no app
 * memory, storage API or callback is retained. Canonical records belong to
 * their source apps. Optional suffixes import temporal/neural records. */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#define CONTEXTS_SERVICE_CAPABILITY "contexts.service"
#define CONTEXTS_AUDIO 1u
#define CONTEXTS_RADIO 2u
#define CONTEXTS_ALL 3u
#define CONTEXTS_NAME_SIZE 17u
#define CONTEXTS_SLOTS 8u
enum { CONTEXTS_OFF, CONTEXTS_LOADING, CONTEXTS_PAUSED, CONTEXTS_LIVE,
       CONTEXTS_UNAVAILABLE, CONTEXTS_RETAINED };
enum { CONTEXTS_MODEL_EMPTY, CONTEXTS_MODEL_REQUESTED, CONTEXTS_MODEL_LOADING,
       CONTEXTS_MODEL_READY, CONTEXTS_MODEL_FAILED, CONTEXTS_MODEL_UNAVAILABLE };
enum { CONTEXTS_RECORD_PREFERENCES=1, CONTEXTS_RECORD_SIGNATURE=2,
       CONTEXTS_RECORD_TEMPORAL_BANK=3, CONTEXTS_RECORD_NEURAL=4 };
enum { CONTEXTS_EXPORT_OK=0, CONTEXTS_EXPORT_STORAGE=1,
       CONTEXTS_EXPORT_INVALID=2, CONTEXTS_EXPORT_UNSUPPORTED=3 };
enum { CONTEXTS_PRESET_NONE, CONTEXTS_PRESET_CLAIMED,
       CONTEXTS_PRESET_APPLIED, CONTEXTS_PRESET_PARTIAL };
enum { CONTEXTS_IMPORT_NOT_REQUESTED, CONTEXTS_IMPORT_MISSING,
       CONTEXTS_IMPORT_READY, CONTEXTS_IMPORT_FAILED, CONTEXTS_IMPORT_UNAVAILABLE };
enum { CONTEXTS_IMPORT_INVALID=-100, CONTEXTS_IMPORT_INCOMPLETE=-101,
       CONTEXTS_IMPORT_UNSUPPORTED=-102, CONTEXTS_IMPORT_STALE=-103 };
enum { CONTEXTS_EVENT_NONE, CONTEXTS_EVENT_SIGNATURE,
       CONTEXTS_EVENT_TEMPORAL, CONTEXTS_EVENT_NEURAL };
typedef struct {
    uint32_t struct_size,source,temporal_state,neural_state,temporal_generation;
    int32_t bank_error[2],neural_error;
    uint32_t bank_size[2],positive_examples,negative_examples;
    uint32_t event_engine,event_age_ms,match_work_units,missed_events;
    bool match_pending;
} contexts_model_details_v1;
typedef struct {
    uint32_t struct_size;
    bool enabled,awake,audio_allowed,radio_allowed;
    /* Desired source mask. A zero mask observes nothing. Callers must pause
     * before foreground capture/playback, alarm output, flash work or sleep.
     * radio_allowed additionally confirms current radio/BLE custody policy. */
    uint32_t sources;
} contexts_policy_v1;
typedef struct {
    uint32_t source,model_state,model_generation,model_error;
    uint32_t room_entry,preset_entry;
    uint32_t samples,age_ms;
    int32_t capture_error;
    int32_t room_slot,event_slot;
    uint32_t room_confidence,event_confidence;
    char room_name[CONTEXTS_NAME_SIZE],event_name[CONTEXTS_NAME_SIZE];
    bool current,room_valid,room_ambiguous,event_valid,event_ambiguous;
    bool signatures_ready,temporal_ready,neural_ready;
    /* Age UINT32_MAX means no observation in this awake capture session.
     * room_valid excludes ambiguous/held/verifying tracker states. */
} contexts_source_status_v1;
typedef struct {
    uint32_t struct_size,state,export_pending,export_active;
    bool cleanup_pending;
    contexts_source_status_v1 audio,radio;
    uint32_t preset_source,preset_generation,preset_result;
    int32_t preset_slot;
} contexts_status_v1;
typedef struct {
    uint32_t source,slot,kind;
    char name[CONTEXTS_NAME_SIZE];
} contexts_label_v1;
typedef struct {
    uint32_t api_version,struct_size;
    void *context;
    bool (*step)(void *,const contexts_policy_v1 *);
    bool (*pause)(void *);
    bool (*status)(void *,contexts_status_v1 *);
    /* Profile-absent sources report MODEL_UNAVAILABLE and never queue an owner.
     * A known mixed mask is intersected with this provider's real sources;
     * unsupported-only or unknown-bit export requests fail without side effects.
     * Explicit retry only: failed sources never requeue themselves. Parent
     * launches each requested owner once through ordinary app handoff. */
    bool (*request_export)(void *,uint32_t sources);
    bool (*begin_export)(void *,uint32_t source);
    bool (*export_record)(void *,uint32_t source,uint32_t kind,uint32_t index,
                          const void *bytes,uint32_t size);
    bool (*finish_export)(void *,uint32_t source,uint32_t result);
    /* Returns 1 for a copied saved slot (including kind=0), 0 at end, -1
     * when this source is not ready. No observation is implied. */
    int32_t (*label)(void *,uint32_t source,uint32_t slot,contexts_label_v1 *);
    /* Consume before the first settings write. The same identity remains
     * consumed through pause, unknown observations and failed/partial writes.
     * Source-local room_entry advances on every distinct confirmed room,
     * including rooms without presets. preset_entry records its consumed edge.
     * A changed model or a different confirmed room permits another claim. */
    bool (*claim_preset)(void *,uint32_t source,uint32_t slot,const char *name,
                         uint32_t model_generation);
    bool (*preset_result)(void *,uint32_t source,uint32_t model_generation,
                          uint32_t result);
    /* Capture-only foreground checkpoint: service an already-owned permitted
     * RX, never open/configure, touch RF/storage, export or apply presets.
     * Call within 16 ms while drawing/servicing input. Complete 256-frame
     * quanta only; the native two-buffer queue has a 32 ms deadline. False
     * latches cleanup failure before any later foreground provider I/O.
     * An RF-only profile keeps this required method: no I/O and true while
     * healthy, false while any source retains cleanup custody. */
    bool (*capture_audio)(void *);
    /* Optional copied import error; no owner API/pointer is retained. For
     * temporal/neural export_record, NULL/0 means confirmed file absence.
     * Rejected records retain their format/identity error in model_details.
     * Storage RETAINED forbids calling this or finish_export in that invocation. */
    bool (*export_model_error)(void *,uint32_t source,uint32_t kind,uint32_t index,int32_t error);
    bool (*model_details)(void *,uint32_t source,contexts_model_details_v1 *);
} contexts_service_v1;
#define CONTEXTS_SERVICE_V1_SIZE (offsetof(contexts_service_v1,capture_audio)+sizeof(((contexts_service_v1*)0)->capture_audio))
#define CONTEXTS_MODEL_IMPORT_V1_SIZE (offsetof(contexts_service_v1,export_model_error)+sizeof(((contexts_service_v1*)0)->export_model_error))
#define CONTEXTS_MODEL_DETAILS_V1_SIZE (offsetof(contexts_service_v1,model_details)+sizeof(((contexts_service_v1*)0)->model_details))
