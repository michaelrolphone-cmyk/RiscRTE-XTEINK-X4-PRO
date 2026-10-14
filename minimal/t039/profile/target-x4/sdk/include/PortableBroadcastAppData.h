#pragma once
#include "RiscAppDataV1.h"
#include "RiscRuntimeV1.h"
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
#ifdef PORTABLE_NATIVE_TIME_TOOLBAR
#include "PortableNativeCustody.h"
#endif
/* App-local lifecycle fence. Stop advertising BEFORE any app-data call that
 * can retain the invocation. After RETAINED there is no radio or storage I/O.
 * Original outcomes, expected revisions, bytes and authority are unchanged. */
#include "PortableBackgroundServices.h"
#if !defined(PORTABLE_CONTEXTS_CLIENT) && !defined(PORTABLE_BLE_BROADCAST)
/* Preserve the original explicit fence API for consumers predating feature
 * defines; the helper historically always required a broadcast stop hook. */
bool portable_broadcast_stop(void);
#endif
static inline bool portable_broadcast_data_stop(void) {
#if defined(PORTABLE_CONTEXTS_CLIENT) || defined(PORTABLE_BLE_BROADCAST)
    return portable_background_stop();
#else
    return portable_broadcast_stop();
#endif
}

typedef struct {
    risc_app_data_v1 api;
    const risc_app_data_v1 *source;
    const risc_runtime_api_v1 *runtime;
    bool retained;
} portable_broadcast_app_data;
static inline int32_t portable_broadcast_data_result(portable_broadcast_app_data *s,int32_t result) {
    if(result==RISC_APP_DATA_RETAINED)s->retained=true;
    return result;
}
static inline bool portable_broadcast_data_ready(portable_broadcast_app_data *s) {
    if(s->retained)return false;
#ifdef PORTABLE_NATIVE_TIME_TOOLBAR
    if(portable_adapter_retained()){s->retained=true;return false;}
#endif
    /* Do not synthesize a backend RETAINED result: without the backend fence
     * Runtime could finalize. This invocation remains inside cleanup instead. */
    while(!portable_broadcast_data_stop()) {
#ifdef PORTABLE_NATIVE_TIME_TOOLBAR
        if(portable_adapter_retained()){s->retained=true;return false;}
#endif
        /* Runtime 0.1.54 appends a terminal invocation fence after boot
         * confirmation. A clean size check keeps the frozen ABI prefix valid. */
        bool (*retain)(void)=NULL;
        const size_t offset=RISC_RUNTIME_CAPABILITIES_V1_SIZE+sizeof(bool (*)(void));
        if(s->runtime->struct_size>=offset+sizeof(retain)) {
            memcpy(&retain,(const unsigned char*)s->runtime+offset,sizeof(retain));
            if(retain && retain()){s->retained=true;return false;}
        }
        /* Historical tables have no fence; keep this app's stack alive and
         * allow only the same cleanup retry before any storage operation. */
        s->runtime->yield_ms(50);
    }
    return true;
}
static inline int32_t portable_broadcast_data_stat(void *context,const char *name,uint32_t *size,uint64_t *revision) {
    portable_broadcast_app_data *s=context;
    if(!portable_broadcast_data_ready(s)){if(size)*size=0;if(revision)*revision=0;return RISC_APP_DATA_RETAINED;}
    return portable_broadcast_data_result(s,s->source->stat(s->source->context,name,size,revision));
}
static inline int32_t portable_broadcast_data_read(void *context,const char *name,uint64_t expected,void *buffer,uint32_t capacity,uint32_t *size,uint64_t *revision) {
    portable_broadcast_app_data *s=context;
    if(!portable_broadcast_data_ready(s)){if(size)*size=0;if(revision)*revision=0;return RISC_APP_DATA_RETAINED;}
    return portable_broadcast_data_result(s,s->source->read(s->source->context,name,expected,buffer,capacity,size,revision));
}
static inline int32_t portable_broadcast_data_replace(void *context,const char *name,uint64_t expected,const void *bytes,uint32_t size) {
    portable_broadcast_app_data *s=context;
    if(!portable_broadcast_data_ready(s))return RISC_APP_DATA_RETAINED;
    return portable_broadcast_data_result(s,s->source->replace(s->source->context,name,expected,bytes,size));
}
static inline const risc_app_data_v1 *portable_broadcast_data_bind(portable_broadcast_app_data *s,const risc_app_data_v1 *source,const risc_runtime_api_v1 *runtime) {
    if(!s||!runtime||runtime->api_version!=1||runtime->struct_size<RISC_RUNTIME_CAPABILITIES_V1_SIZE||!runtime->yield_ms||!source||source->api_version!=1||source->struct_size<sizeof(*source)||!source->stat||!source->read||!source->replace)return NULL;
    *s=(portable_broadcast_app_data){.source=source,.runtime=runtime,.api={1,sizeof(risc_app_data_v1),s,portable_broadcast_data_stat,portable_broadcast_data_read,portable_broadcast_data_replace}};
    return &s->api;
}
