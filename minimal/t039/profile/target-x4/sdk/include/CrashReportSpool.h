#ifndef CRASH_REPORT_SPOOL_H
#define CRASH_REPORT_SPOOL_H

#include "RiscAppDataV1.h"
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

/* Pure consumer of one ordinary app-data file. The owner supplies this fixed
 * state (prefer static storage), a live API, and copied report bytes. Calls
 * are serialized by the owner; views must not outlive their snapshot. No runtime
 * calls, SD access, evidence acknowledgements, allocation, or automatic retry.
 * init is for a new lifecycle only; RETAINED forbids all further storage I/O,
 * teardown and sleep until the runtime has explicitly restarted.
 *
 * File v1, all integers little-endian, no serialized C structs or padding:
 *   0: magic[8] "CRSHSPL\0", 8: u16 version, 10: u16 header size,
 *  12: u32 total size, 16: u32 count, 20: u32 saturating dropped count,
 *  24: last dropped SHA256[32], 56: u32 boot, 60: u32 sequence,
 *  64: reserved zero[12], 76: u32 IEEE CRC32 (this field treated as zero).
 * Each entry is SHA256[32], u32 boot, u32 sequence, u32 text size,
 * u32 reserved zero, then exactly text size UTF-8 bytes (no NUL or padding).
 * The CRC covers the complete header and entries. Empty queues stay as valid
 * files so historical overflow diagnostics survive draining and restarting.
 *
 * The logical report key is the full firmware hash, captured boot/sequence,
 * AND exact text bytes. Boot/sequence may recur after cold boot, and recovery
 * reset metadata may differ when pending evidence is reread on another boot.
 * Same-identity/different-text reports remain distinct pending entries; only
 * an exact identity AND byte match deduplicates. When full, the
 * first seven oldest pending entries stay, entry eight becomes the newest,
 * and the displaced identity is recorded with a saturating dropped count.
 * COMMITTED proves only the requested report, not an evicted report, persists.
 */
#define CRASH_REPORT_SPOOL_FILE "crash-spool.bin"
#define CRASH_REPORT_SPOOL_MAX_REPORTS 8u
#define CRASH_REPORT_SPOOL_TEXT_MAX 4096u
#define CRASH_REPORT_SPOOL_HEADER_SIZE 80u
#define CRASH_REPORT_SPOOL_ENTRY_HEADER_SIZE 48u
#define CRASH_REPORT_SPOOL_FILE_MAX (CRASH_REPORT_SPOOL_HEADER_SIZE + \
    CRASH_REPORT_SPOOL_MAX_REPORTS * (CRASH_REPORT_SPOOL_ENTRY_HEADER_SIZE + CRASH_REPORT_SPOOL_TEXT_MAX))
#if CRASH_REPORT_SPOOL_FILE_MAX > RISC_APP_DATA_FILE_MAX
#error Crash report spool exceeds the AppData file bound
#endif

typedef enum {
    CRASH_REPORT_SPOOL_OK = 0,
    CRASH_REPORT_SPOOL_COMMITTED = 1,
    CRASH_REPORT_SPOOL_REMOVED = 2,
    CRASH_REPORT_SPOOL_RETRY = -1,
    CRASH_REPORT_SPOOL_CORRUPT = -2,
    CRASH_REPORT_SPOOL_COLLISION = -3, /* Legacy value; text variants are valid. */
    CRASH_REPORT_SPOOL_INVALID = -4,
    CRASH_REPORT_SPOOL_RETAINED = -5,
    CRASH_REPORT_SPOOL_UNSAFE = -6
} crash_report_spool_result;

typedef struct {
    uint8_t firmware_sha256[32];
    uint32_t captured_boot;
    uint32_t captured_sequence;
} crash_report_spool_identity;

typedef struct {
    crash_report_spool_identity identity;
    const char *text;
    uint32_t text_size;
} crash_report_spool_view;

