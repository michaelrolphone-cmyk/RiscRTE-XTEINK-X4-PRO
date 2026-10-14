#pragma once
#include "RiscRuntimeV1.h"
#include "RiscTextEntryV1.h"
#include "PortableTextInputHandoff.h"
#include <string.h>
/* One bounded host session; there is no app keyboard, HID subscription, saved
 * caller buffer or callback. Only copied requests/results cross the ABI. */
typedef struct {
    const risc_runtime_api_v1 *runtime;
    const risc_text_entry_api_v1 *api;
    risc_runtime_capability_v1 grant;
    uint64_t session;
    uint32_t capacity;
    bool active, acquired, suspended, closing, retained, home_reason;
} portable_text_client;
static inline int portable_text_client_retain(portable_text_client *c) {
    c->retained=true;portable_text_adapter_retain();return RISC_TEXT_ENTRY_RETAINED;
}
static inline bool portable_text_client_live(portable_text_client *c) {
    if(c->retained)return false;
    if(portable_text_adapter_retained()){c->retained=true;return false;}
    if(c->runtime&&!risc_runtime_get_api(1)){(void)portable_text_client_retain(c);return false;}
    return true;
}
static inline int portable_text_client_release(portable_text_client *c) {
    if(!portable_text_client_live(c))return RISC_TEXT_ENTRY_RETAINED;
    if(c->acquired) {
        risc_runtime_capability_v1 released=c->grant;
        bool ok=c->runtime->release(&released);
        if(!portable_text_client_live(c))return RISC_TEXT_ENTRY_RETAINED;
        if(!ok||released.struct_size!=sizeof(released)||released.api||released.slot||released.generation)return portable_text_client_retain(c);
        c->grant=released;c->api=NULL;c->acquired=false;
    }
    if(c->suspended) {
        if(portable_text_adapter_resume()!=RISC_TEXT_ENTRY_OK)return portable_text_client_retain(c);
        c->suspended=false;
    }
    c->closing=false;return RISC_TEXT_ENTRY_OK;
}
/* Clear the bounded copied request on every exit, including rejected suffixes
 * and retained callbacks. This is local memory cleanup, never provider I/O. */
