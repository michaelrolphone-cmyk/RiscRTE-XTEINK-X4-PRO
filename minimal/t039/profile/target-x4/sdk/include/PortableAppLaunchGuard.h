#pragma once
#include <stdbool.h>
/* Compile the adapter with PORTABLE_APP_LAUNCH_GUARD only when the linked app
 * implements this callback. A false result consumes one navigation attempt;
 * it is not a provider failure, cleanup result, or Runtime authority grant.
 * Resolve/save/discard app-owned edits and return false to display a prompt.
 * Do not recursively request launch from inside this callback. */
bool portable_app_before_launch(const char *destination);

/* Optional compile-time distinction for a physical Home/root request. This
 * is never called to admit shared controls or an ordinary app launch. Opt in
 * with PORTABLE_APP_HOME_GUARD only when the linked app defines the callback. */
#ifdef PORTABLE_APP_HOME_GUARD
bool portable_app_before_home(void);
#endif