typedef struct {
    const risc_app_data_v1 *api;
    uint64_t revision;
    uint32_t size;
    /* count/drop diagnostics and peek views are usable only while loaded.
     * App-data errors invalidate the snapshot; an uncommitted stage is never
     * exposed as a persisted report. No API callback may outlive its owner. */
    uint32_t count;
    uint32_t dropped_count;
    crash_report_spool_identity last_dropped_identity;
    int32_t last_app_data_error;
    bool loaded;
    bool present;
    bool ever_present;
    bool retained;
    uint32_t offsets[CRASH_REPORT_SPOOL_MAX_REPORTS];
    uint8_t bytes[CRASH_REPORT_SPOOL_FILE_MAX];
    /* Preserve caller input across reload, including input from peek(). */
    uint8_t operation_text[CRASH_REPORT_SPOOL_TEXT_MAX];
} crash_report_spool;

static inline uint16_t crash_report_spool_u16(const uint8_t *p) {
    return (uint16_t)((uint16_t)p[0] | (uint16_t)((uint16_t)p[1] << 8));
}
static inline uint32_t crash_report_spool_u32(const uint8_t *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}
static inline void crash_report_spool_put16(uint8_t *p, uint16_t value) {
    p[0] = (uint8_t)value; p[1] = (uint8_t)(value >> 8);
}
static inline void crash_report_spool_put32(uint8_t *p, uint32_t value) {
    p[0] = (uint8_t)value; p[1] = (uint8_t)(value >> 8);
    p[2] = (uint8_t)(value >> 16); p[3] = (uint8_t)(value >> 24);
}
static inline uint32_t crash_report_spool_crc(const uint8_t *bytes, uint32_t size) {
    uint32_t crc = UINT32_MAX;
    for (uint32_t i = 0; i < size; ++i) {
        crc ^= (i >= 76u && i < 80u) ? 0u : bytes[i];
        for (unsigned bit = 0; bit < 8; ++bit)
            crc = (crc >> 1) ^ (UINT32_C(0xedb88320) & (0u - (crc & 1u)));
    }
    return ~crc;
}
static inline bool crash_report_spool_text_valid(const uint8_t *text, uint32_t size) {
    if (!text || !size || size > CRASH_REPORT_SPOOL_TEXT_MAX) return false;
    for (uint32_t i = 0; i < size;) {
        uint32_t c = text[i++], extra;
        if (c < 0x80u) {
            if (c != 9u && c != 10u && c != 13u && (c < 32u || c == 127u)) return false;
            continue;
        }
        if (c >= 0xc2u && c <= 0xdfu) extra = 1;
        else if (c >= 0xe0u && c <= 0xefu) extra = 2;
        else if (c >= 0xf0u && c <= 0xf4u) extra = 3;
        else return false;
        if (extra > size - i) return false;
        if ((c == 0xe0u && text[i] < 0xa0u) || (c == 0xedu && text[i] >= 0xa0u) ||
            (c == 0xf0u && text[i] < 0x90u) || (c == 0xf4u && text[i] >= 0x90u)) return false;
        for (uint32_t j = 0; j < extra; ++j)
            if ((text[i++] & 0xc0u) != 0x80u) return false;
    }
    return true;
}
static inline void crash_report_spool_get_identity(const uint8_t *bytes, crash_report_spool_identity *identity) {
    memcpy(identity->firmware_sha256, bytes, 32);
    identity->captured_boot = crash_report_spool_u32(bytes + 32);
    identity->captured_sequence = crash_report_spool_u32(bytes + 36);
}
static inline void crash_report_spool_put_identity(uint8_t *bytes, const crash_report_spool_identity *identity) {
    memcpy(bytes, identity->firmware_sha256, 32);
    crash_report_spool_put32(bytes + 32, identity->captured_boot);
    crash_report_spool_put32(bytes + 36, identity->captured_sequence);
}
static inline bool crash_report_spool_same_identity(const uint8_t *bytes, const crash_report_spool_identity *identity) {
    return !memcmp(bytes, identity->firmware_sha256, 32) &&
        crash_report_spool_u32(bytes + 32) == identity->captured_boot &&
        crash_report_spool_u32(bytes + 36) == identity->captured_sequence;
}
static inline bool crash_report_spool_api_valid(const risc_app_data_v1 *api) {
    return api && api->api_version == RISC_APP_DATA_API_V1 && api->struct_size >= sizeof(*api) &&
        api->stat && api->read && api->replace;
}
static inline crash_report_spool_result crash_report_spool_init(crash_report_spool *spool, const risc_app_data_v1 *api) {
    if (!spool) return CRASH_REPORT_SPOOL_INVALID;
    memset(spool, 0, sizeof(*spool));
    spool->api = api;
    return crash_report_spool_api_valid(api) ? CRASH_REPORT_SPOOL_OK : CRASH_REPORT_SPOOL_INVALID;
}
static inline crash_report_spool_result crash_report_spool_error(crash_report_spool *spool, int32_t error) {
    spool->last_app_data_error = error;
    spool->loaded = false;
    if (error == RISC_APP_DATA_RETAINED) {
        spool->retained = true;
        return CRASH_REPORT_SPOOL_RETAINED;
    }
    switch (error) {
    case RISC_APP_DATA_NOT_FOUND:
    case RISC_APP_DATA_UNAVAILABLE:
    case RISC_APP_DATA_IO:
    case RISC_APP_DATA_NO_SPACE:
    case RISC_APP_DATA_COMMIT_UNKNOWN:
    case RISC_APP_DATA_STALE:
        return CRASH_REPORT_SPOOL_RETRY;
    default:
        return CRASH_REPORT_SPOOL_UNSAFE;
    }
}
static inline crash_report_spool_result crash_report_spool_validate(crash_report_spool *spool) {
    static const uint8_t magic[8] = {'C','R','S','H','S','P','L',0};
    const uint8_t *bytes = spool->bytes;
    spool->loaded = false;
    if (spool->size < CRASH_REPORT_SPOOL_HEADER_SIZE || spool->size > CRASH_REPORT_SPOOL_FILE_MAX ||
        memcmp(bytes, magic, sizeof(magic)) || crash_report_spool_u16(bytes + 8) != 1u ||
        crash_report_spool_u16(bytes + 10) != CRASH_REPORT_SPOOL_HEADER_SIZE ||
        crash_report_spool_u32(bytes + 12) != spool->size ||
        crash_report_spool_crc(bytes, spool->size) != crash_report_spool_u32(bytes + 76))
        return CRASH_REPORT_SPOOL_CORRUPT;
    for (unsigned i = 64; i < 76; ++i)
        if (bytes[i]) return CRASH_REPORT_SPOOL_CORRUPT;
    uint32_t count = crash_report_spool_u32(bytes + 16);
    uint32_t dropped = crash_report_spool_u32(bytes + 20);
    if (count > CRASH_REPORT_SPOOL_MAX_REPORTS) return CRASH_REPORT_SPOOL_CORRUPT;
    if (!dropped) {
        for (unsigned i = 24; i < 64; ++i)
            if (bytes[i]) return CRASH_REPORT_SPOOL_CORRUPT;
    }
    uint32_t offset = CRASH_REPORT_SPOOL_HEADER_SIZE;
    for (uint32_t i = 0; i < count; ++i) {
        if (offset > spool->size || CRASH_REPORT_SPOOL_ENTRY_HEADER_SIZE > spool->size - offset)
            return CRASH_REPORT_SPOOL_CORRUPT;
        uint32_t length = crash_report_spool_u32(bytes + offset + 40);
        if (crash_report_spool_u32(bytes + offset + 44) ||
            length > spool->size - offset - CRASH_REPORT_SPOOL_ENTRY_HEADER_SIZE ||
            !crash_report_spool_text_valid(bytes + offset + CRASH_REPORT_SPOOL_ENTRY_HEADER_SIZE, length))
            return CRASH_REPORT_SPOOL_CORRUPT;
        for (uint32_t j = 0; j < i; ++j) {
            const uint8_t *prior = bytes + spool->offsets[j];
            if (!memcmp(bytes + offset, prior, 40) && crash_report_spool_u32(prior + 40) == length &&
                !memcmp(bytes + offset + CRASH_REPORT_SPOOL_ENTRY_HEADER_SIZE,
                        prior + CRASH_REPORT_SPOOL_ENTRY_HEADER_SIZE, length))
                return CRASH_REPORT_SPOOL_CORRUPT;
        }
        spool->offsets[i] = offset;
        offset += CRASH_REPORT_SPOOL_ENTRY_HEADER_SIZE + length;
    }
    if (offset != spool->size) return CRASH_REPORT_SPOOL_CORRUPT;
    spool->count = count;
    spool->dropped_count = dropped;
    crash_report_spool_get_identity(bytes + 24, &spool->last_dropped_identity);
    spool->loaded = true;
    return CRASH_REPORT_SPOOL_OK;
}
/* One stat/read attempt. NOT_FOUND is the only path that initializes an empty
 * first queue. Corruption and IO failures never trigger replacement/defaults.
 * Disappearance after this lifecycle has seen the file is unsafe, not a new
 * queue. Tokens are reacquired for every mutation and never saved over reboot. */
