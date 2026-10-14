#pragma once
#include <stdbool.h>
#include <stdint.h>
/* App-local shared renderer, never a Runtime export or firmware UI API. */
#define PORTABLE_WIFI_VIEW_ROWS 17u
#include "PortableWatchKeyboard.h"
#define PORTABLE_WIFI_KEY_COUNT PWK_COUNT
#define PORTABLE_WIFI_KEYS_PER_PAGE PWK_CHARACTERS
typedef struct {
  const char *title, *message, *detail;
  const char *rows[PORTABLE_WIFI_VIEW_ROWS];
  const char *values[PORTABLE_WIFI_VIEW_ROWS];
  unsigned count, selected;
  bool keyboard;
  unsigned key_page;
#if defined(PORTABLE_TOUCH_SCROLL) && defined(PORTABLE_WIFI_SETTINGS_APP)
  unsigned identity; /* Changes when rows or keyboard page identities change. */
#endif
  const char *entry; /* Already masked by the controller for passwords. */
} portable_wifi_view;
enum { WIFI_HIT_BACK=-2, WIFI_HIT_PREVIOUS=-3, WIFI_HIT_NEXT=-4 };
#if defined(PORTABLE_TOUCH_SCROLL) && defined(PORTABLE_WIFI_SETTINGS_APP)
void portable_wifi_scroll_reset(void);
void portable_wifi_scroll_prepare(const portable_wifi_view *view);
void portable_wifi_scroll_interrupt(void);
bool portable_wifi_scroll_changed(void);
bool portable_wifi_scroll_confirm(const portable_wifi_view *view);
#endif
bool portable_wifi_paper(void);
void portable_wifi_render(const portable_wifi_view *view);
/* Called only after a complete adapter-owned input frame. */
int portable_wifi_hit(const portable_wifi_view *view,int x,int y);
/* Private app/client lifecycle. A false suspend blocks native sleep. A false
 * close blocks handoff/unmapping until the runtime can safely revoke grants. */
/* Reconcile radio health before bound services may read persistent storage. */
bool portable_wifi_services_safe(void);
bool portable_wifi_suspend(void);
/* Healthy asynchronous cleanup is progress, not a retained failure. */
bool portable_wifi_stop_pending(void);
/* Bool HCI lifecycle calls cannot report temporary resource deferral. */
bool portable_wifi_async_owned(void);
/* Pair in one owner turn, without yielding. False begin is clean deferral. */
bool portable_wifi_services_begin(void);
bool portable_wifi_services_end(void);
void portable_wifi_resume(void);
bool portable_wifi_close(void);

bool portable_wifi_idle_ready(void);
