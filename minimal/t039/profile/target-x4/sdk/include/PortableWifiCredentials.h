#ifndef PORTABLE_WIFI_CREDENTIALS_H
#define PORTABLE_WIFI_CREDENTIALS_H
/* App-owned, plaintext credential storage for storage.key-value@1 namespace 6.
 * The format uses five fixed keys. Each slot has two 64-byte chunks;
 * a 32-byte selector is the ONLY authority. A save verifies the inactive slot
 * before replacing the selector. Orphan chunks are never recovered or used as
 * fallback, including when the selector is missing, corrupt, or a tombstone.
 *
 * Assumes one writer and the provider's per-key replacement semantics. CRCs
 * detect accidental corruption, not malicious modification. IO can mean that
 * a write persisted: exact readback, including after IO, confirms the outcome.
 * UNCONFIRMED means callers must reload and/or explicitly retry; they must not
 * assume either the old or proposed value survived. No encryption, secure
 * erasure, or durability across backend erase/reflash is promised.
 */
#include "RiscKeyValueV1.h"
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#define PORTABLE_WIFI_CREDENTIALS_STORE_INSTANCE 6u
#define PORTABLE_WIFI_CREDENTIALS_KEY_COUNT 5u
#define PORTABLE_WIFI_CREDENTIALS_SSID_MAX 32u
#define PORTABLE_WIFI_CREDENTIALS_PASSWORD_MAX 63u
#define PORTABLE_WIFI_CREDENTIALS_SELECTOR_KEY "wifi.commit"

typedef struct portable_wifi_credentials {
    char ssid[33];
    char password[64];
} portable_wifi_credentials;

enum {
    PORTABLE_WIFI_CREDENTIALS_LOADED = 0,
    PORTABLE_WIFI_CREDENTIALS_EMPTY = 1,
    PORTABLE_WIFI_CREDENTIALS_INVALID = 2,
    PORTABLE_WIFI_CREDENTIALS_UNAVAILABLE = 3,
    PORTABLE_WIFI_CREDENTIALS_UNCONFIRMED = 4,
    /* The tombstone is confirmed, so load cannot return the old credentials,
     * but at least one slot overwrite could not be confirmed. Physical flash
     * remanence is possible even when all logical overwrites succeed. */
    PORTABLE_WIFI_CREDENTIALS_CLEANUP_REMANENCE = 5,
    /* Temporary no-I/O deferral; keep caller-owned drafts and retry later. */
    PORTABLE_WIFI_CREDENTIALS_AGAIN = 7,
    PORTABLE_WIFI_CREDENTIALS_SAVED = PORTABLE_WIFI_CREDENTIALS_LOADED,
    PORTABLE_WIFI_CREDENTIALS_FORGOTTEN = PORTABLE_WIFI_CREDENTIALS_EMPTY
};

static inline void portable_wifi_credentials_wipe(void *data, size_t size) {
    volatile uint8_t *bytes = (volatile uint8_t *)data;
    while (size--) *bytes++ = 0;
}

static inline void portable_wifi_credentials_clear(portable_wifi_credentials *value) {
    if (value) portable_wifi_credentials_wipe(value, sizeof(*value));
}

static inline bool portable_wifi_credentials_api_valid(const risc_key_value_v1 *kv) {
    return kv && kv->api_version == RISC_KEY_VALUE_API_V1 &&
        kv->struct_size >= sizeof(*kv) && kv->get && kv->put;
}

/* SSID is 1..32 non-NUL bytes (not assumed to be ASCII). Password is empty for
 * an open network, or 8..63 printable ASCII bytes, including spaces. Neither
 * input string is scanned beyond its fixed array. Bytes after NUL are ignored
 * and are never persisted. This API never connects to a network. */
static inline bool portable_wifi_credentials_validate(const portable_wifi_credentials *value) {
    size_t ssid = 0, password = 0;
    if (!value) return false;
    while (ssid < sizeof(value->ssid) && value->ssid[ssid]) ++ssid;
    while (password < sizeof(value->password) && value->password[password]) ++password;
    if (!ssid || ssid > 32 || password > 63 || (password && password < 8)) return false;
    for (size_t i = 0; i < password; ++i) {
        unsigned char c = (unsigned char)value->password[i];
        if (c < 32 || c > 126) return false;
    }
    return true;
}