static inline crash_report_spool_result crash_report_spool_reload(crash_report_spool *spool) {
    if (!spool) return CRASH_REPORT_SPOOL_INVALID;
    if (spool->retained) return CRASH_REPORT_SPOOL_RETAINED;
    spool->loaded = false;
    if (!crash_report_spool_api_valid(spool->api)) return CRASH_REPORT_SPOOL_UNSAFE;
    uint32_t size = 0, read_size = 0;
    uint64_t revision = 0, read_revision = 0;
    int32_t result = spool->api->stat(spool->api->context, CRASH_REPORT_SPOOL_FILE, &size, &revision);
    spool->last_app_data_error = result;
    if (result == RISC_APP_DATA_NOT_FOUND) {
        if (size || revision || spool->ever_present) return CRASH_REPORT_SPOOL_UNSAFE;
        memset(spool->bytes, 0, CRASH_REPORT_SPOOL_HEADER_SIZE);
        memcpy(spool->bytes, "CRSHSPL", 7);
        crash_report_spool_put16(spool->bytes + 8, 1);
        crash_report_spool_put16(spool->bytes + 10, CRASH_REPORT_SPOOL_HEADER_SIZE);
        crash_report_spool_put32(spool->bytes + 12, CRASH_REPORT_SPOOL_HEADER_SIZE);
        spool->size = CRASH_REPORT_SPOOL_HEADER_SIZE;
        crash_report_spool_put32(spool->bytes + 76, crash_report_spool_crc(spool->bytes, spool->size));
        spool->revision = 0;
        spool->present = false;
        return crash_report_spool_validate(spool);
    }
    if (result != RISC_APP_DATA_OK) return crash_report_spool_error(spool, result);
    spool->ever_present = true;
    if (!revision) return CRASH_REPORT_SPOOL_UNSAFE;
    if (size < CRASH_REPORT_SPOOL_HEADER_SIZE || size > CRASH_REPORT_SPOOL_FILE_MAX)
        return CRASH_REPORT_SPOOL_CORRUPT;
    result = spool->api->read(spool->api->context, CRASH_REPORT_SPOOL_FILE, revision,
                             spool->bytes, sizeof(spool->bytes), &read_size, &read_revision);
    spool->last_app_data_error = result;
    if (result != RISC_APP_DATA_OK) return crash_report_spool_error(spool, result);
    if (read_size != size || read_revision != revision) return CRASH_REPORT_SPOOL_UNSAFE;
    spool->size = read_size;
    spool->revision = read_revision;
    spool->present = true;
    return crash_report_spool_validate(spool);
}
/* Views expire on the next mutating call/reload. append/remove accept a view's
 * identity and bytes directly because they copy inputs before any reload. */
