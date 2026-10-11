// Exercises the production paired transaction with real delivered images.
// Flash/boot selection is a memory model; metadata/ELF admission is separate.
#define main paired_bank_unit_main
#include "paired_bank_test.cpp"
#undef main
#include <fstream>
#include <limits>
static std::vector<uint8_t> load(const char* p){std::ifstream f(p,std::ios::binary);assert(f);return {std::istreambuf_iterator<char>(f),{}};}
static unsigned run(const std::vector<uint8_t>& full,const std::vector<uint8_t>& fw,const std::vector<uint8_t>& store,unsigned cut,bool cohort){
 assert(full.size()==0x1000000 && store.size()==StoreBytes);
 Model m;memcpy(m.bytes[0][0].data(),full.data()+0x10000,FirmwareBytes);memcpy(m.bytes[0][1].data(),full.data()+0x2f0000,StoreBytes);
 memcpy(&m.records[0],full.data()+0xff2000,sizeof(Record));assert(validRecord(m.records[0],0));
 auto before0=m.bytes[0][0],before1=m.bytes[0][1];auto record=m.records[0];
 // Explicit canaries stand in for live private data outside both bank spans.
 std::vector<uint8_t> privateData(full.begin()+0x270000,full.begin()+0x2f0000),nvs(full.begin()+0x9000,full.begin()+0xf000);
 for(size_t i=0;i<privateData.size();++i)privateData[i]=uint8_t(i*17+3);
 for(size_t i=0;i<nvs.size();++i)nvs[i]=uint8_t(i*23+9);
 auto privateBefore=privateData,nvsBefore=nvs;
 auto intactActual=[&](){assert(m.bytes[0][0]==before0 && m.bytes[0][1]==before1 && !memcmp(&record,&m.records[0],sizeof record));assert(privateData==privateBefore && nvs==nvsBefore);};
 std::vector<uint8_t> transfer=fw;if(cohort)transfer.insert(transfer.end(),store.begin(),store.end());
 auto attempt=[&](Transaction& t){uint64_t token=0;int rc;
  if(cohort){risc_bank_cohort_v1 c{};c.struct_size=sizeof c;c.store_abi=StoreAbi;c.firmware_size=fw.size();c.store_size=StoreBytes;memcpy(c.active_store_sha256,m.records[0].storeSha,32);SHA256(transfer.data(),transfer.size(),c.sha256);SHA256(fw.data(),fw.size(),c.firmware_sha256);SHA256(store.data(),store.size(),c.store_sha256);rc=t.beginCohort(c,&token);}
  else{risc_bank_image_v1 im{};im.struct_size=sizeof im;im.store_abi=StoreAbi;im.size=fw.size();memcpy(im.active_store_sha256,m.records[0].storeSha,32);SHA256(fw.data(),fw.size(),im.sha256);rc=t.begin(false,im,&token);}
  if(!rc)rc=advance(t,token);
  for(size_t at=0;!rc && at<transfer.size();){unsigned n=std::min(size_t(4093),transfer.size()-at);rc=t.write(token,transfer.data()+at,n);at+=n;}
  if(!rc)rc=t.finish(token);if(!rc)rc=advance(t,token);if(!rc)rc=t.activate(token);return rc;
 };
 m.cut=cut;Transaction t(m.backend());assert(t.initialize(0,m.records[0]));int rc=attempt(t);unsigned operations=m.operations;intactActual();
 if(rc){assert(m.selected==0);m.cut=0; // Simulated reset loses transaction RAM, retains all flash and records.
  Transaction restart(m.backend());assert(restart.initialize(0,m.records[0]));assert(!attempt(restart));}
 assert(m.selected==1 && validRecord(m.records[1],1));assert(!memcmp(m.bytes[1][0].data(),fw.data(),fw.size()));
 assert(m.bytes[1][1]==(cohort?store:before1));intactActual();
 // Bootloader rollback selection model: previous native and store remain an exact pair.
 m.selected=0;Transaction rollback(m.backend());assert(rollback.initialize(0,m.records[0]));intactActual();
 return operations;
}
int main(int argc,char** argv){assert(argc==4);auto full=load(argv[1]),fw=load(argv[2]),store=load(argv[3]);
 for(bool cohort:{false,true}){unsigned count=run(full,fw,store,UINT32_MAX,cohort);std::vector<unsigned> cuts={1,2,3,8,100,1300,2600,count/2,count-3,count-2,count-1,count};for(auto cut:cuts)run(full,fw,store,cut,cohort);std::cout<<(cohort?"cohort":"native-first clone")<<": real payload, "<<count<<" I/O operations, "<<cuts.size()<<" fault/restart/rollback cuts PASS\n";}
}