/* Encoding uses explicit little-endian bytes; no struct layout is persisted.
 * Selector: WFC1, version, live, slot, zero, generation:u64, ssid/password
 * lengths, two zeros, chunks_crc32:u32, four zeros, selector_crc32:u32.
 * Chunk: WC, version, slot*2+part, generation:u64, payload[48], crc32:u32.
 * The concatenated payload is ssid[32], password[63], zero, NUL-padded. */
static inline uint32_t portable_wifi_credentials_crc(const uint8_t *data, size_t size) {
    uint32_t crc = UINT32_C(0xffffffff);
    while (size--) {
        crc ^= *data++;
        for (unsigned i = 0; i < 8; ++i)
            crc = (crc >> 1) ^ (UINT32_C(0xedb88320) & (0u - (crc & 1u)));
    }
    return ~crc;
}

static inline uint32_t portable_wifi_credentials_u32(const uint8_t *p) {
    return (uint32_t)p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}

static inline void portable_wifi_credentials_put_u32(uint8_t *p, uint32_t value) {
    for (unsigned i = 0; i < 4; ++i) p[i] = (uint8_t)(value >> (i * 8));
}

static inline uint64_t portable_wifi_credentials_generation(const uint8_t *selector) {
    /* Constant 32-bit split shifts stay inline on the 32-bit watch target;
     * variable 64-bit shifts would import unsupported libgcc helpers. */
    return (uint64_t)portable_wifi_credentials_u32(selector + 8) |
        ((uint64_t)portable_wifi_credentials_u32(selector + 12) << 32);
}

static inline const char *portable_wifi_credentials_chunk_key(unsigned slot, unsigned part) {
    static const char *const keys[2][2] = {{"wifi.a0", "wifi.a1"}, {"wifi.b0", "wifi.b1"}};
    return keys[slot][part];
}

static inline int portable_wifi_credentials_read_blob(const risc_key_value_v1 *kv,
        const char *key, uint8_t *data, uint32_t expected) {
    uint32_t size = 0;
    int32_t rc = kv->get(kv->context, key, data, expected, &size);
    if (rc == RISC_KEY_VALUE_BUSY) return PORTABLE_WIFI_CREDENTIALS_AGAIN;
    if (rc == RISC_KEY_VALUE_NOT_FOUND) return PORTABLE_WIFI_CREDENTIALS_EMPTY;
    if (rc == RISC_KEY_VALUE_BUFFER_SMALL) return PORTABLE_WIFI_CREDENTIALS_INVALID;
    if (rc != RISC_KEY_VALUE_OK) return PORTABLE_WIFI_CREDENTIALS_UNAVAILABLE;
    return size == expected ? PORTABLE_WIFI_CREDENTIALS_LOADED : PORTABLE_WIFI_CREDENTIALS_INVALID;
}

static inline bool portable_wifi_credentials_selector_valid(const uint8_t *s) {
    if (memcmp(s, "WFC1", 4) || s[4] != 1 || s[5] > 1 || s[6] > 1 || s[7] ||
        !portable_wifi_credentials_generation(s) || s[18] || s[19] ||
        s[24] || s[25] || s[26] || s[27] ||
        portable_wifi_credentials_u32(s + 28) != portable_wifi_credentials_crc(s, 28)) return false;
    if (!s[5]) return !s[6] && !s[16] && !s[17] && !portable_wifi_credentials_u32(s + 20);
    return s[16] >= 1 && s[16] <= 32 && s[17] <= 63 && (!s[17] || s[17] >= 8);
}

