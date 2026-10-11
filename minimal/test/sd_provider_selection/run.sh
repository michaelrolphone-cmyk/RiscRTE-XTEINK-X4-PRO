#!/usr/bin/env bash
set -euo pipefail
proof="$(cd "$(dirname "$0")" && pwd)"
repo="${RUNTIME_SOURCE:?}"
build="${BUILD_DIR:-$proof/build}";mkdir -p "$build"
flags=(-g)
if [[ "${SANITIZE:-0}" == 1 ]];then flags+=(-fsanitize=address,undefined -fno-omit-frame-pointer -fno-sanitize-recover=all -fno-pie -no-pie);fi
shared=(-g);if [[ "${SANITIZE:-0}" == 1 ]];then shared+=(-fsanitize=address,undefined -fno-omit-frame-pointer -fno-sanitize-recover=all);fi
cc "${shared[@]}" -std=c11 -shared -fPIC -fvisibility=hidden "$proof/default.c" -o "$build/default.elf"
cc "${shared[@]}" -std=c11 -shared -fPIC -fvisibility=hidden -I"$repo/sdk/app" -I"$repo/sdk/driver" "$proof/sd_provider.c" -o "$build/sd.elf"
cc "${shared[@]}" -std=c11 -shared -fPIC -fvisibility=hidden -I"$repo/sdk/driver" -I"$repo/sdk/hardware" -DFIXTURE_TYPED -DFIXTURE_ID='"sd-plugin"' -DFIXTURE_CAPABILITY='"test.plugin"' "$repo/test/drivers/provider_graph_fixture.c" -o "$build/plugin-host.elf"
cc "${flags[@]}" -std=c11 -I"$repo/test/native_apps/stubs" -I"$repo/lib/elf_loader/include" -c "$repo/lib/elf_loader/src/esp_elf_validate.c" -o "$build/validate.o"
c++ "${flags[@]}" -std=c++17 -Wall -Wextra -Werror -Wno-missing-field-initializers -rdynamic -DRISC_REMOVABLE_APP_TEST=1 \
 -I"$repo/src" -I"$repo/sdk/app" -I"$repo/sdk/driver" -I"$repo/sdk/hardware" -I"$repo/lib/ArduinoJson/src" -I"$repo/test/drivers/stubs" -I"$repo/test/support/native_registry/stubs" -I"$repo/test/native_apps/stubs" -I"$repo/lib/elf_loader/include" \
 "$repo/src/bootstrap/Json.cpp" "$repo/src/bootstrap/Board.cpp" "$repo/src/bootstrap/Runtime.cpp" "$repo/src/runtime/streams/AppStreamSessions.cpp" "$repo/src/runtime/streams/ProviderQueueHost.cpp" "$repo/src/runtime/drivers/ProviderGraphV2.cpp" "$repo/src/runtime/drivers/ProviderModuleV2.cpp" "$proof/selected_image_test.cpp" "$build/validate.o" -Wl,--wrap=dlopen -ldl -o "$build/test"
python3 "$proof/run_cases.py" "$repo" "$build" "$@"
