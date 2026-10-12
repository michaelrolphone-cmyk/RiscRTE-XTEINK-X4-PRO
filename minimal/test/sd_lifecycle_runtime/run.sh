#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
repo="${RUNTIME_REPO:-/workspace/shared/x4-fast-native-20261012}"
mode="${SANITIZE:-normal}"
build="$here/build-$mode";mkdir -p "$build"
flags=(-g)
if [[ "$mode" == address-undefined ]];then flags+=(-fsanitize=address,undefined -fno-omit-frame-pointer -fno-sanitize-recover=all);fi
if [[ "$mode" == undefined ]];then flags+=(-fsanitize=undefined -fno-omit-frame-pointer -fno-sanitize-recover=all);fi
incs=(-I"$repo/src" -I"$repo/sdk/app" -I"$repo/sdk/driver" -I"$repo/sdk/hardware" -I"$repo/lib/ArduinoJson/src" -I"$repo/test/drivers/stubs" -I"$repo/test/support/native_registry/stubs" -I"$repo/lib/elf_loader/include")
for name in host valid legacy;do
 extra=(-DRESIDENT_APP_ROLE=1);if [[ "$name" == host ]];then extra=(-DRESIDENT_APP_ROLE=0);fi
 if [[ "$name" == legacy ]];then extra+=(-DRESIDENT_NO_DESCRIPTOR);fi
 cc "${flags[@]}" -std=c11 -Wall -Wextra -Werror -fPIC -fvisibility=hidden -shared "${incs[@]}" -DRESIDENT_LOADING_TEST "${extra[@]}" "$repo/test/fixtures/resident_app.c" -o "$build/$name.elf"
done
cc "${flags[@]}" -std=c11 -Wall -Wextra -Werror -fPIC -fvisibility=hidden -shared "${incs[@]}" "$here/bad_descriptor_app.c" -o "$build/bad.elf"
cc "${flags[@]}" -std=c11 -Wall -Wextra -Werror -fPIC -fvisibility=hidden -shared "${incs[@]}" "$repo/test/fixtures/removable_provider.c" -o "$build/sd.elf"
c++ "${flags[@]}" -std=c++17 -Wall -Wextra -Werror -Wno-missing-field-initializers -rdynamic -DRISC_REMOVABLE_APP_TEST=1 "${incs[@]}" \
 "$repo/src/bootstrap/Json.cpp" "$repo/src/bootstrap/Board.cpp" "$repo/src/bootstrap/Runtime.cpp" \
 "$repo/src/runtime/streams/AppStreamSessions.cpp" "$repo/src/runtime/streams/ProviderQueueHost.cpp" \
 "$repo/src/runtime/drivers/ProviderGraphV2.cpp" "$repo/src/runtime/drivers/ProviderModuleV2.cpp" \
 "$here/installed_role_test.cpp" -ldl -o "$build/test"
for app in calculator ble_scanner;do
 "$build/test" "$build" "$app" absent valid.elf
 "$build/test" "$build" "$app" foreground valid.elf
done
for app in gameboy model_viewer hollow_trail;do
 "$build/test" "$build" "$app" absent legacy.elf
 "$build/test" "$build" "$app" legacy legacy.elf
done
"$build/test" "$build" calculator bad-descriptor bad.elf
"$build/test" "$build" calculator missing-descriptor legacy.elf
sha256sum "$build/valid.elf"
echo "PASS all 12 installed lifecycle cases; sanitizer=$mode"
