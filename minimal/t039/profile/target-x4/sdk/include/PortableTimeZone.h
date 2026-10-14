#ifndef PORTABLE_TIMEZONE_H
#define PORTABLE_TIMEZONE_H
/* App-owned pure conversion policy. No runtime/provider/chip ABI, global TZ,
 * allocation, libc calendar, environment, or implicit persistent changes. */
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define PORTABLE_TIMEZONE_ID_BYTES 40u
#define PORTABLE_TIMEZONE_RULE_BYTES 96u
#define PORTABLE_TIMEZONE_MIN_YEAR 1600
#define PORTABLE_TIMEZONE_MAX_YEAR 9999
#define PORTABLE_TIMEZONE_USABLE_EPOCH INT64_C(946684800)
#define PORTABLE_TIMEZONE_VALID_EPOCH INT64_C(1704067200)
typedef enum {
    PORTABLE_TIMEZONE_OK=0, PORTABLE_TIMEZONE_FALLBACK=1,
    PORTABLE_TIMEZONE_FOLD=2, PORTABLE_TIMEZONE_GAP=3,
    PORTABLE_TIMEZONE_INVALID=-1, PORTABLE_TIMEZONE_RANGE=-2,
    PORTABLE_TIMEZONE_BAD_RULE=-3, PORTABLE_TIMEZONE_UNUSABLE=-4
} portable_timezone_status;
typedef enum {
    PORTABLE_TIMEZONE_UTC=0, PORTABLE_TIMEZONE_AFRICA, PORTABLE_TIMEZONE_AMERICA,
    PORTABLE_TIMEZONE_ANTARCTICA, PORTABLE_TIMEZONE_ARCTIC, PORTABLE_TIMEZONE_ASIA,
    PORTABLE_TIMEZONE_ATLANTIC, PORTABLE_TIMEZONE_AUSTRALIA, PORTABLE_TIMEZONE_EUROPE,
    PORTABLE_TIMEZONE_INDIAN, PORTABLE_TIMEZONE_PACIFIC, PORTABLE_TIMEZONE_REGION_COUNT
} portable_timezone_region;
typedef struct { const char *id; const char *posix; portable_timezone_region region; } portable_timezone_entry;
/* Sunday=0; input weekday is ignored and recomputed. Gregorian, no leap seconds. */
typedef struct { int32_t year; uint8_t month,day,hour,minute,second,weekday; } portable_timezone_civil;
typedef struct { uint8_t month,week,weekday; int32_t seconds; } portable_timezone_transition;
typedef struct {
    int32_t standard_offset,daylight_offset; /* Seconds EAST of UTC. */
    uint8_t has_daylight;
    portable_timezone_transition start,end;
} portable_timezone_rule;
typedef struct { int64_t epoch; int32_t offset; uint8_t daylight; } portable_timezone_candidate;
typedef struct { unsigned count; portable_timezone_candidate candidate[2]; } portable_timezone_inverse;
/* Inputs include their accessible byte capacity. A terminating NUL must occur
 * within that capacity and the declared maximum. No truncation is accepted. */
unsigned portable_timezone_count(void);
const portable_timezone_entry *portable_timezone_get(unsigned index); /* NULL on bad index. */
int portable_timezone_find(const char *id,size_t capacity); /* -1 if invalid. UTC aliases supported. */
const char *portable_timezone_region_name(unsigned region); /* NULL if invalid. */
unsigned portable_timezone_region_count(unsigned region);
int portable_timezone_city_index(unsigned region,unsigned city); /* Complete catalog; -1 if invalid. */
int portable_timezone_display_name(unsigned index,char *out,size_t capacity); /* RANGE if insufficient. */
int portable_timezone_parse(const char *posix,size_t capacity,portable_timezone_rule *out);
/* Unknown/malformed IDs return FALLBACK and a usable UTC0 rule. */
int portable_timezone_resolve(const char *id,size_t capacity,portable_timezone_rule *out);
int portable_timezone_civil_to_epoch(const portable_timezone_civil *civil,int64_t *out);
int portable_timezone_epoch_to_civil(int64_t epoch,portable_timezone_civil *out);
int portable_timezone_utc_to_local(const portable_timezone_rule *rule,int64_t epoch,
    portable_timezone_civil *out,portable_timezone_candidate *details);
/* OK=one candidate; FOLD=two in ascending UTC order; GAP=none. No implicit
 * fold choice or gap normalization. Candidate offsets describe actual UTC. */
int portable_timezone_local_to_utc(const portable_timezone_rule *rule,
    const portable_timezone_civil *civil,portable_timezone_inverse *out);
/* Pure Reader boot interpretation. Caller explicitly chooses an index for a
 * fold (0=earlier, 1=later), or -1 to reject ambiguity. A gap/unchosen fold is
 * not usable local-calendar RTC data; a valid UTC interpretation can still win.
 * utc_stores_hint must be 0/1. Reference is a saved epoch, NEVER calibration.
 * Successful selection does not write RTC, system time, or preferences. */
typedef struct {
    int64_t epoch,utc_epoch,local_epoch;
    int32_t local_status;
    uint8_t stores_utc,mode_changed,utc_usable,local_usable;
} portable_timezone_rtc_result;
int portable_timezone_interpret_rtc(const portable_timezone_rule *rule,
    const portable_timezone_civil *rtc,unsigned utc_stores_hint,
    uint32_t reference_epoch,int fold_choice,portable_timezone_rtc_result *out);
#ifdef __cplusplus
}
#endif
#endif
