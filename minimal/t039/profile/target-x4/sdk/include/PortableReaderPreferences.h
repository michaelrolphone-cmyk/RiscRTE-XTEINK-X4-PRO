#pragma once
/* App-owned namespace-1 records. Reader language IDs are frozen to
 * T5S3-Reader 34d8e694d89a1e72d8854403d8592c289fae3ddc,
 * scripts/gen_i18n.py ordering of the Reader translation YAML metadata.
 * ASCII selection names are English display labels, never new language IDs. */
#include "PortableSleepPolicy.h"
#define PORTABLE_READER_LANGUAGE_KEY "reader_language"
#define PORTABLE_READER_FLIP_KEY "reader_flip_ui"
#define PORTABLE_READER_LANGUAGE_COUNT 22u
#define PORTABLE_READER_STORE_INSTANCE 1u
enum { PORTABLE_READER_LOADED=0, PORTABLE_READER_MISSING=1,
       PORTABLE_READER_INVALID=2, PORTABLE_READER_UNAVAILABLE=3 };
static inline const char *portable_reader_language_code(unsigned id) {
    static const char *const codes[]={"EN","ES","FR","DE","CS","PT","RU","SV","RO","CA","UK","BE","IT","PL","FI","DA","NL","TR","KK","HU","LT","SI"};
    return codes[id<PORTABLE_READER_LANGUAGE_COUNT?id:0];
}
static inline const char *portable_reader_language_name(unsigned id) {
    static const char *const names[]={"English","Spanish","French","German","Czech","Portuguese (Brazil)","Russian","Swedish","Romanian","Catalan","Ukrainian","Belarusian","Italian","Polish","Finnish","Danish","Dutch","Turkish","Kazakh","Hungarian","Lithuanian","Slovenian"};
    return names[id<PORTABLE_READER_LANGUAGE_COUNT?id:0];
}
/* These two keys exist only in english.yaml at the frozen source. All other
 * language IDs use the Reader generator's English fallback, verbatim. */
static inline const char *portable_reader_clock_set_time(unsigned language) {
    (void)language;return "Set the clock in Settings";
}
static inline const char *portable_reader_clock_wake(unsigned language) {
    (void)language;return "Press PWR to wake";
}
static inline int portable_reader_preference_load(const risc_key_value_v1 *kv,
        bool language,unsigned *value) {
    if(!value)return PORTABLE_READER_INVALID;
    *value=0;
    if(!portable_sleep_api_valid(kv))return PORTABLE_READER_UNAVAILABLE;
    uint8_t bytes[4]={0};uint32_t size=0;
    int32_t rc=kv->get(kv->context,language?PORTABLE_READER_LANGUAGE_KEY:PORTABLE_READER_FLIP_KEY,bytes,sizeof(bytes),&size);
    if(rc==RISC_KEY_VALUE_NOT_FOUND)return PORTABLE_READER_MISSING;
    if(rc==RISC_KEY_VALUE_BUFFER_SMALL)return PORTABLE_READER_INVALID;
    if(rc!=RISC_KEY_VALUE_OK)return PORTABLE_READER_UNAVAILABLE;
    if(size!=sizeof(bytes) || bytes[0]!=(language?0x4cu:0x52u) || bytes[1]!=1 ||
       bytes[2]>=(language?PORTABLE_READER_LANGUAGE_COUNT:2u) || bytes[3]!=(uint8_t)(bytes[2]^0xa5u))return PORTABLE_READER_INVALID;
    *value=bytes[2];return PORTABLE_READER_LOADED;
}
static inline bool portable_reader_preference_save(const risc_key_value_v1 *kv,
        bool language,unsigned value) {
    if(!portable_sleep_api_valid(kv) || value>=(language?PORTABLE_READER_LANGUAGE_COUNT:2u))return false;
    unsigned current;
    if(portable_reader_preference_load(kv,language,&current)==PORTABLE_READER_LOADED && current==value)return true;
    const uint8_t bytes[]={(uint8_t)(language?0x4c:0x52),1,(uint8_t)value,(uint8_t)(value^0xa5u)};
    if(kv->put(kv->context,language?PORTABLE_READER_LANGUAGE_KEY:PORTABLE_READER_FLIP_KEY,bytes,sizeof(bytes))!=RISC_KEY_VALUE_OK)return false;
    return portable_reader_preference_load(kv,language,&current)==PORTABLE_READER_LOADED && current==value;
}
