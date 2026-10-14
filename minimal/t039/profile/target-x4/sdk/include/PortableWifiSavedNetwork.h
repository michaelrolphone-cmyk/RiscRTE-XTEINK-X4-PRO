#ifndef PORTABLE_WIFI_SAVED_NETWORK_H
#define PORTABLE_WIFI_SAVED_NETWORK_H
/* Opt-in saved-profile consumer contract for foreground network clients such
 * as OTA and App Store. The caller must explicitly acquire BOTH authorized
 * grants: storage.key-value@1 instance 6 and net.wifi@1 instance 15. This helper
 * accepts their already-authorized tables; table pointers cannot prove which
 * grant/namespace they came from. There is no implicit/default acquisition,
 * boot policy, retry policy, credentials copy in another format, or logging.
 *
 * Callers serialize station operations, keep both grants live for this call,
 * and own subsequent status polling and checked cleanup/release. Never call
 * while an earlier native operation has unresolved cleanup: even a DOWN status
 * cannot establish that provider-backed storage is safe. After a failed connect
 * request, immediately run checked cleanup before storage-backed service I/O. The provider
 * connect contract MUST copy SSID/password synchronously before returning;
 * the local plaintext credential copy is volatile-wiped before every return.
 * STARTED means only that connect accepted the request, never that a link or
 * usable IP address exists. A non-DOWN station is never disturbed. No scan,
 * cancellation, disconnect, access-point, or storage-write operation is made.
 * A DOWN station may still reject connect (for example, while a scan owns the
 * radio); this helper leaves that ownership and all recovery to its caller.
 */
#include "PortableWifiCredentials.h"
#include "WifiApi.h"

#define PORTABLE_WIFI_SAVED_NETWORK_STORAGE_INSTANCE PORTABLE_WIFI_CREDENTIALS_STORE_INSTANCE
#define PORTABLE_WIFI_SAVED_NETWORK_WIFI_INSTANCE 15u
#define PORTABLE_WIFI_SAVED_NETWORK_WIFI_CAPABILITY "net.wifi"

enum {
    PORTABLE_WIFI_SAVED_NETWORK_STARTED = 0,
    PORTABLE_WIFI_SAVED_NETWORK_EMPTY = 1,
    PORTABLE_WIFI_SAVED_NETWORK_INVALID = 2,
    PORTABLE_WIFI_SAVED_NETWORK_STORAGE_UNAVAILABLE = 3,
    PORTABLE_WIFI_SAVED_NETWORK_WIFI_UNAVAILABLE = 4,
    PORTABLE_WIFI_SAVED_NETWORK_BUSY = 5,
    PORTABLE_WIFI_SAVED_NETWORK_CONNECT_FAILED = 6
};

/* Require the complete station-management suffix, including checked cleanup,
 * even though this bounded helper itself calls only status and connect. AP and
 * legacy unchecked-disconnect callbacks are deliberately not a prerequisite. */
static inline bool portable_wifi_saved_network_api_valid(const wifi_api_v1 *wifi) {
    return wifi && wifi->api_version == WIFI_API_V1 &&
        wifi->struct_size >= WIFI_MANAGEMENT_V1_SIZE &&
        wifi->connect && wifi->status && wifi->rssi && wifi->addresses &&
        wifi->scan_start && wifi->scan_poll && wifi->scan_cancel && wifi->disconnect_checked;
}

/* Storage results take precedence: an absent profile returns EMPTY without
 * touching Wi-Fi. A changing/unconfirmed storage snapshot is unavailable,
 * never a reason to connect with an older profile or a fabricated default. */
static inline int portable_wifi_saved_network_connect(const risc_key_value_v1 *storage,
        const wifi_api_v1 *wifi) {
    portable_wifi_credentials credentials = {{0}, {0}};
    wifi_link_t state = WIFI_LINK_DOWN;
    int result = PORTABLE_WIFI_SAVED_NETWORK_STORAGE_UNAVAILABLE;
    int loaded = portable_wifi_credentials_load(storage, &credentials);
    if (loaded == PORTABLE_WIFI_CREDENTIALS_EMPTY) {
        result = PORTABLE_WIFI_SAVED_NETWORK_EMPTY; goto finish;
    }
    if (loaded == PORTABLE_WIFI_CREDENTIALS_INVALID) {
        result = PORTABLE_WIFI_SAVED_NETWORK_INVALID; goto finish;
    }
    if (loaded != PORTABLE_WIFI_CREDENTIALS_LOADED) goto finish;
    if (!portable_wifi_saved_network_api_valid(wifi)) {
        result = PORTABLE_WIFI_SAVED_NETWORK_WIFI_UNAVAILABLE; goto finish;
    }
    state = wifi->status(wifi->context);
    if (state == WIFI_LINK_JOINING || state == WIFI_LINK_UP) {
        result = PORTABLE_WIFI_SAVED_NETWORK_BUSY; goto finish;
    }
    if (state != WIFI_LINK_DOWN) {
        result = PORTABLE_WIFI_SAVED_NETWORK_WIFI_UNAVAILABLE; goto finish;
    }
    result = wifi->connect(wifi->context, credentials.ssid, credentials.password) ?
        PORTABLE_WIFI_SAVED_NETWORK_STARTED : PORTABLE_WIFI_SAVED_NETWORK_CONNECT_FAILED;
finish:
    portable_wifi_credentials_clear(&credentials);
    return result;
}
#endif
