// Focused Runtime registration/admission test; native disk is a host fixture.
// It does not qualify the real mount, worker budget, full product or hardware.
#define ATOMIC_COHORT_MAIN unused_original_cohort_main
#include "atomic_key_value_cohort_test.cpp"
#undef ATOMIC_COHORT_MAIN
#include <set>
#include <utility>
struct ProductWriter {const char*id;unsigned ns;};
static constexpr ProductWriter productWriters[]={RISC_NATIVE_SETTINGS_WRITERS};
static_assert(sizeof(productWriters)/sizeof(productWriters[0])==7);
static_assert(RISC_NATIVE_SETTINGS_MAX_WRITERS==7);
static_assert(RISC_RUNTIME_ATOMIC_BINDING_CAPACITY==9);
static bool includePolicyWriter=true;
static bool productBind(R&r){
 for(A*e:{one,six}){const auto ns=e->namespaceId();assert(r.registerAtomicKeyValueReadThrough(ns,*e));assert(r.registerKeyValueAvailability(ns,{reinterpret_cast<void*>(uintptr_t(ns)),availability}));}
 for(const auto&w:productWriters){
  if(!includePolicyWriter&&!strcmp(w.id,"wifi_settings")&&w.ns==1)continue;
  assert(r.registerAtomicKeyValue(w.id,w.ns,w.ns==1?*one:*six));
 }
 return true;
}
static void policy(const std::string&dir,bool preferences){
 const auto path=dir+"/wifi_settings.json";JsonDocument m;std::ifstream in(path);assert(!deserializeJson(m,in));in.close();
 auto req=m["requires"].as<JsonArray>();auto kv=req.add<JsonObject>();kv["capability"]="storage.key-value";kv["api"]=1;
 if(preferences){auto p=req.add<JsonObject>();p["capability"]="storage.preferences";p["api"]=1;}
 {std::ofstream out(path);serializeJson(m,out);}
 JsonDocument b;std::ifstream bin(dir+"/boot.json");assert(!deserializeJson(b,bin));bin.close();
 for(JsonObject row:b["app_capabilities"].as<JsonArray>())if(!strcmp(row["manifest"]|"","wifi_settings.json")){
  auto g=row["grants"].as<JsonArray>();auto k=g.add<JsonObject>();k["capability"]="storage.key-value";k["api"]=1;k["instance_id"]=1;
  if(preferences){auto p=g.add<JsonObject>();p["capability"]="storage.preferences";p["api"]=1;p["instance_id"]=1;}
 }
 std::ofstream out(dir+"/boot.json");serializeJson(b,out);
}
int main(int argc,char**argv){
 assert(argc==2);const std::string base=argv[1];
 root=base+"/old";std::filesystem::create_directories(root);store();policy(root,false);const auto old=root;
 root=base+"/new";std::filesystem::create_directories(root);store();policy(root,true);const auto next=root;
 std::set<std::pair<std::string,unsigned>> seen;
 for(const auto&w:productWriters)assert(seen.emplace(w.id,w.ns).second);
 const std::set<std::pair<std::string,unsigned>> expected={{"settings",1},{"paper_clock",1},{"battery",1},{"ble_scanner",1},{"contexts",1},{"wifi_settings",6},{"wifi_settings",1}};
 assert(seen==expected);
 Disk d1,d6;Alloc allocation;C c1(1,d1.backend(),limits(),allocation.api()),c6(6,d6.backend(),limits(),allocation.api());
 assert(!c1.initialize(nullptr,0,{})&&!c6.initialize(nullptr,0,{}));
 Gate g1,g6;A a1(c1,g1.api()),a6(c6,g6.api());one=&a1;six=&a6;
 const RiscBoot::KeyValueBackend legacy{nullptr,
 [](void*,uint32_t,const char*,void*,uint32_t,uint32_t*)->int32_t{assert(false);return -1;},
 [](void*,uint32_t,const char*,const void*,uint32_t)->int32_t{assert(false);return -1;},2048};
 includePolicyWriter=false;
 RiscTest::FileSources oldFiles({old.c_str(),next.c_str()});R previous({owner,health,delay,logLine,productBind,&legacy});assert(oldFiles.bind(previous));assert(previous.prepare(old.c_str()));
 assert(previous.atomicBindingCount_==8);
 {R candidate({});assert(!previous.validateCohort(candidate,next.c_str(),admit,nullptr));}
 includePolicyWriter=true;
 RiscTest::FileSources newFiles({old.c_str(),next.c_str()});R successor({owner,health,delay,logLine,productBind,&legacy});assert(newFiles.bind(successor));assert(successor.prepare(old.c_str()));assert(successor.atomicBindingCount_==9);
 for(unsigned i=0;i<8;++i){const auto&a=previous.atomicBindings_[i];const auto&b=successor.atomicBindings_[i];assert(!strcmp(a.app,b.app)&&a.nameSpace==b.nameSpace&&a.endpoint.same(b.endpoint));}
 d1.calls=d6.calls=0;
 {R candidate({});assert(successor.validateCohort(candidate,next.c_str(),admit,nullptr));assert(candidate.atomicBindingCount_==9);}
 // Capability cannot grant a different app identity access to this endpoint.
 {JsonDocument m;std::ifstream in(next+"/wifi_settings.json");assert(!deserializeJson(m,in));in.close();m["id"]="intruder";std::ofstream out(next+"/wifi_settings.json");serializeJson(m,out);}
 {R candidate({});assert(!successor.validateCohort(candidate,next.c_str(),admit,nullptr));}
 assert(!d1.calls&&!d6.calls&&!availabilityCalls);
 puts("X4 Wi-Fi policy: old native selection refused, exact ninth binding accepted, prior eight preserved, foreign identity rejected; no storage I/O");
}
