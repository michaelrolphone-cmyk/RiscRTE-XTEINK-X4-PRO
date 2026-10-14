#pragma once
#include "RiscStorageVolumeV1.h"
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

/* Foreground, serialized, post-restart export only. Never call from a panic,
 * logging callback, provider poll, scheduler yield, or another export. The
 * caller keeps the text/SHA buffers immutable throughout the call, keeps its
 * exact internal spool until SAVED, and retains the selected
 * provider/dependencies for the lifetime of state. A RETAINED state is terminal
 * until a real restart: do not unload, remount, export USB, sleep, or retry I/O.
 * safe() must include a side-effect-free provider custody observation, including
 * after the FIRST ready() false and after a successful final close. A boolean
 * ready or grant release alone cannot prove that a pinned provider is safe.
 * safe() is an ownership/admission check, not a readiness test:
 * an absent/exported card should leave it true so ready() can defer normally.
 * Both hooks must be non-reentrant and must not log, yield, or perform I/O.
 * Initial unavailable media defers. After readiness has been established, a
 * refused stat/mkdir/open/rename/remove is checked with ready(): false conservatively
 * retains because it can hide poisoned provider custody, even without a token.
 *
 * Bounds: <=4096 report bytes, <=512 bytes per read/write, <=96 provider calls.
 * budget_ms bounds admission of ordinary calls; up to four reserved checked
 * cleanup/readiness calls may follow expiry. No wrapper can preempt a running
 * synchronous provider call (the selected SD provider's timeout still applies).
 * There is no allocation, background work, refresh, scan, or old-report delete.
 */
#define CRASH_REPORT_SD_TEXT_MAX 4096u
#define CRASH_REPORT_SD_CHUNK_MAX 512u
#define CRASH_REPORT_SD_PATH_CAPACITY 128u
#define CRASH_REPORT_SD_OPERATION_LIMIT 96u
#define CRASH_REPORT_SD_CLEANUP_RESERVE 4u
#define CRASH_REPORT_SD_DEFAULT_BUDGET_MS 250u
#define CRASH_REPORT_SD_MAX_BUDGET_MS 1000u

typedef enum {
 CRASH_REPORT_SD_DEFERRED=0,
 CRASH_REPORT_SD_SAVED=1,
 CRASH_REPORT_SD_RETAINED=2
} crash_report_sd_result;

typedef struct {
 bool retained;
 unsigned operations;
} crash_report_sd_state;

typedef struct {
 void *context;
 uint64_t (*monotonic_ms)(void *context);
 bool (*safe)(void *context);
 uint32_t budget_ms; /* 0 selects the default; larger values are capped. */
} crash_report_sd_hooks;

static inline uint32_t crash_report_sd_crc32(const void *text,size_t length) {
 const unsigned char *bytes=(const unsigned char *)text;
 uint32_t crc=UINT32_MAX;
 for(size_t i=0;i<length;++i) {
  crc^=bytes[i];
  for(unsigned bit=0;bit<8;++bit)crc=(crc>>1)^((0u-(crc&1u))&UINT32_C(0xedb88320));
 }
 return ~crc;
}
static inline char *crash_report_sd_hex32(char *out,uint32_t value) {
 static const char hex[]="0123456789abcdef";
 for(unsigned i=0;i<8;++i)*out++=hex[(value>>(28u-i*4u))&15u];
 return out;
}
/* sha256 must point to exactly 64 hexadecimal characters plus a terminator.
 * Full firmware identity + boot + sequence + text CRC distinguishes reports.
 * A CRC/name collision only defers: final files are never replaced or removed.
 */
static inline bool crash_report_sd_path(char *out,size_t capacity,const char sha256[65],
 uint32_t boot,uint32_t sequence,uint32_t text_crc,bool temporary) {
 if(!out || capacity<CRASH_REPORT_SD_PATH_CAPACITY || !sha256)return false;
 for(unsigned i=0;i<64;++i) {
  char c=sha256[i];
  if(!((c>='0' && c<='9') || (c>='a' && c<='f') || (c>='A' && c<='F')))return false;
 }
 if(sha256[64])return false;
 char *p=out;
 memcpy(p,"/CrashReports/",14);p+=14;
 for(unsigned i=0;i<64;++i) {
  char c=sha256[i];*p++=(char)(c>='A' && c<='F'?c+('a'-'A'):c);
 }
 *p++='-';p=crash_report_sd_hex32(p,boot);
 *p++='-';p=crash_report_sd_hex32(p,sequence);
 *p++='-';p=crash_report_sd_hex32(p,text_crc);
 memcpy(p,temporary?".tmp":".txt",5);
 return true;
}