static inline crash_report_spool_result crash_report_spool_peek(const crash_report_spool *spool,
                                                               uint32_t index, crash_report_spool_view *view) {
    if (!spool) return CRASH_REPORT_SPOOL_INVALID;
    if (spool->retained) return CRASH_REPORT_SPOOL_RETAINED;
    if (!view) return CRASH_REPORT_SPOOL_INVALID;
    if (!spool->loaded) return CRASH_REPORT_SPOOL_RETRY;
    if (index >= spool->count) return CRASH_REPORT_SPOOL_INVALID;
    const uint8_t *entry = spool->bytes + spool->offsets[index];
    crash_report_spool_get_identity(entry, &view->identity);
    view->text_size = crash_report_spool_u32(entry + 40);
    view->text = (const char *)(entry + CRASH_REPORT_SPOOL_ENTRY_HEADER_SIZE);
    return CRASH_REPORT_SPOOL_OK;
}
/* Internal lookup: first exact identity+text match, or -1 if absent. Scan all
 * variants: matching a capture identity alone never deduplicates or removes. */
static inline int crash_report_spool_find(const crash_report_spool *spool,
                                         const crash_report_spool_identity *identity,
                                         const uint8_t *text, uint32_t text_size) {
    for (uint32_t i = 0; i < spool->count; ++i) {
        const uint8_t *entry = spool->bytes + spool->offsets[i];
        if (crash_report_spool_same_identity(entry, identity) &&
            crash_report_spool_u32(entry + 40) == text_size &&
            !memcmp(entry + CRASH_REPORT_SPOOL_ENTRY_HEADER_SIZE, text, text_size)) return (int)i;
    }
    return -1;
}
/* Only STALE and COMMIT_UNKNOWN receive one reconciliation reload. Ordinary
 * failures leave an invalid snapshot and require a later caller checkpoint.
 * The AppData OK contract already proves sync + exact destination readback. */
