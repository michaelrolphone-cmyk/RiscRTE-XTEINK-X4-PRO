#ifndef UTILITIES_POINTS_CATALOG_PROJECTION_H
#define UTILITIES_POINTS_CATALOG_PROJECTION_H
#include <stdint.h>
/* Faces receive copies only; this fixed projection capacity is unrelated to
 * the number of events stored and scheduled. */
#define POINTS_CATALOG_NEXT_COUNT 4u
typedef struct {
    uint32_t event_id,type_id,revision,deadline,parent_day,color;
    uint8_t edge,mode,symbol;uint8_t reserved[1];char label[32];
} points_catalog_event;
typedef struct {
    uint32_t struct_size,catalog_revision,snapshot,seconds,count,flags,has_previous,valid_until;
    points_catalog_event previous,next[POINTS_CATALOG_NEXT_COUNT];
} points_catalog_projection;
#endif
