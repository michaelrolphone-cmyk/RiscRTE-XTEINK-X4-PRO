#pragma once
#include "RiscFailureEvidenceV1.h"
#include <stddef.h>
#include <stdio.h>

/* Shared report body only. Each callback receives one NUL-terminated logical
 * line, without a newline. The pointer is valid only during that callback;
 * wrapping, separators and storage belong to the sink. No allocation, runtime
 * calls, acknowledgement or invented stack frames occur here. */
#define FAILURE_EVIDENCE_REPORT_LINE_CAPACITY 193u
typedef bool (*failure_evidence_report_sink)(void *context,const char *line);

static inline const char *failure_evidence_report_phase(uint32_t phase) {
 switch(phase) {
 case RISC_FAILURE_PHASE_LOAD:return "load";
 case RISC_FAILURE_PHASE_INIT:return "initialize";
 case RISC_FAILURE_PHASE_MAIN:return "main";
 case RISC_FAILURE_PHASE_FINI:return "finalize";
 case RISC_FAILURE_PHASE_CLEANUP:return "cleanup";
 case RISC_FAILURE_PHASE_HANDOFF:return "handoff";
 case RISC_FAILURE_PHASE_RETAINED:return "retained";
 case RISC_FAILURE_PHASE_IDLE:return "idle";
 default:return "unavailable";
 }
}

/* Match the OSD's literal-text treatment: non-ASCII/control bytes become
 * spaces, leading spaces and empty lines are omitted. Never scan past the
 * supplied copied-field bound, even if that field lacks a terminator. */
static inline bool failure_evidence_report_emit(failure_evidence_report_sink sink,
    void *context,const char *text,size_t bound) {
 char line[FAILURE_EVIDENCE_REPORT_LINE_CAPACITY];size_t used=0;
 if(bound>sizeof(line)-1)bound=sizeof(line)-1;
 for(size_t i=0;i<bound && text[i];++i) {
  unsigned char c=(unsigned char)text[i];if(c<32 || c>126)c=' ';
  if(!used && c==' ')continue;
  line[used++]=(char)c;
 }
 if(!used)return true;
 line[used]=0;return sink(context,line);
}

/* A caller supplies a fully copied v1 record, never a live crash stack. Failed
 * sinks stop emission immediately; false may mean a partial report was sent.
 * application/detail keep the same last-byte NUL bound as the OSD's copied
 * record, without mutating the input. Counts are bounded by their ABI arrays. */
static inline bool failure_evidence_report_format(const risc_failure_evidence_v1 *record,
    failure_evidence_report_sink sink,void *context) {
 if(!record || !sink || record->api_version!=RISC_FAILURE_EVIDENCE_API_V1 ||
    record->struct_size<sizeof(*record))return false;
 char line[128];
#define FAILURE_EVIDENCE_REPORT_TEXT(text) do { \
 if(!failure_evidence_report_emit(sink,context,(text),FAILURE_EVIDENCE_REPORT_LINE_CAPACITY-1))return false; \
 } while(0)
