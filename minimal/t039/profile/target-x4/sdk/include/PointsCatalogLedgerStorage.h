#ifndef UTILITIES_POINTS_CATALOG_LEDGER_STORAGE_H
#define UTILITIES_POINTS_CATALOG_LEDGER_STORAGE_H
#include "PointsCatalogLedger.h"
#include "RiscBoundAppDataV1.h"
typedef struct {
    uint64_t file_revision;
    uint8_t *pending;
    uint8_t *retained_read;
    uint32_t pending_size;
    bool missing,uncertain,retained;
} points_catalog_ledger_storage;
static inline void points_catalog_ledger_storage_dispose(points_catalog_ledger_storage *s) {
    if(s&&!s->retained){POINTS_CATALOG_FREE(s->pending);memset(s,0,sizeof(*s));}
}
static inline int32_t points_catalog_ledger_storage_result(points_catalog_ledger_storage *s,int32_t r) {
    if(r==RISC_APP_DATA_RETAINED||r==RISC_APP_DATA_CONTEXT)s->retained=true;
    return r;
}
static inline int32_t points_catalog_ledger_read(points_catalog_ledger_storage *s,const risc_bound_app_data_v1 *api,
                                                uint8_t **out,uint32_t *size,uint64_t *rev) {
    *out=NULL;*size=0;*rev=0;if(s->retained)return RISC_APP_DATA_RETAINED;
    uint32_t n=0;uint64_t version=0;int32_t r=api->stat(api->context,POINTS_LEDGER_FILE,&n,&version);
    if(r)return points_catalog_ledger_storage_result(s,r);
    if(n<68||!version)return RISC_APP_DATA_IO;
    uint8_t *b=POINTS_CATALOG_ALLOC(n);if(!b)return RISC_APP_DATA_NO_SPACE;
    uint32_t used=0;uint64_t actual=0;r=api->read(api->context,POINTS_LEDGER_FILE,version,b,n,&used,&actual);
    if(r==RISC_APP_DATA_RETAINED||r==RISC_APP_DATA_CONTEXT) {
        s->retained_read=b;
        return points_catalog_ledger_storage_result(s,r);
    }
    if(r||used!=n||actual!=version){POINTS_CATALOG_FREE(b);return points_catalog_ledger_storage_result(s,r?r:RISC_APP_DATA_IO);}
    *out=b;*size=n;*rev=version;return RISC_APP_DATA_OK;
}
static inline int32_t points_catalog_ledger_load(points_catalog_ledger_storage *s,const risc_bound_app_data_v1 *api,
                                                points_catalog_ledger *out,uint32_t domain) {
    if(s->retained)return RISC_APP_DATA_RETAINED;
    uint8_t *b=NULL;uint32_t n=0;uint64_t revision=0;
    int32_t r=points_catalog_ledger_read(s,api,&b,&n,&revision);
    if(r==RISC_APP_DATA_NOT_FOUND) {
        s->missing=true;
        if(s->uncertain&&!s->file_revision){POINTS_CATALOG_FREE(s->pending);s->pending=NULL;s->pending_size=0;s->uncertain=false;return RISC_APP_DATA_STALE;}
        return r;
    }
    if(r)return r;
    points_catalog_ledger l={0};int decoded=points_catalog_ledger_decode(&l,b,n);
    if(decoded||l.time_domain!=domain){POINTS_CATALOG_FREE(b);points_catalog_ledger_dispose(&l);return RISC_APP_DATA_IO;}
    bool matches=!s->uncertain||(n==s->pending_size&&!memcmp(b,s->pending,n));POINTS_CATALOG_FREE(b);
    if(s->uncertain){POINTS_CATALOG_FREE(s->pending);s->pending=NULL;s->pending_size=0;s->uncertain=false;}
    points_catalog_ledger_dispose(out);*out=l;s->file_revision=revision;s->missing=false;
    return matches?RISC_APP_DATA_OK:RISC_APP_DATA_STALE;
}
static inline int32_t points_catalog_ledger_write(points_catalog_ledger_storage *s,const risc_bound_app_data_v1 *api,
                                                 const points_catalog_ledger *l) {
    if(s->retained)return RISC_APP_DATA_RETAINED;
    if(s->uncertain)return RISC_APP_DATA_COMMIT_UNKNOWN;
    uint32_t n=0,used=0;if(!points_catalog_ledger_size(l->count,&n))return RISC_APP_DATA_INVALID;
    uint8_t *b=POINTS_CATALOG_ALLOC(n);if(!b)return RISC_APP_DATA_NO_SPACE;
    if(points_catalog_ledger_encode(l,b,n,&used)){POINTS_CATALOG_FREE(b);return RISC_APP_DATA_INVALID;}
    s->pending=b;s->pending_size=n;s->uncertain=true;
    int32_t r=api->replace(api->context,POINTS_LEDGER_FILE,s->missing?0:s->file_revision,b,n);
    points_catalog_ledger_storage_result(s,r);
    if(r==RISC_APP_DATA_INVALID||r==RISC_APP_DATA_STALE||r==RISC_APP_DATA_NO_SPACE) {
        POINTS_CATALOG_FREE(s->pending);s->pending=NULL;s->pending_size=0;s->uncertain=false;
    }
    return r;
}
/* Same-generation bytes are immutable; higher generations may only advance
 * unchanged event revisions. Catalog edits reset only their own cursors. */
static inline bool points_catalog_ledger_advances(const points_catalog_ledger *next,const points_catalog_ledger *old) {
    if(!old->generation)return true;
    if(next->generation<old->generation||next->revision<old->revision)return false;
    for(uint32_t i=0;i<old->count;i++) {
        const points_catalog_cursor *a=&old->entries[i],*b=points_catalog_cursor_find(next,a->id);
        if(b&&b->revision==a->revision&&(b->day<a->day||(b->day==a->day&&(b->delivered&a->delivered)!=a->delivered)))return false;
    }
    if(next->generation==old->generation) {
        uint32_t an,bn,used;if(!points_catalog_ledger_size(next->count,&an)||!points_catalog_ledger_size(old->count,&bn)||an!=bn)return false;
        uint8_t *a=POINTS_CATALOG_ALLOC(an),*b=POINTS_CATALOG_ALLOC(bn);bool same=false;
        if(a&&b&&!points_catalog_ledger_encode(next,a,an,&used)&&!points_catalog_ledger_encode(old,b,bn,&used))same=!memcmp(a,b,an);
        POINTS_CATALOG_FREE(a);POINTS_CATALOG_FREE(b);return same;
    }
    return true;
}
#endif