static inline void portable_wifi_credentials_make_selector(uint8_t *s, uint64_t generation,
        bool live, unsigned slot, unsigned ssid, unsigned password, uint32_t crc) {
    memset(s, 0, 32); memcpy(s, "WFC1", 4); s[4] = 1; s[5] = live ? 1 : 0; s[6] = (uint8_t)slot;
    portable_wifi_credentials_put_u32(s + 8, (uint32_t)generation);
    portable_wifi_credentials_put_u32(s + 12, (uint32_t)(generation >> 32));
    s[16] = (uint8_t)ssid; s[17] = (uint8_t)password;
    portable_wifi_credentials_put_u32(s + 20, crc);
    portable_wifi_credentials_put_u32(s + 28, portable_wifi_credentials_crc(s, 28));
}

static inline int portable_wifi_credentials_write_status(const risc_key_value_v1 *kv,
        const char *key, const uint8_t *data, uint32_t size) {
    uint8_t check[64] = {0};
    /* Never infer persistence from a failed return code, or trust OK alone. */
    int rc=kv->put(kv->context, key, data, size);
    if(rc==RISC_KEY_VALUE_BUSY)return PORTABLE_WIFI_CREDENTIALS_AGAIN;
    bool same = portable_wifi_credentials_read_blob(kv, key, check, size) ==
        PORTABLE_WIFI_CREDENTIALS_LOADED && !memcmp(check, data, size);
    portable_wifi_credentials_wipe(check, sizeof(check));
    return same?PORTABLE_WIFI_CREDENTIALS_LOADED:PORTABLE_WIFI_CREDENTIALS_UNCONFIRMED;
}
static inline bool portable_wifi_credentials_write_verify(const risc_key_value_v1 *kv,
        const char *key,const uint8_t *data,uint32_t size) {
    return portable_wifi_credentials_write_status(kv,key,data,size)==PORTABLE_WIFI_CREDENTIALS_LOADED;
}

/* EMPTY covers a missing selector or a valid forget tombstone. Missing or
 * corrupt selected chunks are INVALID. Read failures are UNAVAILABLE and a
 * changed selector during the read is UNCONFIRMED. Every non-LOADED result
 * clears out completely. Unselected chunks are intentionally never consulted. */
static inline int portable_wifi_credentials_load(const risc_key_value_v1 *kv,
        portable_wifi_credentials *out) {
    uint8_t selector[32] = {0}, check[32] = {0}, chunks[128] = {0}, payload[96] = {0};
    int result = PORTABLE_WIFI_CREDENTIALS_INVALID;
    if (!out) goto finish;
    portable_wifi_credentials_clear(out);
    if (!portable_wifi_credentials_api_valid(kv)) { result = PORTABLE_WIFI_CREDENTIALS_UNAVAILABLE; goto finish; }
    result = portable_wifi_credentials_read_blob(kv, PORTABLE_WIFI_CREDENTIALS_SELECTOR_KEY, selector, 32);
    if (result != PORTABLE_WIFI_CREDENTIALS_LOADED) goto finish;
    if (!portable_wifi_credentials_selector_valid(selector)) { result = PORTABLE_WIFI_CREDENTIALS_INVALID; goto finish; }
    if (!selector[5]) { result = PORTABLE_WIFI_CREDENTIALS_EMPTY; goto finish; }
    for (unsigned part = 0; part < 2; ++part) {
        uint8_t *chunk = chunks + 64 * part;
        result = portable_wifi_credentials_read_blob(kv,
            portable_wifi_credentials_chunk_key(selector[6], part), chunk, 64);
        if (result == PORTABLE_WIFI_CREDENTIALS_EMPTY) result = PORTABLE_WIFI_CREDENTIALS_INVALID;
        if (result != PORTABLE_WIFI_CREDENTIALS_LOADED) goto finish;
        if (memcmp(chunk, "WC", 2) || chunk[2] != 1 || chunk[3] != selector[6] * 2u + part ||
            memcmp(chunk + 4, selector + 8, 8) ||
            portable_wifi_credentials_u32(chunk + 60) != portable_wifi_credentials_crc(chunk, 60)) {
            result = PORTABLE_WIFI_CREDENTIALS_INVALID; goto finish;
        }
        memcpy(payload + part * 48, chunk + 12, 48);
    }
    if (portable_wifi_credentials_u32(selector + 20) != portable_wifi_credentials_crc(chunks, 128)) {
        result = PORTABLE_WIFI_CREDENTIALS_INVALID; goto finish;
    }
    for (unsigned i = 0; i < 96; ++i) {
        bool ssid = i < selector[16];
        bool password = i >= 32 && i < 32u + selector[17];
        if ((ssid && !payload[i]) || (password && (payload[i] < 32 || payload[i] > 126)) ||
            (!ssid && !password && payload[i])) { result = PORTABLE_WIFI_CREDENTIALS_INVALID; goto finish; }
    }
    result = portable_wifi_credentials_read_blob(kv, PORTABLE_WIFI_CREDENTIALS_SELECTOR_KEY, check, 32);
    if (result == PORTABLE_WIFI_CREDENTIALS_AGAIN) goto finish;
    if (result != PORTABLE_WIFI_CREDENTIALS_LOADED || memcmp(selector, check, 32)) {
        result = PORTABLE_WIFI_CREDENTIALS_UNCONFIRMED; goto finish;
    }
    memcpy(out->ssid, payload, selector[16]); memcpy(out->password, payload + 32, selector[17]);
    result = PORTABLE_WIFI_CREDENTIALS_LOADED;
finish:
    portable_wifi_credentials_wipe(selector, sizeof(selector));
    portable_wifi_credentials_wipe(check, sizeof(check));
    portable_wifi_credentials_wipe(chunks, sizeof(chunks));
    portable_wifi_credentials_wipe(payload, sizeof(payload));
    return result;
}

