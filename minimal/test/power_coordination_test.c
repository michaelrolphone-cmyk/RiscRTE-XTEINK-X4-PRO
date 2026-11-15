#define main legacy_power_fixture_main
#include "power_test.c"
#undef main
#include "../drivers/x4pro_power/X4PowerCoordinationV1.h"
int main(int argc,char**argv){
 assert(argc==2);const risc_driver_v2*d=t5_driver_get(2);const x4_power_v1*a=d->capability;
 assert(x4_power_deep(a));const x4_power_coordination_api_v1*s=x4_power_coordination(a);
 assert(s&&s->owner(s->context)==X4_COORDINATION_BUSY);assert(d->start(deps,5));
 assert(s->owner(s->context)==X4_COORDINATION_OK);uint64_t first=0,second=0,overflow=99;
 if(!strcmp(argv[1],"owner")){
  owner=false;assert(s->owner(s->context)==X4_COORDINATION_BUSY&&s->create(s->context,&first)==X4_COORDINATION_BUSY&&!first&&!locked);
  owner=true;assert(d->quiesce());return 0;
 }
 if(!strcmp(argv[1],"create-retained")){
  unlock_ok=false;assert(s->create(s->context,&first)==X4_COORDINATION_RETAINED&&!first&&locked);
  assert(!d->quiesce());return 0;
 }
 assert(s->create(s->context,&first)==0&&s->create(s->context,&second)==0&&first!=second&&!locked);
 assert(s->create(s->context,&overflow)==X4_COORDINATION_BUSY&&!overflow&&!locked);
 assert(!d->quiesce()&&live&&!locked);
 assert(s->try_lock(s->context,first)==0&&s->try_lock(s->context,second)==0&&!locked);
 assert(s->try_lock(s->context,first)==X4_COORDINATION_BUSY&&s->destroy(s->context,first)==X4_COORDINATION_BUSY&&!locked);
 bool key=false;assert(a->read_key(a->context,&key)&&!key&&!locked);
 if(!strcmp(argv[1],"unlock-retained")){
  unlock_ok=false;assert(s->unlock(s->context,first)==X4_COORDINATION_RETAINED);
  assert(!d->quiesce());return 0;
 }
 assert(s->unlock(s->context,first)==0&&s->unlock(s->context,second)==0);
 assert(s->destroy(s->context,first)==0&&s->destroy(s->context,second)==0);
 uint64_t next=0;assert(s->create(s->context,&next)==0&&next!=first&&next!=second);
 assert(s->try_lock(s->context,first)==X4_COORDINATION_INVALID&&s->destroy(s->context,next)==0);
 assert(d->quiesce()&&s->owner(s->context)==X4_COORDINATION_BUSY&&!live&&!locked);
 puts("Power coordination: typed BUSY/RETAINED, independent tokens, released native mutex, lifetime PASS");
 return 0;
}