typedef struct {
 crash_report_sd_state *state;
 const risc_storage_volume_api_v1_ext *volume;
 const crash_report_sd_hooks *hooks;
 uint64_t started;
 uint32_t budget;
 risc_storage_file_t handle;
 bool temporary_owned;
 bool temporary_cleanup_failed;
 const char *temporary;
} crash_report_sd_attempt;

static inline bool crash_report_sd_safe(crash_report_sd_attempt *a) {
 if(a->state->retained)return false;
 if(!a->hooks->safe(a->hooks->context))a->state->retained=true;
 return !a->state->retained;
}
static inline bool crash_report_sd_admit(crash_report_sd_attempt *a,bool cleanup) {
 if(!crash_report_sd_safe(a))return false;
 unsigned limit=cleanup?CRASH_REPORT_SD_OPERATION_LIMIT:
  CRASH_REPORT_SD_OPERATION_LIMIT-CRASH_REPORT_SD_CLEANUP_RESERVE;
 if(a->state->operations>=limit) {
  if(cleanup)a->state->retained=true;
  return false;
 }
 if(!cleanup) {
  uint64_t now=a->hooks->monotonic_ms(a->hooks->context);
  if(!crash_report_sd_safe(a) || now-a->started>=a->budget)return false;
 }
 ++a->state->operations;return true;
}
static inline bool crash_report_sd_ready(crash_report_sd_attempt *a,bool cleanup) {
 if(!crash_report_sd_admit(a,cleanup))return false;
 bool ready=a->volume->base.ready(a->volume->base.context);
 return crash_report_sd_safe(a) && ready;
}
static inline bool crash_report_sd_close(crash_report_sd_attempt *a) {
 if(!a->handle)return !a->state->retained;
 if(!crash_report_sd_admit(a,true))return false;
 bool closed=a->volume->base.file_close(a->volume->base.context,a->handle,true);
 if(!crash_report_sd_safe(a))return false;
 if(!closed) {a->state->retained=true;return false;}
 a->handle=RISC_STORAGE_FILE_INVALID;return true;
}
static inline bool crash_report_sd_remove_temporary(crash_report_sd_attempt *a) {
 if(a->temporary_cleanup_failed)return false;
 if(!a->temporary_owned)return !a->state->retained;
 if(!crash_report_sd_admit(a,true))return false;
 bool removed=a->volume->base.remove(a->volume->base.context,a->temporary);
 if(!crash_report_sd_safe(a))return false;
 if(!removed) {
  /* Read-only media can cleanly refuse an unlink. Never retry it in this
   * attempt, or report SAVED. Failed readiness instead means uncertain
   * provider custody and must retain, even when there is no open token. */
  a->temporary_cleanup_failed=true;
  if(!crash_report_sd_ready(a,true))a->state->retained=true;
  return false;
 }
 a->temporary_owned=false;return true;
}
static inline bool crash_report_sd_open(crash_report_sd_attempt *a,const char *path,uint32_t flags) {
 if(!crash_report_sd_admit(a,false))return false;
 a->handle=a->volume->file_open(a->volume->base.context,path,flags);
 if(!crash_report_sd_safe(a))return false;
 if(a->handle)return true;
 /* The selected provider can allocate a FIL and then return 0 when its guard
  * leave fails. An attempted open with failed readiness is uncertain ownership,
  * even though there is no token available for us to close. */
 if(!crash_report_sd_ready(a,true))a->state->retained=true;
 return false;
}
static inline bool crash_report_sd_error_clear(crash_report_sd_attempt *a) {
 if(!crash_report_sd_admit(a,false))return false;
 uint32_t error=a->volume->handle_error(a->volume->base.context,a->handle,false);
 return crash_report_sd_safe(a) && !error;
}
static inline bool crash_report_sd_sync(crash_report_sd_attempt *a) {
 if(!crash_report_sd_admit(a,false))return false;
 bool synced=a->volume->file_sync(a->volume->base.context,a->handle);
 return crash_report_sd_safe(a) && synced;
}
/* An already opened ordinary file is compared byte-for-byte, including length
 * and EOF. Success includes checked sync and close, also on the dedupe path. */
