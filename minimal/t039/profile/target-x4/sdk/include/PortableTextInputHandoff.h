#pragma once
#include <stdbool.h>
/* App-local presenter handoff. These functions never pass app callbacks or
 * buffers to the separately loaded host. Resume is legal only after the host
 * has confirmed its close and the client's capability grant is released. */
int portable_text_adapter_suspend(void);
int portable_text_adapter_resume(void);
int portable_text_adapter_attention(void);
void portable_text_adapter_retain(void);
bool portable_text_adapter_retained(void);
