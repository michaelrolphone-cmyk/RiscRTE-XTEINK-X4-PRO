#pragma once
// Separate Wi-Fi successor: preserve all six native writers and append policy writer.
// This is a logical firmware domain, not a card ID, MAC address or secret.
#define RISC_NATIVE_SETTINGS_LOGICAL_OWNER {'X','4','-','R','T','E','-','S','E','T','T','I','N','G','S',1}
#define RISC_NATIVE_SETTINGS_VOLUME_INSTANCE 9
#define RISC_NATIVE_SETTINGS_WRITERS {"settings",1},{"paper_clock",1},{"battery",1},{"ble_scanner",1},{"contexts",1},{"wifi_settings",6},{"wifi_settings",1}
#define RISC_NATIVE_SETTINGS_PORT_SELECTED 1
#define RISC_NATIVE_SETTINGS_NAMESPACE_MASK 3
#define RISC_NATIVE_SETTINGS_MAX_WRITERS 7
#define RISC_RUNTIME_ATOMIC_BINDING_CAPACITY 9