static inline bool crash_report_sd_verify(crash_report_sd_attempt *a,const void *text,size_t length) {
 uint64_t size=0,position=UINT64_MAX;
 if(!crash_report_sd_admit(a,false))return false;
 bool info=a->volume->file_info(a->volume->base.context,a->handle,&size,&position);
 if(!crash_report_sd_safe(a) || !info || size!=length || position)return false;
 unsigned char chunk[CRASH_REPORT_SD_CHUNK_MAX];
 for(size_t offset=0;offset<length;) {
  size_t request=length-offset;
  if(request>sizeof(chunk))request=sizeof(chunk);
  if(!crash_report_sd_admit(a,false))return false;
  size_t read=a->volume->base.file_read(a->volume->base.context,a->handle,chunk,request);
  if(!crash_report_sd_safe(a) || read!=request || !crash_report_sd_error_clear(a) ||
     memcmp(chunk,(const unsigned char *)text+offset,request))return false;
  offset+=request;
 }
 if(!crash_report_sd_admit(a,false))return false;
 size_t extra=a->volume->base.file_read(a->volume->base.context,a->handle,chunk,1);
 if(!crash_report_sd_safe(a) || extra || !crash_report_sd_error_clear(a) ||
    !crash_report_sd_sync(a))return false;
 return crash_report_sd_close(a);
}

