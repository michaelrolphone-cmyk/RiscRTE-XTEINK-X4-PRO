#pragma once
#include "PortablePointsCatalogView.h"
/* Copies the existing alarm client's read-only projection at a settled point.
 * 1 copied, 2 pending reconciliation, 0 unavailable/unsupported,
 * -1 ordinary error, -2 uncertain custody. Pending never modifies out. */
int portable_home_points_catalog(portable_points_catalog_view *out);
#ifdef PORTABLE_DESK_CLOCK_SPARSE_START
/* TIMER only, before peripheral holds: bounded service reconciliation through
 * the same grant. No promotion or foreground policy. Same result contract. */
int portable_desk_points_catalog_refresh(portable_points_catalog_view *out);
#endif
