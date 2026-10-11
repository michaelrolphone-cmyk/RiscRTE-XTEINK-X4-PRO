#!/usr/bin/env bash
set -euo pipefail
: "${RUNTIME_REPO:?matching Runtime source required}"
: "${SYSTEM_REPO:?matching System-Apps source required}"
# Arguments: bridge full fixture, draft catalog, actual successor cohort.
root="$(cd "$(dirname "$0")" && pwd)"
build="$(mktemp -d)"; trap 'rm -rf "$build"' EXIT
openssl="${OPENSSL_PREFIX:-/usr}"
c++ -DRISC_PAIRED_APP_DATA -std=c++17 -Wall -Wextra -Wno-return-type -fsanitize=undefined -fno-sanitize-recover=all \
 -I"$RUNTIME_REPO/src" -I"$RUNTIME_REPO/test" -I"$RUNTIME_REPO/sdk/app" -I"$RUNTIME_REPO/sdk/driver" -I"$RUNTIME_REPO/sdk/hardware" \
 -I"$SYSTEM_REPO/Services/update" -I"$SYSTEM_REPO/lib/PortableApps/include" -I"$SYSTEM_REPO/lib/NativeApps/include" \
 -I"$openssl/include" "$root/qualified_update_service_test.cpp" "$RUNTIME_REPO/src/runtime/update/PairedBank.cpp" \
 -L"$openssl/lib" -lcrypto -o "$build/test"
"$build/test" "$@"
