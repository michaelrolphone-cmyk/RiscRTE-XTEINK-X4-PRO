#pragma once
/* App-owned interpretation metadata for a calendar RTC. This is not clock
 * calibration or chip-layout selection. Callers own an explicit namespace-1
 * key-value grant; reads never repair storage or set either clock. */
#include "RiscKeyValueV1.h"
#include <stdbool.h>
#include <stdint.h>
#define PORTABLE_RTC_BASIS_KEY "rtc_basis"
#define PORTABLE_RTC_BASIS_INSTANCE 1u
#define PORTABLE_RTC_BASIS_BYTES 12u
#define PORTABLE_RTC_BASIS_MIN_REFERENCE UINT32_C(946684800)
#define PORTABLE_RTC_BASIS_MAX_REFERENCE UINT32_C(4102444799)
typedef struct { bool stores_utc; uint32_t reference_epoch; } portable_rtc_basis;
enum { PORTABLE_RTC_BASIS_LOADED=0, PORTABLE_RTC_BASIS_MISSING=1,
       PORTABLE_RTC_BASIS_INVALID=2, PORTABLE_RTC_BASIS_UNAVAILABLE=3 };
enum { PORTABLE_RTC_BASIS_SAVED=0, PORTABLE_RTC_BASIS_UNCHANGED=1,
       PORTABLE_RTC_BASIS_BAD_VALUE=-1, PORTABLE_RTC_BASIS_NO_STORAGE=-2,
       PORTABLE_RTC_BASIS_WRITE_FAILED=-3, PORTABLE_RTC_BASIS_VERIFY_FAILED=-4 };
static inline uint32_t portable_rtc_basis_word(const uint8_t *p) {
 return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;
}
static inline void portable_rtc_basis_put_word(uint8_t *p,uint32_t value) {
 for(unsigned i=0;i<4;++i)p[i]=(uint8_t)(value>>(i*8));
}
static inline uint32_t portable_rtc_basis_check(const uint8_t *p) {
 uint32_t value=UINT32_C(2166136261);
 for(unsigned i=0;i<8;++i){value^=p[i];value*=UINT32_C(16777619);}return value;
}
static inline bool portable_rtc_basis_valid(const portable_rtc_basis *value) {
 return value && (!value->reference_epoch || (value->reference_epoch>=PORTABLE_RTC_BASIS_MIN_REFERENCE &&
        value->reference_epoch<=PORTABLE_RTC_BASIS_MAX_REFERENCE));
}
static inline bool portable_rtc_basis_api(const risc_key_value_v1 *kv) {
 return kv && kv->api_version==RISC_KEY_VALUE_API_V1 && kv->struct_size>=sizeof(*kv) && kv->get && kv->put;
}
static inline int portable_rtc_basis_load(const risc_key_value_v1 *kv,portable_rtc_basis *out) {
 if(!out)return PORTABLE_RTC_BASIS_INVALID;
 out->stores_utc=false;out->reference_epoch=0;
 if(!portable_rtc_basis_api(kv))return PORTABLE_RTC_BASIS_UNAVAILABLE;
 uint8_t bytes[PORTABLE_RTC_BASIS_BYTES]={0};uint32_t size=0;
 int32_t result=kv->get(kv->context,PORTABLE_RTC_BASIS_KEY,bytes,sizeof(bytes),&size);
 if(result==RISC_KEY_VALUE_NOT_FOUND)return PORTABLE_RTC_BASIS_MISSING;
 if(result==RISC_KEY_VALUE_BUFFER_SMALL)return PORTABLE_RTC_BASIS_INVALID;
 if(result!=RISC_KEY_VALUE_OK)return PORTABLE_RTC_BASIS_UNAVAILABLE;
 if(size!=sizeof(bytes) || bytes[0]!=0x52 || bytes[1]!=0x54 || bytes[2]!=1 || bytes[3]>1 ||
    portable_rtc_basis_word(bytes+8)!=portable_rtc_basis_check(bytes))return PORTABLE_RTC_BASIS_INVALID;
 portable_rtc_basis value={bytes[3]!=0,portable_rtc_basis_word(bytes+4)};
 if(!portable_rtc_basis_valid(&value))return PORTABLE_RTC_BASIS_INVALID;
 *out=value;return PORTABLE_RTC_BASIS_LOADED;
}
/* Invoke only after an explicit, verified RTC/time-policy change. A failed
 * write or readback is unconfirmed even if bytes may already have persisted. */
static inline int portable_rtc_basis_save(const risc_key_value_v1 *kv,const portable_rtc_basis *value) {
 if(!portable_rtc_basis_valid(value))return PORTABLE_RTC_BASIS_BAD_VALUE;
 if(!portable_rtc_basis_api(kv))return PORTABLE_RTC_BASIS_NO_STORAGE;
 portable_rtc_basis old;
 if(portable_rtc_basis_load(kv,&old)==PORTABLE_RTC_BASIS_LOADED &&
    old.stores_utc==value->stores_utc && old.reference_epoch==value->reference_epoch)return PORTABLE_RTC_BASIS_UNCHANGED;
 uint8_t bytes[PORTABLE_RTC_BASIS_BYTES]={0x52,0x54,1,(uint8_t)(value->stores_utc?1:0)};
 portable_rtc_basis_put_word(bytes+4,value->reference_epoch);
 portable_rtc_basis_put_word(bytes+8,portable_rtc_basis_check(bytes));
 if(kv->put(kv->context,PORTABLE_RTC_BASIS_KEY,bytes,sizeof(bytes))!=RISC_KEY_VALUE_OK)return PORTABLE_RTC_BASIS_WRITE_FAILED;
 if(portable_rtc_basis_load(kv,&old)!=PORTABLE_RTC_BASIS_LOADED ||
    old.stores_utc!=value->stores_utc || old.reference_epoch!=value->reference_epoch)return PORTABLE_RTC_BASIS_VERIFY_FAILED;
 return PORTABLE_RTC_BASIS_SAVED;
}