/* Only explicit Save calls persist drafts. A corrupt selector can be replaced
 * by an explicit Save; an unreadable selector cannot. Before commit, no write
 * touches the previously selected slot. A failed intermediate write returns
 * UNCONFIRMED; Save is safely retryable after any interruption. */
static inline int portable_wifi_credentials_save(const risc_key_value_v1 *kv,
        const portable_wifi_credentials *draft) {
    uint8_t selector[32] = {0}, chunks[128] = {0}, payload[96] = {0};
    portable_wifi_credentials actual;
    uint64_t generation = 1;
    unsigned slot = 0, ssid = 0, password = 0;
    int result = PORTABLE_WIFI_CREDENTIALS_INVALID;
    portable_wifi_credentials_clear(&actual);
    if (!portable_wifi_credentials_validate(draft)) goto finish;
    if (!portable_wifi_credentials_api_valid(kv)) { result = PORTABLE_WIFI_CREDENTIALS_UNAVAILABLE; goto finish; }
    /* Snapshot before provider callbacks: later UI edits must not mix versions
     * of the supplied draft or turn a previously validated string unbounded. */
    while (ssid < 32 && draft->ssid[ssid]) ++ssid;
    while (password < 63 && draft->password[password]) ++password;
    memcpy(payload, draft->ssid, ssid); memcpy(payload + 32, draft->password, password);
    result = portable_wifi_credentials_read_blob(kv, PORTABLE_WIFI_CREDENTIALS_SELECTOR_KEY, selector, 32);
    if (result == PORTABLE_WIFI_CREDENTIALS_UNAVAILABLE || result == PORTABLE_WIFI_CREDENTIALS_AGAIN) goto finish;
    if (result == PORTABLE_WIFI_CREDENTIALS_LOADED && portable_wifi_credentials_selector_valid(selector)) {
        generation = portable_wifi_credentials_generation(selector) + 1;
        if (!generation) generation = 1;
        if (selector[5]) slot = selector[6] ^ 1u;
    }
    for (unsigned part = 0; part < 2; ++part) {
        uint8_t *chunk = chunks + part * 64;
        memcpy(chunk, "WC", 2); chunk[2] = 1; chunk[3] = (uint8_t)(slot * 2 + part);
        portable_wifi_credentials_put_u32(chunk + 4, (uint32_t)generation);
        portable_wifi_credentials_put_u32(chunk + 8, (uint32_t)(generation >> 32));
        memcpy(chunk + 12, payload + part * 48, 48);
        portable_wifi_credentials_put_u32(chunk + 60, portable_wifi_credentials_crc(chunk, 60));
        int written=portable_wifi_credentials_write_status(kv, portable_wifi_credentials_chunk_key(slot, part), chunk, 64);
        if (written != PORTABLE_WIFI_CREDENTIALS_LOADED) {
            result = !part&&written==PORTABLE_WIFI_CREDENTIALS_AGAIN?written:PORTABLE_WIFI_CREDENTIALS_UNCONFIRMED; goto finish;
        }
    }
    portable_wifi_credentials_make_selector(selector, generation, true, slot, ssid, password,
        portable_wifi_credentials_crc(chunks, 128));
    if (!portable_wifi_credentials_write_verify(kv, PORTABLE_WIFI_CREDENTIALS_SELECTOR_KEY, selector, 32)) {
        result = PORTABLE_WIFI_CREDENTIALS_UNCONFIRMED; goto finish;
    }
    result = portable_wifi_credentials_load(kv, &actual);
    if (result != PORTABLE_WIFI_CREDENTIALS_LOADED || memcmp(actual.ssid, payload, ssid) || actual.ssid[ssid] ||
        memcmp(actual.password, payload + 32, password) || actual.password[password])
        result = PORTABLE_WIFI_CREDENTIALS_UNCONFIRMED;
finish:
    portable_wifi_credentials_clear(&actual);
    portable_wifi_credentials_wipe(selector, sizeof(selector));
    portable_wifi_credentials_wipe(chunks, sizeof(chunks));
    portable_wifi_credentials_wipe(payload, sizeof(payload));
    return result;
}

