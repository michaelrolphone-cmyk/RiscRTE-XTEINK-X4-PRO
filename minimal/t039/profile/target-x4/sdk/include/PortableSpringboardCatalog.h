#pragma once
/* Selected paper Springboard only: the builder supplies the admitted count.
 * Keep the existing default for callers without an explicit selected catalog. */
#ifndef PORTABLE_SPRINGBOARD_CATALOG_BOUND
#define PORTABLE_SPRINGBOARD_CATALOG_BOUND 18
#endif
#if PORTABLE_SPRINGBOARD_CATALOG_BOUND < 1 || PORTABLE_SPRINGBOARD_CATALOG_BOUND > 40
#error "Springboard catalog must fit the explicit bounded build contract"
#endif