static inline crash_report_spool_result crash_report_spool_commit(crash_report_spool *spool,
        const crash_report_spool_identity *identity, uint32_t text_size, bool removing) {
    crash_report_spool_put32(spool->bytes + 12, spool->size);
    crash_report_spool_put32(spool->bytes + 76, crash_report_spool_crc(spool->bytes, spool->size));
    spool->loaded = false;
    int32_t result = spool->api->replace(spool->api->context, CRASH_REPORT_SPOOL_FILE,
                                        spool->revision, spool->bytes, spool->size);
    spool->last_app_data_error = result;
    if (result == RISC_APP_DATA_OK) {
        spool->present = true;
        spool->ever_present = true;
        spool->revision = 0; /* Any write invalidates all mount-session tokens. */
        crash_report_spool_result verified = crash_report_spool_validate(spool);
        if (verified != CRASH_REPORT_SPOOL_OK) return verified;
        return removing ? CRASH_REPORT_SPOOL_REMOVED : CRASH_REPORT_SPOOL_COMMITTED;
    }
    if (result != RISC_APP_DATA_STALE && result != RISC_APP_DATA_COMMIT_UNKNOWN)
        return crash_report_spool_error(spool, result);
    crash_report_spool_result reloaded = crash_report_spool_reload(spool);
    if (reloaded != CRASH_REPORT_SPOOL_OK) return reloaded;
    /* Keep the initiating ambiguity available after a successful readback. */
    spool->last_app_data_error = result;
    int found = crash_report_spool_find(spool, identity, spool->operation_text, text_size);
    if (removing) return found == -1 ? CRASH_REPORT_SPOOL_REMOVED : CRASH_REPORT_SPOOL_RETRY;
    return found >= 0 ? CRASH_REPORT_SPOOL_COMMITTED : CRASH_REPORT_SPOOL_RETRY;
}
static inline crash_report_spool_result crash_report_spool_append(crash_report_spool *spool,
        const crash_report_spool_identity *identity, const char *text, uint32_t text_size) {
    if (!spool) return CRASH_REPORT_SPOOL_INVALID;
    if (spool->retained) return CRASH_REPORT_SPOOL_RETAINED;
    if (!identity || !crash_report_spool_text_valid((const uint8_t *)text, text_size))
        return CRASH_REPORT_SPOOL_INVALID;
    crash_report_spool_identity copied_identity = *identity;
    memmove(spool->operation_text, text, text_size);
    crash_report_spool_result reloaded = crash_report_spool_reload(spool);
    if (reloaded != CRASH_REPORT_SPOOL_OK) return reloaded;
    int found = crash_report_spool_find(spool, &copied_identity, spool->operation_text, text_size);
    if (found >= 0) return CRASH_REPORT_SPOOL_COMMITTED;
    uint32_t offset = spool->size;
    if (spool->count == CRASH_REPORT_SPOOL_MAX_REPORTS) {
        offset = spool->offsets[CRASH_REPORT_SPOOL_MAX_REPORTS - 1];
        memcpy(spool->bytes + 24, spool->bytes + offset, 40);
        if (spool->dropped_count != UINT32_MAX)
            crash_report_spool_put32(spool->bytes + 20, spool->dropped_count + 1);
    } else {
        crash_report_spool_put32(spool->bytes + 16, spool->count + 1);
    }
    crash_report_spool_put_identity(spool->bytes + offset, &copied_identity);
    crash_report_spool_put32(spool->bytes + offset + 40, text_size);
    crash_report_spool_put32(spool->bytes + offset + 44, 0);
    memcpy(spool->bytes + offset + CRASH_REPORT_SPOOL_ENTRY_HEADER_SIZE, spool->operation_text, text_size);
    spool->size = offset + CRASH_REPORT_SPOOL_ENTRY_HEADER_SIZE + text_size;
    return crash_report_spool_commit(spool, &copied_identity, text_size, false);
}
/* Call only after SD persistence is proved. Exact report bytes are required
 * so a same-identity text variant never removes different evidence.
 * REMOVED means validated absence, including an already removed report. */
