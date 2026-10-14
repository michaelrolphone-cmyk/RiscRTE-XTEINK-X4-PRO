#pragma once
#include <stdbool.h>
/* File handles never cross a poll, sleep, alarm or quick-control boundary.
 * A failed read-handle close retains its grant and blocks further storage I/O.
 * The controller retries Close/Back; it never abandons uncertain ownership. */
#ifdef PORTABLE_TOUCH_SCROLL
#include "PortableTouchScroll.h"
void portable_file_browser_scroll_interrupt(void);
void portable_file_browser_touch_sample(portable_touch_sample *sample,uint32_t *now);
void portable_file_browser_scroll_clip(const portable_scroll_viewport *view);
#endif
bool portable_file_browser_safe(void);
bool portable_file_browser_close(void);
