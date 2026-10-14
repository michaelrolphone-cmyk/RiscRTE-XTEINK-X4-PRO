#pragma once
#include "PortableTouchScroll.h"
/* Private linked-client interface. No Runtime/provider ABI expansion. The
 * app must preserve its latest dirty state until ready, and associate hit
 * identities with completed rather than merely submitted frames. */
void portable_paper_scroll_sample(portable_touch_sample *sample,uint32_t *now);
void portable_paper_scroll_clip(const portable_scroll_viewport *view);
bool portable_paper_scroll_settled(void);
bool portable_paper_scroll_available(void);