#define FAILURE_EVIDENCE_REPORT_FORMAT(...) do { \
 int length=snprintf(line,sizeof(line),__VA_ARGS__); \
 if(length<0 || (size_t)length>=sizeof(line))return false; \
 FAILURE_EVIDENCE_REPORT_TEXT(line); \
 } while(0)
 FAILURE_EVIDENCE_REPORT_TEXT(record->kind==RISC_FAILURE_NATIVE_PANIC?"Native crash recorded":
  record->kind==RISC_FAILURE_RETENTION?"Runtime stopped; restart was required":"Previous restart recorded");
 FAILURE_EVIDENCE_REPORT_FORMAT("Record: boot %lu / sequence %lu",(unsigned long)record->record_boot,(unsigned long)record->record_sequence);
 FAILURE_EVIDENCE_REPORT_FORMAT("This boot reset reason: %lu (raw)",(unsigned long)record->current_reset_reason);
 if(record->captured_reset_hint) {
  FAILURE_EVIDENCE_REPORT_FORMAT("Capture reset hint: %lu (raw)",(unsigned long)record->captured_reset_hint);
 }else FAILURE_EVIDENCE_REPORT_TEXT("Capture reset hint: unavailable");
 if(record->flags&RISC_FAILURE_CONTEXT) {
  FAILURE_EVIDENCE_REPORT_TEXT("LAST RUNTIME ACTIVITY (not fault attribution)");
  if(record->application[0]) {
   if(!failure_evidence_report_emit(sink,context,record->application,sizeof(record->application)-1))return false;
  }else FAILURE_EVIDENCE_REPORT_TEXT("Application: unavailable");
  FAILURE_EVIDENCE_REPORT_FORMAT("Phase: %s (%lu)",failure_evidence_report_phase(record->phase),(unsigned long)record->phase);
  FAILURE_EVIDENCE_REPORT_FORMAT("Invocation: %llu",(unsigned long long)record->invocation);
 }else FAILURE_EVIDENCE_REPORT_TEXT("Application / phase / invocation: unavailable");
 if(record->kind==RISC_FAILURE_RETENTION) {
  FAILURE_EVIDENCE_REPORT_FORMAT("Failure status: %ld",(long)record->status);
 }else FAILURE_EVIDENCE_REPORT_TEXT("Failure status: unavailable");
 if(record->detail[0]) {
  if(!failure_evidence_report_emit(sink,context,record->detail,sizeof(record->detail)-1))return false;
 }else FAILURE_EVIDENCE_REPORT_TEXT("Failure detail: unavailable");
 FAILURE_EVIDENCE_REPORT_TEXT("RECENT SEQUENCE (bounded saved history)");
 if(!record->history_count)FAILURE_EVIDENCE_REPORT_TEXT("Sequence history: unavailable");
 for(unsigned i=0;i<record->history_count && i<RISC_FAILURE_EVIDENCE_HISTORY;++i) {
  const risc_failure_step_v1 *step=&record->history[i];
  FAILURE_EVIDENCE_REPORT_FORMAT("%lu: %s / invocation %llu",(unsigned long)step->sequence,
   failure_evidence_report_phase(step->phase),(unsigned long long)step->invocation);
 }
 if(record->history_count>=RISC_FAILURE_EVIDENCE_HISTORY)FAILURE_EVIDENCE_REPORT_TEXT("History limited to 8 saved steps.");
 FAILURE_EVIDENCE_REPORT_TEXT("RAW PC / STACK (addresses, no symbols)");
 if(record->flags&RISC_FAILURE_REGISTERS) {
  FAILURE_EVIDENCE_REPORT_FORMAT("Exception PC %08lx  SP %08lx",(unsigned long)record->pc,(unsigned long)record->sp);
 }else FAILURE_EVIDENCE_REPORT_TEXT("Exception PC / SP: unavailable");
 const char *state=record->stack_status==RISC_FAILURE_STACK_COMPLETE?"Stack walk: complete":
  record->stack_status==RISC_FAILURE_STACK_LIMIT?"Stack truncated: frame limit reached":
  record->stack_status==RISC_FAILURE_STACK_INVALID?"Stack incomplete: invalid frame":
  record->stack_status==RISC_FAILURE_STACK_UNSUPPORTED?"Stack unavailable: unsupported capture":"Stack unavailable: not captured";
 FAILURE_EVIDENCE_REPORT_TEXT(state);
 for(unsigned i=0;i<record->frame_count && i<RISC_FAILURE_EVIDENCE_FRAMES;++i) {
  FAILURE_EVIDENCE_REPORT_FORMAT("#%u PC %08lx  SP %08lx",i,(unsigned long)record->frames[i].pc,(unsigned long)record->frames[i].sp);
 }
 if(record->frame_count>RISC_FAILURE_EVIDENCE_FRAMES)FAILURE_EVIDENCE_REPORT_TEXT("Reported frames exceed capacity; truncated.");
 FAILURE_EVIDENCE_REPORT_TEXT("Evidence may not survive power loss.");
#undef FAILURE_EVIDENCE_REPORT_FORMAT
#undef FAILURE_EVIDENCE_REPORT_TEXT
 return true;
}