/* Commit and verify a tombstone BEFORE touching either slot. If confirmation
 * fails, return UNCONFIRMED without erasing any slot. Once confirmed, attempt
 * every slot overwrite even when another fails. Missing/invalid old metadata
 * need not be recovered to forget. Retry completes any interrupted cleanup. */
static inline int portable_wifi_credentials_forget(const risc_key_value_v1 *kv) {
    uint8_t selector[32] = {0}, check[32] = {0}, zeros[64] = {0};
    uint64_t generation = 1;
    int result = PORTABLE_WIFI_CREDENTIALS_UNAVAILABLE;
    bool clean = true;
    if (!portable_wifi_credentials_api_valid(kv)) goto finish;
    result=portable_wifi_credentials_read_blob(kv, PORTABLE_WIFI_CREDENTIALS_SELECTOR_KEY, check, 32);
    if(result==PORTABLE_WIFI_CREDENTIALS_AGAIN)goto finish;
    if (result == PORTABLE_WIFI_CREDENTIALS_LOADED && portable_wifi_credentials_selector_valid(check)) {
        generation = portable_wifi_credentials_generation(check) + 1;
        if (!generation) generation = 1;
    }
    portable_wifi_credentials_make_selector(selector, generation, false, 0, 0, 0, 0);
    result=portable_wifi_credentials_write_status(kv,PORTABLE_WIFI_CREDENTIALS_SELECTOR_KEY,selector,32);
    if(result!=PORTABLE_WIFI_CREDENTIALS_LOADED)goto finish;
    for (unsigned slot = 0; slot < 2; ++slot)
        for (unsigned part = 0; part < 2; ++part)
            if (!portable_wifi_credentials_write_verify(kv, portable_wifi_credentials_chunk_key(slot, part), zeros, 64))
                clean = false;
    if (portable_wifi_credentials_read_blob(kv, PORTABLE_WIFI_CREDENTIALS_SELECTOR_KEY, check, 32) !=
            PORTABLE_WIFI_CREDENTIALS_LOADED || memcmp(check, selector, 32)) {
        result = PORTABLE_WIFI_CREDENTIALS_UNCONFIRMED; goto finish;
    }
    result = clean ? PORTABLE_WIFI_CREDENTIALS_EMPTY : PORTABLE_WIFI_CREDENTIALS_CLEANUP_REMANENCE;
finish:
    portable_wifi_credentials_wipe(selector, sizeof(selector));
    portable_wifi_credentials_wipe(check, sizeof(check));
    portable_wifi_credentials_wipe(zeros, sizeof(zeros));
    return result;
}
#endif
