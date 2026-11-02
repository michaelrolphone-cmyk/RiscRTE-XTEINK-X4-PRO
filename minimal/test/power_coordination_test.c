#define main legacy_power_fixture_main
#include "power_test.c"
#undef main
#include "../drivers/x4pro_power/X4PowerCoordinationV1.h"
int main(int argc,char**argv){
 assert(argc==2);const risc_driver_v2*d=t5_driver_get(2);const x4_power_v1*a=d->capability;
 assert(x4_power_deep(a));const x4_power_coordination_api_v1*s=x4_power_coordination(a);
 assert(s&&!s->is_owner(s->context));assert(d->start(deps,5));
 assert(s->is_owner(s->context));uint64_t first=0,second=0,overflow=99;
 if(!strcmp(argv[1],"owner")){
  owner=false;assert(!s->is_owner(s->context)&&!s->create(s->context,&first)&&!first&&!locked);
  owner=true;assert(d->quiesce());return 0;
 }
 if(!strcmp(argv[1],"create-retained")){
  unlock_ok=false;assert(!s->create(s->context,&first)&&!first&&locked);
  assert(!s->is_owner(s->context)&&!d->quiesce());return 0;
 }
 assert(s->create(s->context,&first)&&s->create(s->context,&second)&&first!=second&&!locked);
 assert(!s->create(s->context,&overflow)&&!overflow&&!locked);
 assert(!d->quiesce()&&live&&!locked);
 assert(s->try_lock(s->context,first)&&s->try_lock(s->context,second)&&!locked);
 assert(!s->try_lock(s->context,first)&&!s->destroy(s->context,first)&&!locked);
 bool key=false;assert(a->read_key(a->context,&key)&&!key&&!locked);
 if(!strcmp(argv[1],"unlock-retained")){
  unlock_ok=false;assert(!s->unlock(s->context,first));
  assert(!s->is_owner(s->context)&&!d->quiesce());return 0;
 }
 assert(s->unlock(s->context,first)&&s->unlock(s->context,second));
 assert(s->destroy(s->context,first)&&s->destroy(s->context,second));
 uint64_t next=0;assert(s->create(s->context,&next)&&next!=first&&next!=second);
 assert(!s->try_lock(s->context,first)&&s->destroy(s->context,next));
 assert(d->quiesce()&&!s->is_owner(s->context)&&!live&&!locked);
 puts("Power coordination: independent tokens, released native mutex, owner and lifetime PASS");
 return 0;
}
