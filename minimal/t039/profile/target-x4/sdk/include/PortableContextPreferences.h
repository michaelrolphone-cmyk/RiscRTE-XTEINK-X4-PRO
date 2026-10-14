#pragma once
/* App-owned namespace-1 preferences. Contexts stores no hardware pointers and
 * never writes a default merely because a key is absent. Each room preset is
 * one verified 64-byte record, so an interrupted save cannot mix its fields. */
#include "PortableQuickPreferences.h"
#include "PortableSleepPolicy.h"
#include "PortableAlarmSettings.h"
#include <string.h>
#define PORTABLE_CONTEXT_PRESETS 8u
#define PORTABLE_CONTEXT_NAME_MAX 16u
#define PORTABLE_CONTEXT_ENABLED_KEY "contexts_on"
#define PORTABLE_CONTEXT_RECORD_BYTES 64u
enum {
    PORTABLE_CONTEXT_SLEEP=1u, PORTABLE_CONTEXT_IDLE=2u,
    PORTABLE_CONTEXT_DEEP=4u, PORTABLE_CONTEXT_BRIGHTNESS=8u,
    PORTABLE_CONTEXT_VOLUME=16u, PORTABLE_CONTEXT_DND=32u,
    PORTABLE_CONTEXT_ALERT=64u, PORTABLE_CONTEXT_FACE=128u,
    PORTABLE_CONTEXT_ACTIONS=255u
};
enum { PORTABLE_CONTEXT_EMPTY=0, PORTABLE_CONTEXT_AUDIO=1, PORTABLE_CONTEXT_RF=2 };
typedef struct {
    char name[PORTABLE_CONTEXT_NAME_MAX+1u];
    uint32_t idle_ms,deep_ms;
    uint16_t actions;
    uint8_t source,slot,face,brightness,volume,alert,sleep;
    bool enabled,dnd;
} portable_context_preset;
static inline void portable_context_preset_init(portable_context_preset *p) {
    memset(p,0,sizeof(*p));p->idle_ms=PORTABLE_SLEEP_IDLE_MS;p->deep_ms=PORTABLE_SLEEP_LIGHT_MS;
    p->brightness=PQA_BRIGHTNESS_DEFAULT;p->volume=PQA_VOLUME_DEFAULT;
    p->alert=PORTABLE_ALERT_VIBRATE;p->sleep=PORTABLE_SLEEP_HYBRID;
}
static inline bool portable_context_name_valid(const char name[17]) {
    if(!name||!name[0])return false;
    for(unsigned i=0;i<=PORTABLE_CONTEXT_NAME_MAX;i++) {
        if(!name[i])return true;
        if(i==PORTABLE_CONTEXT_NAME_MAX||(unsigned char)name[i]<32u||(unsigned char)name[i]>126u)return false;
    }
    return false;
}
static inline bool portable_context_preset_valid(const portable_context_preset *p) {
    if(!p||p->source>PORTABLE_CONTEXT_RF||p->slot>=8u||(p->actions&~PORTABLE_CONTEXT_ACTIONS)||
       p->brightness<10u||p->brightness>100u||p->volume>100u||
       p->alert<PORTABLE_ALERT_VIBRATE||p->alert>PORTABLE_ALERT_BOTH||p->sleep>PORTABLE_SLEEP_HYBRID||
       p->idle_ms<5000u||p->idle_ms>3600000u||p->idle_ms%1000u||
       p->deep_ms<60000u||p->deep_ms>3600000u||p->deep_ms%1000u)return false;
    if(p->source==PORTABLE_CONTEXT_EMPTY)return !p->enabled&&!p->actions&&!p->name[0];
    return portable_context_name_valid(p->name)&&(!p->enabled||p->actions);
}
static inline uint32_t portable_context_crc(const uint8_t *p,unsigned size) {
    uint32_t crc=UINT32_MAX;
    for(unsigned i=0;i<size;i++) {crc^=p[i];for(unsigned b=0;b<8;b++)crc=(crc>>1)^((0u-(crc&1u))&UINT32_C(0xedb88320));}
    return ~crc;
}
static inline void portable_context_u32_put(uint8_t *b,uint32_t value) {
    for(unsigned i=0;i<4;i++)b[i]=(uint8_t)(value>>(i*8));
}
static inline uint32_t portable_context_u32_get(const uint8_t *b) {
    return (uint32_t)b[0]|((uint32_t)b[1]<<8)|((uint32_t)b[2]<<16)|((uint32_t)b[3]<<24);
}
static inline bool portable_context_preset_encode(const portable_context_preset *p,uint8_t out[64]) {
    if(!out||!portable_context_preset_valid(p))return false;
    memset(out,0,64);out[0]='C';out[1]='T';out[2]='P';out[3]=1;
    out[4]=p->enabled;out[5]=p->source;out[6]=p->slot;out[7]=p->face;
    out[8]=p->brightness;out[9]=p->volume;out[10]=p->dnd;out[11]=p->alert;out[12]=p->sleep;
    out[14]=(uint8_t)p->actions;out[15]=(uint8_t)(p->actions>>8);
    portable_context_u32_put(out+16,p->idle_ms);portable_context_u32_put(out+20,p->deep_ms);
    for(unsigned i=0;i<16&&p->name[i];i++)out[24+i]=(uint8_t)p->name[i];
    portable_context_u32_put(out+60,portable_context_crc(out,60));return true;
}
static inline bool portable_context_preset_decode(portable_context_preset *p,const uint8_t *in,uint32_t size) {
    if(!p||!in||size!=64||in[0]!='C'||in[1]!='T'||in[2]!='P'||in[3]!=1||
       in[4]>1||in[10]>1||in[13]||portable_context_u32_get(in+60)!=portable_context_crc(in,60))return false;
    for(unsigned i=40;i<60;i++)if(in[i])return false;
    bool ended=false;for(unsigned i=24;i<40;i++){if(!in[i])ended=true;else if(ended)return false;}
    portable_context_preset next;portable_context_preset_init(&next);
    next.enabled=in[4]!=0;next.source=in[5];next.slot=in[6];next.face=in[7];
    next.brightness=in[8];next.volume=in[9];next.dnd=in[10]!=0;next.alert=in[11];next.sleep=in[12];
    next.actions=(uint16_t)((unsigned)in[14]|((unsigned)in[15]<<8));
    next.idle_ms=portable_context_u32_get(in+16);next.deep_ms=portable_context_u32_get(in+20);
    memcpy(next.name,in+24,16);next.name[16]=0;
    if(!portable_context_preset_valid(&next))return false;
    *p=next;return true;
}
static inline bool portable_context_preset_key(unsigned slot,char out[8]) {
    if(slot>=PORTABLE_CONTEXT_PRESETS)return false;
    memcpy(out,"ctx_p0",7);out[5]=(char)('0'+slot);return true;
}
static inline int32_t portable_context_preset_load(const risc_key_value_v1 *kv,unsigned slot,portable_context_preset *out) {
    if(!out)return RISC_KEY_VALUE_INVALID;
    portable_context_preset_init(out);char key[8];
    if(!portable_context_preset_key(slot,key))return RISC_KEY_VALUE_INVALID;
    if(!pqa_preferences_valid(kv))return RISC_KEY_VALUE_CONTEXT;
    uint8_t bytes[64];uint32_t n=0;int32_t result=kv->get(kv->context,key,bytes,sizeof(bytes),&n);
    if(result!=RISC_KEY_VALUE_OK)return result;
    return portable_context_preset_decode(out,bytes,n)?RISC_KEY_VALUE_OK:RISC_KEY_VALUE_INVALID;
}
static inline bool portable_context_preset_save(const risc_key_value_v1 *kv,unsigned slot,const portable_context_preset *p) {
    char key[8];uint8_t bytes[64],actual[64];uint32_t n=0;
    if(!pqa_preferences_valid(kv)||!portable_context_preset_key(slot,key)||!portable_context_preset_encode(p,bytes))return false;
    if(kv->get(kv->context,key,actual,sizeof(actual),&n)==RISC_KEY_VALUE_OK&&n==64&&!memcmp(actual,bytes,64))return true;
    int32_t result=kv->put(kv->context,key,bytes,64);
    return (result==RISC_KEY_VALUE_OK||result==RISC_KEY_VALUE_IO)&&
        kv->get(kv->context,key,actual,sizeof(actual),&n)==RISC_KEY_VALUE_OK&&n==64&&!memcmp(actual,bytes,64);
}
static inline bool portable_context_enabled_load(const risc_key_value_v1 *kv,bool *enabled) {
    if(!enabled)return false;
    *enabled=false;if(!pqa_preferences_valid(kv))return false;
    uint8_t bytes[4];uint32_t n=0;int32_t result=kv->get(kv->context,PORTABLE_CONTEXT_ENABLED_KEY,bytes,sizeof(bytes),&n);
    if(result==RISC_KEY_VALUE_NOT_FOUND)return true;
    if(result!=RISC_KEY_VALUE_OK||n!=4||bytes[0]!='C'||bytes[1]!=1||bytes[2]>1||bytes[3]!=(uint8_t)(bytes[2]^0xa5u))return false;
    *enabled=bytes[2]!=0;return true;
}
static inline bool portable_context_enabled_save(const risc_key_value_v1 *kv,bool enabled) {
    if(!pqa_preferences_valid(kv))return false;
    const uint8_t bytes[]={'C',1,enabled?1:0,(uint8_t)((enabled?1:0)^0xa5u)};
    int32_t result=kv->put(kv->context,PORTABLE_CONTEXT_ENABLED_KEY,bytes,sizeof(bytes));bool actual=false;
    return (result==RISC_KEY_VALUE_OK||result==RISC_KEY_VALUE_IO)&&portable_context_enabled_load(kv,&actual)&&actual==enabled;
}
/* Match all identity fields. Replacing, deleting or renaming a saved model must
 * not accidentally inherit automation from a prior occupant of its slot. */
static inline bool portable_context_preset_matches(const portable_context_preset *p,unsigned source,unsigned slot,const char *name) {
    return portable_context_preset_valid(p)&&p->enabled&&p->source==source&&p->slot==slot&&name&&
        !strncmp(p->name,name,17);
}