static inline crash_report_spool_result crash_report_spool_remove(crash_report_spool *spool,
        const crash_report_spool_identity *identity, const char *text, uint32_t text_size) {
    if (!spool) return CRASH_REPORT_SPOOL_INVALID;
    if (spool->retained) return CRASH_REPORT_SPOOL_RETAINED;
    if (!identity || !crash_report_spool_text_valid((const uint8_t *)text, text_size))
        return CRASH_REPORT_SPOOL_INVALID;
    crash_report_spool_identity copied_identity = *identity;
    memmove(spool->operation_text, text, text_size);
    crash_report_spool_result reloaded = crash_report_spool_reload(spool);
    if (reloaded != CRASH_REPORT_SPOOL_OK) return reloaded;
    int found = crash_report_spool_find(spool, &copied_identity, spool->operation_text, text_size);
    if (found == -1) return CRASH_REPORT_SPOOL_REMOVED;
    uint32_t offset = spool->offsets[(unsigned)found];
    uint32_t next = offset + CRASH_REPORT_SPOOL_ENTRY_HEADER_SIZE + text_size;
    memmove(spool->bytes + offset, spool->bytes + next, spool->size - next);
    spool->size -= CRASH_REPORT_SPOOL_ENTRY_HEADER_SIZE + text_size;
    crash_report_spool_put32(spool->bytes + 16, spool->count - 1);
    return crash_report_spool_commit(spool, &copied_identity, text_size, true);
}

#endif
