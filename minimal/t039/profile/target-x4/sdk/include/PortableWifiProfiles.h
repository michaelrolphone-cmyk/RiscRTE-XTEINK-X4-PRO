#pragma once
/* Growing network collection using the existing per-profile atomic codec.
 * Slot zero keeps the original five keys/default. Other slots have independent
 * selectors. A checked count reserves each new slot before its credential save;
 * an interrupted save leaves a reusable empty slot, never an orphan authority.
 * Only actual storage failure or the 32-bit index space limits the collection.
 * Callers serialize writes under namespace 6 and checked radio cleanup. */
#include "PortableWifiCredentials.h"
#define PORTABLE_WIFI_PROFILE_PAGE 8u
#define PORTABLE_WIFI_PROFILE_AGAIN PORTABLE_WIFI_CREDENTIALS_AGAIN
#define PORTABLE_WIFI_PROFILE_COUNT_KEY "wifi.profiles"
#define PORTABLE_WIFI_PROFILE_FULL 6

typedef struct {
    const risc_key_value_v1 *source;
    unsigned index;
} portable_wifi_profile_context;

static inline bool portable_wifi_profile_key(uint32_t index,const char *key,char out[16]) {
    if(!key)return false;
    for(unsigned i=0;i<5;i++)if(key[i]!="wifi."[i])return false;
    size_t n=0;while(n<15&&key[n])++n;
    if(n==15)return false;
    if(!index){memcpy(out,key,n+1);return true;}
    static const char hex[]="0123456789abcdef";
    out[0]='w';for(unsigned i=0;i<8;i++)out[1+i]=hex[(index>>(28-4*i))&15u];
    out[9]='.';
    if(!strcmp(key+5,"commit")){out[10]='c';out[11]=0;}
    else {if(n!=7)return false;out[10]=key[5];out[11]=key[6];out[12]=0;}
    return true;
}
/* Absent metadata is the exact legacy single-profile layout. Reads never
 * migrate or write. A corrupt count is not a reason to invent an empty store. */
static inline int portable_wifi_profile_count(const risc_key_value_v1 *kv,uint32_t *out) {
    if(!out)return PORTABLE_WIFI_CREDENTIALS_INVALID;
    *out=0;
    if(!portable_wifi_credentials_api_valid(kv))return PORTABLE_WIFI_CREDENTIALS_UNAVAILABLE;
    uint8_t data[32]={0};int rc=portable_wifi_credentials_read_blob(kv,PORTABLE_WIFI_PROFILE_COUNT_KEY,data,sizeof(data));
    if(rc==PORTABLE_WIFI_CREDENTIALS_EMPTY){*out=1;return PORTABLE_WIFI_CREDENTIALS_LOADED;}
    if(rc!=PORTABLE_WIFI_CREDENTIALS_LOADED)return rc;
    if(memcmp(data,"WFN1",4)||data[4]!=1||data[5]||data[6]||data[7]||
       !portable_wifi_credentials_u32(data+8)||portable_wifi_credentials_u32(data+28)!=portable_wifi_credentials_crc(data,28))return PORTABLE_WIFI_CREDENTIALS_INVALID;
    for(unsigned i=12;i<28;i++)if(data[i])return PORTABLE_WIFI_CREDENTIALS_INVALID;
    *out=portable_wifi_credentials_u32(data+8);return PORTABLE_WIFI_CREDENTIALS_LOADED;
}
static inline int portable_wifi_profile_reserve(const risc_key_value_v1 *kv,uint32_t index) {
    uint32_t count=0;int rc=portable_wifi_profile_count(kv,&count);if(rc)return rc;
    if(index<count)return PORTABLE_WIFI_CREDENTIALS_LOADED;
    if(index!=count)return PORTABLE_WIFI_CREDENTIALS_INVALID;
    if(count==UINT32_MAX)return PORTABLE_WIFI_PROFILE_FULL;
    uint8_t data[32]={0};memcpy(data,"WFN1",4);data[4]=1;
    portable_wifi_credentials_put_u32(data+8,count+1);
    portable_wifi_credentials_put_u32(data+28,portable_wifi_credentials_crc(data,28));
    return portable_wifi_credentials_write_status(kv,PORTABLE_WIFI_PROFILE_COUNT_KEY,data,sizeof(data));
}
static inline int32_t portable_wifi_profile_get(void *context,const char *key,void *data,uint32_t capacity,uint32_t *size) {
    portable_wifi_profile_context *c=context;char mapped[16];
    if(!portable_wifi_profile_key(c->index,key,mapped)){if(size)*size=0;return RISC_KEY_VALUE_INVALID;}
    return c->source->get(c->source->context,mapped,data,capacity,size);
}
static inline int32_t portable_wifi_profile_put(void *context,const char *key,const void *data,uint32_t size) {
    portable_wifi_profile_context *c=context;char mapped[16];
    if(!portable_wifi_profile_key(c->index,key,mapped))return RISC_KEY_VALUE_INVALID;
    return c->source->put(c->source->context,mapped,data,size);
}
static inline risc_key_value_v1 portable_wifi_profile_api(portable_wifi_profile_context *c) {
    return (risc_key_value_v1){1,sizeof(risc_key_value_v1),c,portable_wifi_profile_get,portable_wifi_profile_put};
}
static inline int portable_wifi_profile_load(const risc_key_value_v1 *kv,unsigned index,portable_wifi_credentials *out) {
    if(!out)return PORTABLE_WIFI_CREDENTIALS_INVALID;
    portable_wifi_credentials_clear(out);
    if(!portable_wifi_credentials_api_valid(kv))return PORTABLE_WIFI_CREDENTIALS_UNAVAILABLE;
    portable_wifi_profile_context c={kv,index};risc_key_value_v1 selected=portable_wifi_profile_api(&c);
    return portable_wifi_credentials_load(&selected,out);
}
static inline int portable_wifi_profile_save(const risc_key_value_v1 *kv,unsigned index,const portable_wifi_credentials *value) {
    if(!portable_wifi_credentials_validate(value))return PORTABLE_WIFI_CREDENTIALS_INVALID;
    int reserved=portable_wifi_profile_reserve(kv,index);if(reserved)return reserved;
    if(!portable_wifi_credentials_api_valid(kv))return PORTABLE_WIFI_CREDENTIALS_UNAVAILABLE;
    portable_wifi_profile_context c={kv,index};risc_key_value_v1 selected=portable_wifi_profile_api(&c);
    return portable_wifi_credentials_save(&selected,value);
}
static inline int portable_wifi_profile_forget(const risc_key_value_v1 *kv,unsigned index) {
    if(!portable_wifi_credentials_api_valid(kv))return PORTABLE_WIFI_CREDENTIALS_UNAVAILABLE;
    portable_wifi_profile_context c={kv,index};risc_key_value_v1 selected=portable_wifi_profile_api(&c);
    return portable_wifi_credentials_forget(&selected);
}
/* Search performs at most one profile read per step. The application yields,
 * accepts cancellation and presents progress between steps, even when storage
 * contains many profiles. No credentials are kept in the search state. */
