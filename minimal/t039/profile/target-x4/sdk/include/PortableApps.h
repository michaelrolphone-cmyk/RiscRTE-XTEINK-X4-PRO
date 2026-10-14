#pragma once
#include "T5AppApi.h"
/* Deployment-owned bounded catalog, linked into the application. No discovery,
 * filesystem access or installation claims. Entries are admitted by boot
 * policy. */
extern const t5_app_manifest_t portable_catalog[];
extern const unsigned portable_catalog_count;
