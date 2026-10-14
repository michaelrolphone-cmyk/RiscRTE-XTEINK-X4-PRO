#pragma once
#include "RiscInputNavigationV1.h"
#include "RiscRuntimeV1.h"
/* Optional deployment-owned, app-local navigation bridge. The default remains
 * the granted input.navigation@1 capability. A local bridge must return that
 * same contract, acquire only declared runtime capabilities, and never expose
 * board-specific details to shared apps. No new runtime export is required.
 *
 * close is called even when open or API validation fails, so implementations
 * must release partially acquired resources and make close idempotent. */
#ifdef PORTABLE_INPUT_NAVIGATION_LOCAL
const risc_input_navigation_api_v1 *portable_input_navigation_open(
    const risc_runtime_api_v1 *runtime);
void portable_input_navigation_close(const risc_runtime_api_v1 *runtime);
#endif
