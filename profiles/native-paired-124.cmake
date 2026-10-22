# Additive 0.1.124 paired-storage candidate; .122 and .123 stay frozen.
# This is not a reconstruction of the missing historical composition JSON.
get_filename_component(x4_root "${CMAKE_CURRENT_LIST_DIR}/.." REALPATH)
set(RISC_NATIVE_TARGET "esp32s3-16mb-appdata-iq")
set(RISC_NATIVE_PARTITIONS "${CMAKE_CURRENT_LIST_DIR}/partitions-native-idf61.csv")
set(RISC_NATIVE_SETTINGS_HEADER "${CMAKE_CURRENT_LIST_DIR}/native-idf61-settings.h")
set(RISC_NATIVE_EXTRA_SOURCES "${x4_root}/minimal/native/X4EarlyBoot.cpp")
set(RISC_NATIVE_APPDATA ON)
set(RISC_NATIVE_IQ ON)
set(RISC_NATIVE_DEFINITIONS
    RISC_PAIRED_BANKS=1 RISC_PAIRED_APP_DATA=1
    RISC_ENABLE_HTTP=1 RISC_ENABLE_RADIO_IQ=1 RISC_STAGE_LOGS=1
    RISC_ENABLE_SDMMC=1 RISC_ENABLE_USB_PHY=1
    RISC_NATIVE_DIAGNOSTIC_OBSERVER=1
    RISC_APP_POLICY_ROWS=32 RISC_APP_REQUIREMENT_ROWS=24 RISC_APP_IMAGE_CACHE=1
    RISC_PROVIDER_CAPACITY=40 RISC_INSTALLED_APP_CAPACITY=64 RISC_PLATFORM_CAPACITY=40
    RISC_NATIVE_TCP_LISTENER=1 RISC_NATIVE_ENTROPY=1
    RISC_RETAINED_WAKE_BYTES=512 RISC_NATIVE_FAILURE_EVIDENCE=1
    BOARD_XTEINK_X4_PRO=1 RISC_NATIVE_PACKAGE_VOLUME=1
    RISC_NATIVE_SETTINGS_BACKEND=1 RISC_NATIVE_SETTINGS_STARTUP_ENTROPY=1
    RISC_NATIVE_APP_DATA_MOUNT=1 RISC_NATIVE_SETTINGS_FRESH_INTERNAL_FALLBACK=1
    RISC_NATIVE_SETTINGS_ASSEMBLY=1 RISC_NATIVE_SETTINGS_PSRAM_PAYLOAD=1
    RISC_NATIVE_SETTINGS_LIFECYCLE=1 RISC_NATIVE_SETTINGS_WORKER=1
    RISC_RUNTIME_ATOMIC_KEY_VALUE=1 RISC_NATIVE_STORAGE_CUSTODY=1
    RISC_NATIVE_PROVISION_REQUEST=1
    RISC_NATIVE_SERIAL_FILES=1 RISC_NATIVE_SERIAL_BOOT_FILES=1
    RISC_NATIVE_SERIAL_APPDATA_FILES=1 RISC_NATIVE_SERIAL_SD=1
    RISC_NATIVE_SERIAL_SD_INSTANCE=9
    "RISC_NATIVE_SERIAL_SD_PROVIDER=\"x4pro-sd\"")
set(RISC_NATIVE_COMPILE_OPTIONS -fstack-usage
    "-ffile-prefix-map=${RISC_RUNTIME_ROOT}=."
    "-ffile-prefix-map=${x4_root}=x4")
