#pragma once
#include <stdbool.h>
/* App-local host entry points. The Runtime table remains invocation-bound. */
enum {
 PORTABLE_RESIDENT_FAILED=0, PORTABLE_RESIDENT_RETURNED=1,
 PORTABLE_RESIDENT_HANDOFF=2, PORTABLE_RESIDENT_NO_PENDING=3
};
/* HANDOFF requires immediate app_main return: no focus, repaint or provider
 * restore. NULL is a startup continuation query only in the explicit legacy
 * compatibility profile. A negative result seals terminal retention. */
int portable_resident_run_foreground(const char *path);
const char *portable_resident_take_launch(void);
bool portable_resident_take_sleep(void);
