// Real shared X4 update service + production paired transaction. The HTTP,
// flash and boot selection boundaries are models; ELF admission is separate.
#define main unused_paired_unit_entry
#include "paired_bank_test.cpp"
#undef main
#define UPDATE_FIRMWARE 1
#define UPDATE_PRODUCT_X4
#define UPDATE_CATALOG_URL "https://raw.githubusercontent.com/michaelrolphone-cmyk/RiskRTE-XTEINK-X4-PRO/release-index/release-index.json"
#include "service.cpp"
#include <fstream>
static std::vector<uint8_t> readFile(const char*p){std::ifstream f(p,std::ios::binary);assert(f);return {std::istreambuf_iterator<char>(f),{}};}
namespace integration {
std::unique_ptr<Model> model;std::unique_ptr<Transaction> transaction;
std::vector<uint8_t> full,catalogBytes,candidate;size_t position;bool download;unsigned downloads,cohortBegins,activated,restarted;const char*productVersion="0.1.85";
const risc_http_client_v1 httpApi={1,sizeof(httpApi),nullptr,
 [](void*,const risc_http_request_v1*q,uint64_t*h)->int32_t{assert(q->utc_seconds==1800000000ULL);download=strcmp(q->url,WatchUpdate::CatalogUrl)!=0;if(download){assert(!strcmp(q->url,catalog->rows[0].url)&&q->max_bytes==candidate.size());++downloads;}position=0;*h=1;return 0;},
 [](void*,uint64_t,void*out,uint32_t capacity,uint32_t*n)->int32_t{const auto&bytes=download?candidate:catalogBytes;*n=std::min(size_t(capacity),bytes.size()-position);if(!*n)return RISC_HTTP_EOF;memcpy(out,bytes.data()+position,*n);position+=*n;return 0;},
 [](void*,uint64_t,risc_http_response_v1*out)->int32_t{out->status_code=200;return 0;},
 [](void*,uint64_t)->int32_t{return 0;}};
const risc_platform_clock_api_v1 clockApi={1,sizeof(clockApi),nullptr,[](void*)->uint64_t{return 1;},[](void*,uint32_t){}};
risc_bank_store_v1 bankApi={1,sizeof(bankApi),nullptr,
 [](void*,risc_bank_status_v1*out){assert(transaction->status(out));out->store_abi=2;out->firmware_capacity=FirmwareBytes;out->store_capacity=StoreBytes;strcpy(out->layout,"riscrte-paired-appdata-v2");strcpy(out->runtime_version,"0.2.18");memcpy(out->active_store_sha256,model->records[0].storeSha,32);return true;},
 [](void*,const risc_bank_image_v1*,uint64_t*)->int32_t{assert(false);return -1;},[](void*,const char*,const void*,uint32_t,const risc_bank_image_v1*,uint64_t*)->int32_t{assert(false);return -1;},
 [](void*,uint64_t h,risc_bank_status_v1*s){return transaction->step(h,s);},
 [](void*,uint64_t h,const void*p,uint32_t n){return transaction->write(h,p,n);},
 [](void*,uint64_t h){return transaction->finish(h);},
 [](void*,uint64_t h){assert(!http_handle);++activated;return transaction->activate(h);},
 [](void*,uint64_t h){return transaction->abort(h);},
 [](void*,uint64_t h){assert(transaction->activated(h));++restarted;return true;},[](void*,uint32_t,void*,uint32_t,uint32_t*)->int32_t{assert(false);return -1;},
 [](void*,risc_bank_cohort_status_v1*out)->int32_t{strcpy(out->product,WatchUpdate::Product);strcpy(out->version,productVersion);strcpy(out->source_repo,WatchUpdate::Repository);memset(out->source_revision,'a',40);out->source_revision[40]=0;return 0;},
 [](void*,const risc_bank_cohort_v1*c,uint64_t*h)->int32_t{assert(!strcmp(c->version,"0.1.86")&&!strcmp(c->runtime_version,"0.2.18"));++cohortBegins;return transaction->beginCohort(*c,h);}};
void until(uint32_t target){for(unsigned i=0;i<50000;++i){if(view.state==target)return;assert(view.state!=SOFTWARE_UPDATE_ERROR&&view.state!=SOFTWARE_UPDATE_RETAINED);step(nullptr);}assert(false);}
}
int main(int argc,char**argv){using namespace integration;assert(argc==4);full=readFile(argv[1]);catalogBytes=readFile(argv[2]);candidate=readFile(argv[3]);assert(full.size()==0x1000000);
 model.reset(new Model);memcpy(model->bytes[0][0].data(),full.data()+0x10000,FirmwareBytes);memcpy(model->bytes[0][1].data(),full.data()+0x2f0000,StoreBytes);memcpy(&model->records[0],full.data()+0xff2000,96);assert(validRecord(model->records[0],0));auto oldFirmware=model->bytes[0][0],oldStore=model->bytes[0][1];
 transaction.reset(new Transaction(model->backend()));assert(transaction->initialize(0,model->records[0]));
 risc_provider_dependency_v1 dependencies[]={{RISC_HTTP_CLIENT_CAPABILITY,1,&httpApi},{RISC_BANK_STORE_CAPABILITY,1,&bankApi},{"platform.clock",1,&clockApi}};
 assert(t5_driver_get(2)->start(dependencies,3));assert(refresh(nullptr,1800000000ULL));until(SOFTWARE_UPDATE_LIST);assert(catalog->count==1&&catalog->rows[0].view.availability==SOFTWARE_UPDATE_AVAILABLE);
 assert(begin(nullptr,0,1800000000ULL));until(SOFTWARE_UPDATE_READY);assert(downloads==1&&cohortBegins==1&&!activated&&!model->selected);assert(activate(nullptr)&&restart(nullptr)&&activated==1&&restarted==1&&model->selected==1);
 assert(model->bytes[0][0]==oldFirmware&&model->bytes[0][1]==oldStore);auto&c=catalog->cohort;assert(!memcmp(model->bytes[1][0].data(),candidate.data(),c.firmware_size));assert(!memcmp(model->bytes[1][1].data(),candidate.data()+c.firmware_size,StoreBytes));
 puts("Actual feed-enabled X4 updater: .85 -> .86 catalog availability, real payload streaming, paired SHA/readback, activation/restart and old pair preservation PASS");
}
