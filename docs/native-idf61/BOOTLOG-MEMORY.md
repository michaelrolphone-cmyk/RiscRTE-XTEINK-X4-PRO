# Native X4 bootlog copy placement

## Scope and capacity

`X4EarlyBoot.cpp` places only these four zero-initialized, ordinary-task copies
in SDK external BSS when both native IDF and external BSS are enabled:

| Copy | Bytes | Purpose |
| --- | ---: | --- |
| `X4BootLog::history` | 3648 | Eight complete persistent boot sessions |
| `X4BootLog::current` | 456 | Current persistent boot session |
| `previous` | 264 | Reporting copy of the previous RTC boot record |
| `X4BootLog::earlyEvents` | 160 | Ten early rail-event records |
| **Total** | **4528** | No capacity reduction |

The previous X4 CI ELF had `_heap_start = 0x3fcb1150`, overlapping the fixed
IQ bank by 4432 bytes. This change predicts **only 96 bytes of static margin**;
alignment and other linked changes can consume it. This prediction is not a
release result. The unchanged Runtime `scripts/radio_iq_proof.py` remains the
release authority for `[0x3fcb0000, 0x3fcc0000)` and its IRAM alias. The bank is
not moved, and this placement proof cannot override a failed IQ proof.

## Lifetime and custody audit

The first accesses occur in wrapped `app_main`, after the SDK maps and clears
external BSS. `previous` is copied from the retained record there. Rail-event
copies are produced by the synchronous GPIO1 handoff and consumed by bootlog
startup. History and current-session copies are ordinary NVS/reporting state.
They are not used by a wake stub, ISR, panic handler, or application cache-off
path. The diagnostic observer is owner-task-only and only sets an internal
pending flag; persistent storage drains outside the borrowed-line observer.

The live 264-byte `risc_x4_boot_record` remains `RTC_NOINIT_ATTR`. Startup
admission, counters, NVS handle, pending/reentrancy flags and storage status
remain internal. Neither Runtime retained-wake storage nor any CPU, settings,
diagnostic control or ISR state changes. The four types have zero static
initialization and need no global constructor. Legacy builds keep their
previous placement because the placement macro is empty outside native IDF.

Native external-BSS placement requires `CONFIG_SPIRAM_BOOT_INIT`; the source
rejects a configuration that enables this placement without boot-time PSRAM
initialization. The effective-config packaging gate must require both
`CONFIG_SPIRAM_BOOT_INIT` and
`CONFIG_SPIRAM_ALLOW_BSS_SEG_EXTERNAL_MEMORY`.

## Pinned SDK flash/cache audit

The audit used official ESP-IDF v6.1 commit
`fff9895c82d744c7237be8847347bdd1b07c6643`:

- `components/esp_system/port/cpu_start.c` initializes PSRAM and calls
  `esp_psram_bss_init()` before application startup. External BSS requires
  successful PSRAM initialization.
- `components/esp_psram/system_layer/esp_psram.c` maps/zeros external BSS and excludes its
  reserved storage from the allocatable PSRAM heap.
- `components/nvs_flash/src/nvs_page.cpp` and `nvs_partition.cpp` send NVS data
  through the partition write path to `esp_flash_write`.
- `components/spi_flash/esp_flash_api.c`, `esp_flash_write`, checks whether
  the source is internal DRAM or direct-write-supported. For the non-DRAM
  SPI1 source it copies chunks into the internal 32-byte `temp_buf` before
  `start_prog` disables caches.
- `components/esp_hal_mspi/spi_flash_hal.c` sets SPI1
  `supports_direct_write` false. Therefore external `current` is not read
  during the flash-disabled program interval.

This establishes the existing synchronous NVS path's custody of external
source bytes. It is not permission to add new ISR, panic or cache-off uses of
these copies, or to relocate the live RTC record.

## Qualification and release boundaries

`minimal/test/verify_native_idf61_bootlog_memory.py` exposes `proof(elf_bytes)`
and a `--elf` CLI. It accepts the pinned target's Xtensa ELF32 little-endian
object or final executable, and checks:

- Exact capacities, eight-byte alignment, and external-BSS section placement.
- Zero-only object storage; final external BSS must be NOLOAD/NOBITS and in
  the ESP32-S3 external address range.
- Twelve startup/persistence controls in internal data, and unchanged RTC
  record size/section.
- No pre-`app_main` constructor in the source object. On a final ELF, no
  X4 source constructor is permitted; other firmware constructors are valid.
- For the object, actual relocation-backed `CALLX8` instructions preserve the
  eight GPIO1 stages, eight early-event captures, bootlog start, native-ready
  admission and Runtime entry ordering.

The bounded target object compiled in the official SDK6.1 context passes
these checks. Its compile command and object are qualification evidence,
not a distributable source identity or final firmware. Source host regressions
also pass the 72 GPIO1/readiness combinations and bootlog recovery tests in
normal and ASAN/UBSAN builds. The host attribute shim exercises placement
syntax and initialization; only target ELF inspection establishes placement.
All 24 executable `.text.*` sections match the pre-placement target object
byte-for-byte. Negative checks reject reduced capacity, an internal copy,
a nonzero external initializer, an external control, a removed startup call,
a constructor section, and the previous failing final ELF.

The object proof is supplemented, not replaced, by the final linked startup
proof in `verify_native_idf61_target.py`, the package's final bootlog-memory
proof, and the unchanged Runtime IQ proof. Final CI must run all three on
the actual candidate ELF. No hardware boot or power-path qualification is
claimed by these source and target-object checks.