typedef struct {
    uint32_t count,next,empty,index;
    int fault,result;
    bool done,initialized;
    char ssid[33];
} portable_wifi_profile_search;
static inline int portable_wifi_profile_search_begin(const risc_key_value_v1 *kv,const char *ssid,portable_wifi_profile_search *search) {
    if(!ssid||!search)return PORTABLE_WIFI_CREDENTIALS_INVALID;
    memset(search,0,sizeof(*search));search->empty=UINT32_MAX;
    unsigned n=0;while(n<sizeof(search->ssid)&&ssid[n])++n;
    if(!n||n==sizeof(search->ssid))return PORTABLE_WIFI_CREDENTIALS_INVALID;
    memcpy(search->ssid,ssid,n);int rc=portable_wifi_profile_count(kv,&search->count);
    if(rc==PORTABLE_WIFI_CREDENTIALS_AGAIN)return rc;
    if(rc){search->done=true;search->result=rc;return rc;}
    search->initialized=true;
    return PORTABLE_WIFI_PROFILE_AGAIN;
}
static inline int portable_wifi_profile_search_step(const risc_key_value_v1 *kv,portable_wifi_profile_search *search) {
    if(!search)return PORTABLE_WIFI_CREDENTIALS_INVALID;
    if(search->done)return search->result;
    if(!search->initialized){
        int rc=portable_wifi_profile_count(kv,&search->count);
        if(rc==PORTABLE_WIFI_CREDENTIALS_AGAIN)return rc;
        if(rc){search->done=true;return search->result=rc;}
        search->initialized=true;
    }
    if(search->next<search->count){
        uint32_t i=search->next;portable_wifi_credentials value={{0},{0}};
        int rc=portable_wifi_profile_load(kv,i,&value);
        bool same=rc==PORTABLE_WIFI_CREDENTIALS_LOADED&&!strcmp(value.ssid,search->ssid);
        portable_wifi_credentials_clear(&value);
        if(rc==PORTABLE_WIFI_CREDENTIALS_AGAIN)return rc;
        ++search->next;
        if(same){search->index=i;search->done=true;return search->result=PORTABLE_WIFI_CREDENTIALS_LOADED;}
        if(rc==PORTABLE_WIFI_CREDENTIALS_EMPTY&&search->empty==UINT32_MAX)search->empty=i;
        else if(rc!=PORTABLE_WIFI_CREDENTIALS_EMPTY&&rc!=PORTABLE_WIFI_CREDENTIALS_LOADED)search->fault=rc;
    }
    if(search->next<search->count)return PORTABLE_WIFI_PROFILE_AGAIN;
    search->done=true;
    if(search->fault)return search->result=search->fault;
    search->index=search->empty!=UINT32_MAX?search->empty:search->count;
    if(search->index==UINT32_MAX)return search->result=PORTABLE_WIFI_PROFILE_FULL;
    return search->result=PORTABLE_WIFI_CREDENTIALS_EMPTY;
}