set(RISC_NATIVE_LINK_OPTIONS
    "-Wl,-u,risc_paired_store_abi" "-Wl,-u,risc_runtime_update_version"
    "-Wl,-u,risc_sdmmc_host_abi" "-Wl,-u,risc_installed_app_capacity"
    "-Wl,-u,risc_tcp_listener_abi" "-Wl,-u,risc_entropy_abi"
    "-Wl,-u,risc_platform_capacity"
    "-Wl,--wrap=esp_panic_handler" "-Wl,-u,risc_native_failure_evidence_abi"
    "-Wl,-u,risc_x4_native_composition_identity"
    "-Wl,-u,risc_x4_native_source_identity" "-Wl,-u,risc_x4_native_ready"
    "-Wl,--wrap=app_main"
    "-Wl,--wrap=esp_vfs_register" "-Wl,-u,__wrap_esp_vfs_register"
    "-Wl,--wrap=esp_vfs_unregister" "-Wl,-u,__wrap_esp_vfs_unregister"
    "-Wl,--wrap=esp_partition_read" "-Wl,-u,__wrap_esp_partition_read"
    "-Wl,--wrap=esp_partition_write" "-Wl,-u,__wrap_esp_partition_write"
    "-Wl,--wrap=esp_partition_erase_range" "-Wl,-u,__wrap_esp_partition_erase_range"
    "-Wl,--wrap=esp_littlefs_format" "-Wl,-u,__wrap_esp_littlefs_format"
    "-Wl,--wrap=esp_littlefs_format_partition" "-Wl,-u,__wrap_esp_littlefs_format_partition")

# Generate a new candidate identity. Never re-use the released composition hash.
# The selection record does not claim a complete historical source inventory.
if(DEFINED RISC_X4_SOURCE_SHA)
    set(x4_source "${RISC_X4_SOURCE_SHA}")
else()
    execute_process(COMMAND git rev-parse HEAD WORKING_DIRECTORY "${x4_root}"
        OUTPUT_VARIABLE x4_source OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
endif()
if(DEFINED RISC_SOURCE_SHA)
    set(x4_runtime_source "${RISC_SOURCE_SHA}")
else()
    execute_process(COMMAND git rev-parse HEAD WORKING_DIRECTORY "${RISC_RUNTIME_ROOT}"
        OUTPUT_VARIABLE x4_runtime_source OUTPUT_STRIP_TRAILING_WHITESPACE COMMAND_ERROR_IS_FATAL ANY)
endif()
foreach(source x4_source x4_runtime_source)
    string(LENGTH "${${source}}" length)
    if(NOT length EQUAL 40 OR NOT "${${source}}" MATCHES "^[0-9a-f]+$")
        message(FATAL_ERROR "X4 candidate requires exact product and Runtime commit identities")
    endif()
endforeach()
set(x4_selection "schema=x4.native-idf61-selection-v1\nproduct_source=${x4_source}\nruntime_source=${x4_runtime_source}\nproduct_baseline=93ee386b7e23628f3776edc6cfd2805cf675d649\nruntime_baseline=6a3b3d46f5b2857eacc6e9863799dec1f466b036\nsdk_source=fff9895c82d744c7237be8847347bdd1b07c6643\ntarget=${RISC_NATIVE_TARGET}\ndefinitions=${RISC_NATIVE_DEFINITIONS}\ncompile_options=-fstack-usage;-ffile-prefix-map=<runtime>=.;-ffile-prefix-map=<product>=x4\nlink_options=${RISC_NATIVE_LINK_OPTIONS}\n")
foreach(input profiles/native-paired-124.cmake profiles/native-idf61-settings.h
              profiles/partitions-native-idf61.csv minimal/native/X4EarlyBoot.cpp
              minimal/native/X4BootRecord.h minimal/native/X4Gpio1Handoff.h
              docs/native-paired-124/source-inputs.json)
    file(SHA256 "${x4_root}/${input}" digest)
    string(APPEND x4_selection "sha256:${input}=${digest}\n")
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${x4_root}/${input}")
endforeach()
string(SHA256 x4_composition "${x4_selection}")
set(x4_generated "${CMAKE_BINARY_DIR}/x4-native-idf61")
file(MAKE_DIRECTORY "${x4_generated}")
file(WRITE "${x4_generated}/selection.txt" "${x4_selection}composition_sha256=${x4_composition}\n")
file(WRITE "${x4_generated}/X4NativeBuildIdentity.h"
    "#pragma once\n#define X4_NATIVE_COMPOSITION_IDENTITY \"X4_NATIVE_COMPOSITION:${x4_composition}\"\n#define X4_NATIVE_SOURCE_IDENTITY \"X4_SOURCE=${x4_source} X4_VERSION=0.1.124-paired-candidate X4_BASELINE=93ee386b7e23628f3776edc6cfd2805cf675d649 X4_NATIVE_BASELINE=6a3b3d46f5b2857eacc6e9863799dec1f466b036\"\n")
set(RISC_NATIVE_INCLUDE_DIRECTORIES "${x4_generated}")