static inline crash_report_sd_result crash_report_sd_export(crash_report_sd_state *state,
 const risc_storage_volume_api_v1_ext *volume,const char firmware_sha256[65],
 uint32_t boot,uint32_t sequence,const void *text,size_t length,const crash_report_sd_hooks *hooks) {
 if(!state)return CRASH_REPORT_SD_DEFERRED;
 if(state->retained)return CRASH_REPORT_SD_RETAINED;
 state->operations=0;
 if(!volume || volume->base.api_version!=RISC_STORAGE_VOLUME_API_V1 ||
    volume->base.struct_size<sizeof(*volume) || !volume->base.ready || !volume->base.stat ||
    !volume->base.file_read || !volume->base.file_write || !volume->base.file_close ||
    !volume->base.remove || !volume->file_open || !volume->file_info || !volume->file_sync ||
    !volume->handle_error || !volume->mkdir || !volume->rename || !hooks ||
    !hooks->monotonic_ms || !hooks->safe || !text || !length || length>CRASH_REPORT_SD_TEXT_MAX)
  return CRASH_REPORT_SD_DEFERRED;
 char final[CRASH_REPORT_SD_PATH_CAPACITY],temporary[CRASH_REPORT_SD_PATH_CAPACITY];
 uint32_t crc=crash_report_sd_crc32(text,length);
 if(!crash_report_sd_path(final,sizeof(final),firmware_sha256,boot,sequence,crc,false) ||
    !crash_report_sd_path(temporary,sizeof(temporary),firmware_sha256,boot,sequence,crc,true))
  return CRASH_REPORT_SD_DEFERRED;
 crash_report_sd_attempt a={state,volume,hooks,0,0,RISC_STORAGE_FILE_INVALID,false,false,temporary};
 a.budget=hooks->budget_ms?hooks->budget_ms:CRASH_REPORT_SD_DEFAULT_BUDGET_MS;
 if(a.budget>CRASH_REPORT_SD_MAX_BUDGET_MS)a.budget=CRASH_REPORT_SD_MAX_BUDGET_MS;
 if(!crash_report_sd_safe(&a))return CRASH_REPORT_SD_RETAINED;
 a.started=hooks->monotonic_ms(hooks->context);
 if(!crash_report_sd_safe(&a))return CRASH_REPORT_SD_RETAINED;
 bool saved=false,directory=false,exists=false;
 uint64_t size=0;
 if(!crash_report_sd_ready(&a,false))goto finish;
 if(!crash_report_sd_admit(&a,false))goto finish;
 exists=volume->base.stat(volume->base.context,"/CrashReports",&size,&directory);
 if(!crash_report_sd_safe(&a))goto finish;
 if(exists) {if(!directory)goto finish;}
 else {
  if(!crash_report_sd_ready(&a,true)) {state->retained=true;goto finish;}
  if(!crash_report_sd_admit(&a,false))goto finish;
  bool created=volume->mkdir(volume->base.context,"/CrashReports");
  if(!crash_report_sd_safe(&a))goto finish;
  if(!created) {
   if(!crash_report_sd_ready(&a,true))state->retained=true;
   goto finish;
  }
 }
 if(!crash_report_sd_admit(&a,false))goto finish;
 exists=volume->base.stat(volume->base.context,final,&size,&directory);
 if(!crash_report_sd_safe(&a))goto finish;
 if(exists) {
  if(directory || size!=length || !crash_report_sd_open(&a,final,RISC_STORAGE_OPEN_READ))goto finish;
  saved=crash_report_sd_verify(&a,text,length);goto finish;
 }
 if(!crash_report_sd_ready(&a,true)) {state->retained=true;goto finish;}
 /* Only this report's deterministic .tmp can be removed. No directory handles
  * or scans are used. This allows a fresh-boot retry of an interrupted write. */
 if(!crash_report_sd_admit(&a,false))goto finish;
 exists=volume->base.stat(volume->base.context,temporary,&size,&directory);
 if(!crash_report_sd_safe(&a))goto finish;
 if(exists) {
  if(directory)goto finish;
  a.temporary_owned=true;
  if(!crash_report_sd_remove_temporary(&a))goto finish;
 }else if(!crash_report_sd_ready(&a,true)) {state->retained=true;goto finish;}
 if(!crash_report_sd_open(&a,temporary,
    RISC_STORAGE_OPEN_WRITE|RISC_STORAGE_OPEN_CREATE|RISC_STORAGE_OPEN_EXCLUSIVE))goto finish;
 a.temporary_owned=true;
 for(size_t offset=0;offset<length;) {
  size_t request=length-offset;
  if(request>CRASH_REPORT_SD_CHUNK_MAX)request=CRASH_REPORT_SD_CHUNK_MAX;
  if(!crash_report_sd_admit(&a,false))goto finish;
  size_t written=volume->base.file_write(volume->base.context,a.handle,(const unsigned char *)text+offset,request);
  if(!crash_report_sd_safe(&a) || written!=request || !crash_report_sd_error_clear(&a))goto finish;
  offset+=request;
 }
 if(!crash_report_sd_sync(&a) || !crash_report_sd_close(&a))goto finish;
 if(!crash_report_sd_open(&a,temporary,RISC_STORAGE_OPEN_READ) ||
    !crash_report_sd_verify(&a,text,length))goto finish;
 if(!crash_report_sd_admit(&a,false))goto finish;
 {
  bool renamed=volume->rename(volume->base.context,temporary,final);
  if(!crash_report_sd_safe(&a))goto finish;
  if(!renamed) {
   if(!crash_report_sd_ready(&a,true))state->retained=true;
   goto finish;
  }
 }
 a.temporary_owned=false;
 if(!crash_report_sd_open(&a,final,RISC_STORAGE_OPEN_READ))goto finish;
 saved=crash_report_sd_verify(&a,text,length);
finish:
 /* No provider call is admitted after an unsafe callback/uncertain close or
  * removal. A clean failure closes once, then attempts only our owned .tmp.
  * A refused cleanup is never retried during this attempt. */
 if(!state->retained && crash_report_sd_close(&a))crash_report_sd_remove_temporary(&a);
 return state->retained?CRASH_REPORT_SD_RETAINED:
  saved && !a.temporary_cleanup_failed?CRASH_REPORT_SD_SAVED:CRASH_REPORT_SD_DEFERRED;
}
