#ifndef UTILITIES_POINTS_CATALOG_STORAGE_H
#define UTILITIES_POINTS_CATALOG_STORAGE_H
#include "PointsCatalog.h"
#include "RiscAppDataV1.h"
#define POINTS_STORAGE_MEMORY (-32)

/* App and provider use the same file mechanics through separately authorized
 * capabilities. There is no retry of an ambiguous replace: resolution reads
 * the actual complete document before permitting another edit. */
typedef struct {
    points_catalog saved;
    uint64_t file_revision;
    uint8_t *pending;
    /* A terminal backend result can still own the supplied read buffer. */
    uint8_t *retained_read;
    uint32_t pending_size;
    bool loaded, missing, uncertain, retained;
    int32_t error;
} points_catalog_storage;

static inline bool points_catalog_storage_api(const risc_app_data_v1 *api) {
    return api&&api->api_version==RISC_APP_DATA_API_V1&&api->struct_size>=sizeof(*api)&&api->stat&&api->read&&api->replace;
}
static inline int32_t points_catalog_storage_result(points_catalog_storage *s,int32_t result) {
    if(result==RISC_APP_DATA_RETAINED||result==RISC_APP_DATA_CONTEXT)s->retained=true;
    s->error=result;return result;
}
static inline void points_catalog_storage_dispose(points_catalog_storage *s) {
    if(!s||s->retained)return;
    points_catalog_dispose(&s->saved);POINTS_CATALOG_FREE(s->pending);memset(s,0,sizeof(*s));
}
static inline int32_t points_catalog_read_document(points_catalog_storage *s,const risc_app_data_v1 *api,
                                                  uint8_t **bytes,uint32_t *size,uint64_t *revision) {
    if(!s||!bytes||!size||!revision||!points_catalog_storage_api(api))return RISC_APP_DATA_INVALID;
    *bytes=NULL;*size=0;*revision=0;
    if(s->retained)return RISC_APP_DATA_RETAINED;
    uint32_t n=0;uint64_t expected=0;
    int32_t rc=api->stat(api->context,POINTS_CATALOG_FILE,&n,&expected);
    if(rc!=RISC_APP_DATA_OK)return points_catalog_storage_result(s,rc);
    if(!expected||n<POINTS_CATALOG_HEADER_BYTES+4)return points_catalog_storage_result(s,RISC_APP_DATA_IO);
    uint8_t *data=POINTS_CATALOG_ALLOC(n);
    if(!data)return points_catalog_storage_result(s,POINTS_STORAGE_MEMORY);
    uint32_t actual=0;uint64_t token=0;
    rc=api->read(api->context,POINTS_CATALOG_FILE,expected,data,n,&actual,&token);
    if(rc==RISC_APP_DATA_RETAINED||rc==RISC_APP_DATA_CONTEXT) {
        s->retained_read=data;
        return points_catalog_storage_result(s,rc);
    }
    if(rc!=RISC_APP_DATA_OK||actual!=n||token!=expected) {
        POINTS_CATALOG_FREE(data);
        return points_catalog_storage_result(s,rc==RISC_APP_DATA_OK?RISC_APP_DATA_IO:rc);
    }
    *bytes=data;*size=n;*revision=token;return RISC_APP_DATA_OK;
}
static inline int32_t points_catalog_storage_load(points_catalog_storage *s,const risc_app_data_v1 *api,uint32_t domain) {
    if(!s||domain>POINTS_TIME_NATIVE_UTC)return RISC_APP_DATA_INVALID;
    if(s->retained)return RISC_APP_DATA_RETAINED;
    if(s->uncertain)return RISC_APP_DATA_COMMIT_UNKNOWN;
    s->loaded=false;s->missing=false;
    uint8_t *bytes=NULL;uint32_t n=0;uint64_t revision=0;
    int32_t rc=points_catalog_read_document(s,api,&bytes,&n,&revision);
    if(rc==RISC_APP_DATA_NOT_FOUND){s->loaded=false;s->missing=true;s->file_revision=0;return rc;}
    if(rc!=RISC_APP_DATA_OK)return rc;
    points_catalog decoded={0};int result=points_catalog_decode(&decoded,bytes,n);POINTS_CATALOG_FREE(bytes);
    if(result!=POINTS_CATALOG_OK)return points_catalog_storage_result(s,result==POINTS_CATALOG_MEMORY?POINTS_STORAGE_MEMORY:RISC_APP_DATA_IO);
    if(decoded.time_domain!=domain){points_catalog_dispose(&decoded);return points_catalog_storage_result(s,RISC_APP_DATA_INVALID);}
    points_catalog_dispose(&s->saved);s->saved=decoded;s->file_revision=revision;s->loaded=true;s->missing=false;
    return points_catalog_storage_result(s,RISC_APP_DATA_OK);
}
static inline int32_t points_catalog_storage_migrate(points_catalog_storage *s,const points_config *legacy,
                                                     const points_meta *meta,uint32_t domain) {
    if(!s||s->retained||s->uncertain||!s->missing||s->file_revision)return RISC_APP_DATA_INVALID;
    int result=points_catalog_migrate(&s->saved,legacy,meta,domain);
    if(result!=POINTS_CATALOG_OK)return result==POINTS_CATALOG_MEMORY?POINTS_STORAGE_MEMORY:RISC_APP_DATA_INVALID;
    s->loaded=true;return points_catalog_storage_result(s,RISC_APP_DATA_OK);
}
static inline int32_t points_catalog_storage_resolve(points_catalog_storage *s,const risc_app_data_v1 *api) {
    if(!s||!s->loaded||!s->uncertain||!s->pending||!points_catalog_storage_api(api))return RISC_APP_DATA_INVALID;
    if(s->retained)return RISC_APP_DATA_RETAINED;
    uint8_t *bytes=NULL;uint32_t n=0;uint64_t revision=0;
    int32_t rc=points_catalog_read_document(s,api,&bytes,&n,&revision);
    if(rc==RISC_APP_DATA_NOT_FOUND&&s->missing) {
        POINTS_CATALOG_FREE(s->pending);s->pending=NULL;s->pending_size=0;s->uncertain=false;s->file_revision=0;
        return points_catalog_storage_result(s,RISC_APP_DATA_IO);
    }
    if(rc!=RISC_APP_DATA_OK)return rc;
    points_catalog decoded={0};int result=points_catalog_decode(&decoded,bytes,n);
    if(result!=POINTS_CATALOG_OK||decoded.time_domain!=s->saved.time_domain) {
        points_catalog_dispose(&decoded);POINTS_CATALOG_FREE(bytes);
        return points_catalog_storage_result(s,result==POINTS_CATALOG_MEMORY?POINTS_STORAGE_MEMORY:RISC_APP_DATA_IO);
    }
    bool committed=n==s->pending_size&&!memcmp(bytes,s->pending,n);
    /* A different valid complete document may be the old value or a concurrent
     * editor's value. Adopt it and report conflict; never overwrite it. */
    POINTS_CATALOG_FREE(bytes);POINTS_CATALOG_FREE(s->pending);s->pending=NULL;s->pending_size=0;
    points_catalog_dispose(&s->saved);s->saved=decoded;s->file_revision=revision;
    s->uncertain=false;s->missing=false;
    return points_catalog_storage_result(s,committed?RISC_APP_DATA_OK:RISC_APP_DATA_STALE);
}
static inline int32_t points_catalog_storage_save(points_catalog_storage *s,const risc_app_data_v1 *api,const points_catalog *desired) {
    if(!s||!s->loaded||!points_catalog_storage_api(api)||!points_catalog_valid(desired)||
       desired->time_domain!=s->saved.time_domain||desired->revision<s->saved.revision)return RISC_APP_DATA_INVALID;
    if(s->retained)return RISC_APP_DATA_RETAINED;
    if(s->uncertain)return RISC_APP_DATA_COMMIT_UNKNOWN;
    if(desired->revision==s->saved.revision&&!s->missing)return RISC_APP_DATA_INVALID;
    uint32_t size,used;
    if(!points_catalog_size(desired->event_count,desired->type_count,&size))return RISC_APP_DATA_INVALID;
    uint8_t *bytes=POINTS_CATALOG_ALLOC(size);if(!bytes)return points_catalog_storage_result(s,POINTS_STORAGE_MEMORY);
    if(points_catalog_encode(desired,bytes,size,&used)!=POINTS_CATALOG_OK){POINTS_CATALOG_FREE(bytes);return RISC_APP_DATA_INVALID;}
    s->pending=bytes;s->pending_size=size;s->uncertain=true;
    int32_t rc=api->replace(api->context,POINTS_CATALOG_FILE,s->file_revision,bytes,size);
    if(rc==RISC_APP_DATA_RETAINED||rc==RISC_APP_DATA_CONTEXT)return points_catalog_storage_result(s,rc);
    if(rc==RISC_APP_DATA_NO_SPACE||rc==RISC_APP_DATA_INVALID||rc==RISC_APP_DATA_STALE) {
        POINTS_CATALOG_FREE(s->pending);s->pending=NULL;s->pending_size=0;s->uncertain=false;
        return points_catalog_storage_result(s,rc);
    }
    /* Read back even after OK. A commit with a subsequent read failure remains
     * locked until resolution, using only stat/read and never another put. */
    return points_catalog_storage_resolve(s,api);
}
#endif
