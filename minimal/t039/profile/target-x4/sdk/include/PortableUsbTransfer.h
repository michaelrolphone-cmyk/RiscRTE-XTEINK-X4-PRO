#pragma once
#include <stdbool.h>
/* Private foreground-owner integration. The capability and all media custody
 * remain in the dedicated app; ordinary Quick Actions only launch its ELF. */
void portable_usb_transfer_service(void);
bool portable_usb_transfer_close(void);
bool portable_usb_transfer_owned(void);