static inline int portable_text_client_request_result(risc_text_entry_request_v1 *request,int result) {
    volatile unsigned char *p=(volatile unsigned char*)request;
    for(size_t i=0;i<sizeof(*request);++i)p[i]=0;
    return result;
}
static inline int portable_text_client_begin_mode(portable_text_client *c,const risc_runtime_api_v1 *runtime,
                                            const char *label,const char *initial,uint32_t capacity,bool masked) {
    if(!c||!portable_text_client_live(c))return RISC_TEXT_ENTRY_RETAINED;
    if(c->active||c->acquired||c->suspended)return RISC_TEXT_ENTRY_BUSY;
    if(!runtime||!runtime->acquire||!runtime->release||!label||!initial||!capacity||capacity>RISC_TEXT_ENTRY_BYTES)return RISC_TEXT_ENTRY_INVALID;
    risc_text_entry_request_v1 request={.api_version=1,.struct_size=sizeof(request),.capacity=capacity};
    unsigned n=0;for(;n<RISC_TEXT_ENTRY_LABEL&&label[n];n++){if((unsigned char)label[n]<32||(unsigned char)label[n]>126)return portable_text_client_request_result(&request,RISC_TEXT_ENTRY_INVALID);request.label[n]=label[n];}
    if(n==RISC_TEXT_ENTRY_LABEL)return portable_text_client_request_result(&request,RISC_TEXT_ENTRY_INVALID);
    for(n=0;n<capacity&&initial[n];n++){if((unsigned char)initial[n]<32||(unsigned char)initial[n]>126)return portable_text_client_request_result(&request,RISC_TEXT_ENTRY_INVALID);request.text[n]=initial[n];}
    if(n==capacity)return portable_text_client_request_result(&request,RISC_TEXT_ENTRY_INVALID);
    c->runtime=runtime;c->capacity=capacity;c->grant=(risc_runtime_capability_v1){.struct_size=sizeof(c->grant)};
    bool acquired=runtime->acquire(RISC_TEXT_ENTRY_CAPABILITY,1,0,&c->grant);
    if(!portable_text_client_live(c))return portable_text_client_request_result(&request,RISC_TEXT_ENTRY_RETAINED);
    if(!acquired){if(c->grant.struct_size!=sizeof(c->grant)||c->grant.api||c->grant.slot||c->grant.generation)return portable_text_client_request_result(&request,portable_text_client_retain(c));return portable_text_client_request_result(&request,RISC_TEXT_ENTRY_UNAVAILABLE);}
    if(c->grant.struct_size!=sizeof(c->grant)||!c->grant.api||!c->grant.slot||!c->grant.generation)return portable_text_client_request_result(&request,portable_text_client_retain(c));
    c->acquired=true;c->api=c->grant.api;
    if(c->api->api_version!=1||c->api->struct_size<sizeof(*c->api)||!c->api->open||!c->api->poll||!c->api->close) {
        int closed=portable_text_client_release(c);return portable_text_client_request_result(&request,closed==RISC_TEXT_ENTRY_OK?RISC_TEXT_ENTRY_UNAVAILABLE:closed);
    }
    if(masked&&!risc_text_entry_masked(c->api)){
        int closed=portable_text_client_release(c);return portable_text_client_request_result(&request,closed==RISC_TEXT_ENTRY_OK?RISC_TEXT_ENTRY_UNAVAILABLE:closed);
    }
    c->home_reason=risc_text_entry_home_reason(c->api);
    if(c->home_reason)request.reserved=RISC_TEXT_ENTRY_REQUEST_HOME_REASON;
    if(masked)request.reserved|=RISC_TEXT_ENTRY_REQUEST_MASKED;
    int rc=portable_text_adapter_suspend();
    if(rc!=RISC_TEXT_ENTRY_OK){if(rc==RISC_TEXT_ENTRY_RETAINED)return portable_text_client_request_result(&request,portable_text_client_retain(c));int closed=portable_text_client_release(c);return portable_text_client_request_result(&request,closed==RISC_TEXT_ENTRY_OK?rc:closed);}
    c->suspended=true;c->session=0;
    rc=c->api->open(c->api->context,&request,&c->session);
    if(rc==RISC_TEXT_ENTRY_RETAINED)return portable_text_client_request_result(&request,portable_text_client_retain(c));
    if(!portable_text_client_live(c))return portable_text_client_request_result(&request,RISC_TEXT_ENTRY_RETAINED);
    if(rc==RISC_TEXT_ENTRY_OK&&c->session){c->active=true;return portable_text_client_request_result(&request,RISC_TEXT_ENTRY_OK);}
    if(c->session||(rc!=RISC_TEXT_ENTRY_UNAVAILABLE&&rc!=RISC_TEXT_ENTRY_BUSY&&rc!=RISC_TEXT_ENTRY_INVALID))return portable_text_client_request_result(&request,portable_text_client_retain(c));
    int closed=portable_text_client_release(c);return portable_text_client_request_result(&request,closed==RISC_TEXT_ENTRY_OK?rc:closed);
}
static inline int portable_text_client_begin(portable_text_client *c,const risc_runtime_api_v1 *runtime,
                                            const char *label,const char *initial,uint32_t capacity) {
    return portable_text_client_begin_mode(c,runtime,label,initial,capacity,false);
}
static inline int portable_text_client_state_result(risc_text_entry_state_v1 *state,int result) {
    volatile unsigned char *p=(volatile unsigned char*)state;
    for(size_t i=0;i<sizeof(*state);++i)p[i]=0;
    return result;
}
static inline int portable_text_client_poll(portable_text_client *c,risc_text_entry_state_v1 *out) {
    if(!c||!out)return RISC_TEXT_ENTRY_INVALID;
    if(!portable_text_client_live(c))return RISC_TEXT_ENTRY_RETAINED;
    if(!c->active)return RISC_TEXT_ENTRY_STALE;
    if(c->closing)return RISC_TEXT_ENTRY_AGAIN;
    risc_text_entry_state_v1 state={.struct_size=sizeof(state)};
    int rc=c->api->poll(c->api->context,c->session,&state);
    if(rc==RISC_TEXT_ENTRY_RETAINED)return portable_text_client_state_result(&state,portable_text_client_retain(c));
    if(!portable_text_client_live(c))return portable_text_client_state_result(&state,RISC_TEXT_ENTRY_RETAINED);
    if(rc==RISC_TEXT_ENTRY_AGAIN)return portable_text_client_state_result(&state,rc);
    if(rc!=RISC_TEXT_ENTRY_OK||state.struct_size<sizeof(state)||!state.revision||
       (state.flags&~(RISC_TEXT_ENTRY_HARDWARE|RISC_TEXT_ENTRY_PRESENTING|(c->home_reason?RISC_TEXT_ENTRY_HOME_CANCEL:0u)))||state.state>RISC_TEXT_ENTRY_CANCELLED||
       ((state.flags&RISC_TEXT_ENTRY_HOME_CANCEL)&&state.state!=RISC_TEXT_ENTRY_CANCELLED)||
       !memchr(state.text,0,c->capacity))return portable_text_client_state_result(&state,portable_text_client_retain(c));
    for(unsigned i=0;state.text[i];i++)if((unsigned char)state.text[i]<32||(unsigned char)state.text[i]>126)return portable_text_client_state_result(&state,portable_text_client_retain(c));
    /* Logical attention is independent; close settles the owned frame. */
    int attention=portable_text_adapter_attention();
    if(attention<0)return portable_text_client_state_result(&state,portable_text_client_retain(c));
    if(attention)state.state=RISC_TEXT_ENTRY_CANCELLED;
    *out=state;return portable_text_client_state_result(&state,RISC_TEXT_ENTRY_OK);
}
static inline int portable_text_client_close(portable_text_client *c) {
    if(!c||!portable_text_client_live(c))return RISC_TEXT_ENTRY_RETAINED;
    if(c->active) {
        c->closing=true;
        int rc=c->api->close(c->api->context,c->session);
        if(rc==RISC_TEXT_ENTRY_RETAINED)return portable_text_client_retain(c);
        if(!portable_text_client_live(c))return RISC_TEXT_ENTRY_RETAINED;
        if(rc==RISC_TEXT_ENTRY_AGAIN)return rc;
        if(rc!=RISC_TEXT_ENTRY_OK)return portable_text_client_retain(c);
        c->session=0;c->active=false;
    }
    return portable_text_client_release(c);
}
