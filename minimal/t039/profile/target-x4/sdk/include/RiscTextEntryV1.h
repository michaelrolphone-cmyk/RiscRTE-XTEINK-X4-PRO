#pragma once
/* One separately loaded System-owned plain-text service. Requests and results
 * are copied; no app buffer, callback or pointer is retained after a call.
 * Serialized grant-owner calls only. A token is valid only until clean close.
 * Apps pause their presenter before open and resume it only after close OK.
 * This revision accepts printable ASCII, without email/URL/number modes. */
#include <stdint.h>
#include <stddef.h>
#define RISC_TEXT_ENTRY_CAPABILITY "ui.text-input"
#define RISC_TEXT_ENTRY_API_V1 1u
#define RISC_TEXT_ENTRY_BYTES 72u
#define RISC_TEXT_ENTRY_LABEL 40u
enum { RISC_TEXT_ENTRY_OK=0, RISC_TEXT_ENTRY_AGAIN=1, RISC_TEXT_ENTRY_INVALID=-1,
       RISC_TEXT_ENTRY_STALE=-2, RISC_TEXT_ENTRY_BUSY=-3, RISC_TEXT_ENTRY_UNAVAILABLE=-4,
       RISC_TEXT_ENTRY_RETAINED=-9 };
enum { RISC_TEXT_ENTRY_EDITING=0, RISC_TEXT_ENTRY_ACCEPTED=1, RISC_TEXT_ENTRY_CANCELLED=2 };
enum { RISC_TEXT_ENTRY_HARDWARE=1u, RISC_TEXT_ENTRY_PRESENTING=2u };
/* Optional result reason, returned only for a negotiated request. Back/Escape
 * remain plain CANCELLED; Home keeps the copied draft text and this flag. */
#define RISC_TEXT_ENTRY_HOME_CANCEL 4u
#define RISC_TEXT_ENTRY_REQUEST_HOME_REASON 1u
/* Negotiated display-only masking. Results still copy the caller's text. */
#define RISC_TEXT_ENTRY_REQUEST_MASKED 2u
#define RISC_TEXT_ENTRY_MASKED_TAG 0x544d534bu
#define RISC_TEXT_ENTRY_MASKED_VERSION 1u
#define RISC_TEXT_ENTRY_HOME_REASON_TAG 0x54484f4du
#define RISC_TEXT_ENTRY_HOME_REASON_VERSION 1u
typedef struct {
    uint32_t api_version, struct_size, capacity, reserved;
    char label[RISC_TEXT_ENTRY_LABEL];
    char text[RISC_TEXT_ENTRY_BYTES];
} risc_text_entry_request_v1;
typedef struct {
    uint32_t struct_size, state, flags, revision;
    char text[RISC_TEXT_ENTRY_BYTES];
} risc_text_entry_state_v1;
typedef struct {
    uint32_t api_version, struct_size;
    void *context;
    int32_t (*open)(void *, const risc_text_entry_request_v1 *, uint64_t *session);
    /* Copies current state. ACCEPTED/CANCELLED remain readable until close.
     * One bounded input/presentation step; never sleeps or saves app data. */
    int32_t (*poll)(void *, uint64_t, risc_text_entry_state_v1 *);
    /* Cancels an editing session. AGAIN means keep grant/token and retry after
     * yield; RETAINED forbids further service I/O and app/host unmapping. */
    int32_t (*close)(void *, uint64_t);
} risc_text_entry_api_v1;

/* Size-safe additive capability suffix. Old request/result layouts and all
 * callbacks are unchanged; old clients send reserved=0 and receive old flags. */
typedef struct {
    risc_text_entry_api_v1 base;
    uint32_t home_reason_tag, home_reason_version;
} risc_text_entry_api_v1_home_reason;
static inline int risc_text_entry_home_reason(const risc_text_entry_api_v1 *api) {
    if(!api || api->api_version!=RISC_TEXT_ENTRY_API_V1 ||
       api->struct_size<sizeof(risc_text_entry_api_v1_home_reason))return 0;
    const risc_text_entry_api_v1_home_reason *ext=(const risc_text_entry_api_v1_home_reason *)api;
    return ext->home_reason_tag==RISC_TEXT_ENTRY_HOME_REASON_TAG &&
        ext->home_reason_version==RISC_TEXT_ENTRY_HOME_REASON_VERSION;
}

/* Masking follows the existing home-reason prefix. An older provider must
 * never receive a secret request as unmasked plain text. */
typedef struct {
    risc_text_entry_api_v1_home_reason base;
    uint32_t masked_tag, masked_version;
} risc_text_entry_api_v1_masked;
static inline int risc_text_entry_masked(const risc_text_entry_api_v1 *api) {
    if(!risc_text_entry_home_reason(api) ||
       api->struct_size<sizeof(risc_text_entry_api_v1_masked))return 0;
    const risc_text_entry_api_v1_masked *ext=(const risc_text_entry_api_v1_masked *)api;
    return ext->masked_tag==RISC_TEXT_ENTRY_MASKED_TAG &&
        ext->masked_version==RISC_TEXT_ENTRY_MASKED_VERSION;
}
