/* Production driver/shared FatFs. Native worker/sector boundary is modeled;
 * real cross-thread cancellation and CPU permissions have independent tests. */
#include <RiscStorageWorkerV1.h>
static const risc_storage_worker_v1 fixture_worker;
#define X4PRO_SD_ASYNC 1
#define main legacy_fixture_main
#include "sd_test.c"
#undef main
static bool work_running,work_bound,work_scope,work_opened;
static unsigned work_state,work_reads,work_writes,work_opens;
static uint64_t work_serial,work_token;
static risc_storage_work_execute_v1 work_execute;
static void*work_context;
static _Alignas(8) unsigned char work_request[RISC_STORAGE_WORKER_BYTES],work_result[RISC_STORAGE_WORKER_BYTES];
static uint32_t work_size,work_result_size;
static int32_t work_result_status;
static bool work_on_worker(void*c){(void)c;return work_running;}
static uint64_t work_now(void*c){(void)c;return now_ms;}
static void work_delay(void*c,uint32_t ms){(void)c;assert(work_scope);now_ms+=ms;}
static bool work_power(void*c,bool level){(void)c;(void)level;assert(work_scope);return true;}
static bool work_open(void*c,risc_sdmmc_card_info_v1*out){(void)c;assert(work_scope&&!work_opened);++work_opens;work_opened=true;*out=(risc_sdmmc_card_info_v1){sizeof(*out),512,card_sectors,20000000,0};return true;}
static bool work_read(void*c,uint64_t lba,uint32_t n,void*out){(void)c;assert(work_scope&&work_opened&&n&&n<=8&&lba+n<=card_sectors);++work_reads;if(absent)return false;memcpy(out,card_image+lba*512,n*512);return true;}
static bool work_write(void*c,uint64_t lba,uint32_t n,const void*in){(void)c;assert(work_scope&&work_opened&&n&&n<=8&&lba+n<=card_sectors);++work_writes;memcpy(card_image+lba*512,in,n*512);return true;}
static bool work_sync(void*c){(void)c;return work_scope&&work_opened;}
static bool work_close(void*c){(void)c;assert(work_scope);work_opened=false;return true;}
static const risc_storage_work_io_v1 work_io={NULL,work_on_worker,work_now,work_power,work_delay,work_open,work_read,work_write,work_sync,work_close};
static int32_t work_bind(void*c,risc_storage_work_execute_v1 fn,void*ctx){(void)c;assert(owner&&work_scope&&!work_bound);work_bound=true;work_execute=fn;work_context=ctx;return 0;}
static int32_t work_submit(void*c,const void*p,uint32_t n,uint64_t*out){(void)c;assert(owner&&work_bound&&n<=sizeof(work_request));if(work_state)return RISC_STORAGE_WORK_BUSY;memcpy(work_request,p,n);work_size=n;work_state=1;*out=work_token=++work_serial;return 0;}
static int32_t work_collect(void*c,uint64_t t,void*p,uint32_t n,uint32_t*size,int32_t*status){(void)c;assert(owner&&t==work_token);*size=0;if(work_state!=2)return RISC_STORAGE_WORK_PENDING;assert(n>=work_result_size);memcpy(p,work_result,work_result_size);*size=work_result_size;*status=work_result_status;work_state=0;return 0;}
static int32_t work_cancel(void*c,uint64_t t){(void)c;assert(owner&&t==work_token);if(work_running)return RISC_STORAGE_WORK_PENDING;work_state=0;return RISC_STORAGE_WORK_CANCELLED;}
static int32_t work_unbind(void*c){(void)c;assert(owner&&!work_state);work_bound=false;return 0;}
static int32_t work_claim(void*c,const risc_storage_work_scope_v1*q){(void)c;assert(owner&&!work_scope&&q->power==5&&q->clk==41&&q->cmd==42&&q->dat0==40);work_scope=true;return 0;}
static int32_t work_release(void*c){(void)c;assert(owner&&!work_bound&&!work_opened);work_scope=false;return 0;}
static const risc_storage_worker_v1 fixture_worker={1,sizeof(fixture_worker),NULL,work_bind,work_submit,work_collect,work_cancel,work_unbind,work_claim,work_release,&work_io};
static void work_step(void){assert(owner&&work_state==1);owner=false;work_running=true;work_result_status=work_execute(work_context,work_request,work_size,work_result,sizeof(work_result),&work_result_size);work_running=false;owner=true;work_state=2;}
static uint64_t session,operation;
static risc_storage_async_result_v1 async_result;
static void request(unsigned op,const char*path){risc_storage_async_request_v1 q={0};q.operation=op;if(path)strcpy(q.path,path);assert(async_submit(NULL,session,&q,&operation)==0);}
static int32_t finish(void){work_step();return async_collect(NULL,session,operation,&async_result);}
static void end_session(void){int32_t rc=async_end(NULL,session);if(rc==RISC_STORAGE_ASYNC_PENDING){work_step();rc=async_end(NULL,session);}assert(rc==0);}
int main(void){
 format(false);assert(t5_driver_get(2));assert(START());assert(work_scope&&work_bound&&!work_reads&&!work_opens&&!mounted);
 assert(async_begin(NULL,&session)==0);request(RISC_STORAGE_ASYNC_REFRESH,NULL);
 for(unsigned frames=0;frames<1000;++frames)assert(async_collect(NULL,session,operation,&async_result)==RISC_STORAGE_ASYNC_PENDING&&!work_reads);
 assert(finish()==0&&mounted&&work_opens==1&&work_reads);end_session();
 assert(mkdir_path(NULL,"/Apps")&&mkdir_path(NULL,"/Apps/unknown"));
 const char manifest[]="{\"type\":\"application\",\"id\":\"uncompiled\"}";
 uint32_t h=file_open_write(NULL,"/Apps/unknown/manifest.json");assert(h);assert(file_write(NULL,h,manifest,sizeof(manifest)-1)==sizeof(manifest)-1&&file_close(NULL,h,true));
 assert(async_begin(NULL,&session)==0);request(RISC_STORAGE_ASYNC_OPEN_DIRECTORY,"/Apps");assert(finish()==0);
 request(RISC_STORAGE_ASYNC_NEXT_ENTRY,NULL);assert(finish()==0&&async_result.entry.is_directory&&!strcmp(async_result.entry.name,"unknown"));
 request(RISC_STORAGE_ASYNC_READ_SMALL_FILE,"/Apps/unknown/manifest.json");assert(finish()==0&&async_result.size==sizeof(manifest)-1&&!memcmp(async_result.data,manifest,sizeof(manifest)-1));
 risc_storage_export_token_t export=0;uint64_t blocks=0;uint32_t bytes=0;
 assert(export_begin(NULL,&export,&blocks,&bytes)==RISC_STORAGE_EXPORT_REFUSED);assert(!export&&export_state==EXPORT_LOCAL);
 end_session();assert(!has_handles());
 assert(export_begin(NULL,&export,&blocks,&bytes)==RISC_STORAGE_EXPORT_READY);
 unsigned char batch[4096];unsigned before=work_reads;assert(export_read(NULL,export,0,8,batch)==RISC_STORAGE_EXPORT_READY&&work_reads==before+1);assert(export_end(NULL,export)==RISC_STORAGE_EXPORT_READY);
 assert(async_begin(NULL,&session)==0);
 request(RISC_STORAGE_ASYNC_REMOVE_FILE,"/Apps/unknown/manifest.json");assert(finish()==0);
 request(RISC_STORAGE_ASYNC_REMOVE_FILE,"/Apps/unknown/manifest.json");assert(finish()==0); // restart retry
 request(RISC_STORAGE_ASYNC_REMOVE_FILE,"/Apps/unknown");assert(finish()==RISC_STORAGE_ASYNC_IO); // never recursive
 end_session();
 assert(risc_storage_volume_packages(&logging_api.prepared.base.sleep.terminal.power.volume.base));
 assert(async_begin(NULL,&session)==0);
 risc_storage_package_request_v1 pq={0};pq.operation=RISC_STORAGE_PACKAGE_WRITE_SMALL;strcpy(pq.path,"/Apps/unknown/manifest.install");pq.size=sizeof(manifest)-1;memcpy(pq.data,manifest,pq.size);
 assert(package_submit(NULL,session,&pq,&operation)==0);memset(pq.data,0xff,sizeof(pq.data));assert(finish()==0);
 pq=(risc_storage_package_request_v1){0};pq.operation=RISC_STORAGE_PACKAGE_REPLACE;strcpy(pq.path,"/Apps/unknown/manifest.install");strcpy(pq.destination,"/Apps/unknown/manifest.json");assert(package_submit(NULL,session,&pq,&operation)==0);assert(finish()==0);
 request(RISC_STORAGE_ASYNC_READ_SMALL_FILE,"/Apps/unknown/manifest.json");assert(finish()==0&&async_result.size==sizeof(manifest)-1&&!memcmp(async_result.data,manifest,sizeof(manifest)-1));end_session();
 assert(rename_path(NULL,"/Apps/unknown/manifest.json","/Apps/unknown/manifest.json.risc-replace"));
 assert(async_begin(NULL,&session)==0);pq=(risc_storage_package_request_v1){0};pq.operation=RISC_STORAGE_PACKAGE_RECOVER;strcpy(pq.path,"/Apps/unknown/manifest.json");assert(package_submit(NULL,session,&pq,&operation)==0);assert(finish()==0);
 request(RISC_STORAGE_ASYNC_READ_SMALL_FILE,"/Apps/unknown/manifest.json");assert(finish()==0&&async_result.size==sizeof(manifest)-1);end_session();
 assert(prepare_sleep(NULL));assert(commit_sleep(NULL));assert(!work_scope&&pins[0].held);assert(resume_sleep(NULL)==RISC_STORAGE_SLEEP_READY&&work_scope&&!pins[0].held);
 assert(async_begin(NULL,&session)==0);request(RISC_STORAGE_ASYNC_OPEN_DIRECTORY,"/Apps");assert(finish()==0);request(RISC_STORAGE_ASYNC_NEXT_ENTRY,NULL);end_session();assert(!has_handles());
 assert(quiesce());stop();assert(!work_bound&&!work_scope&&!fixture_lock);free(card_image);
 puts("production async SD: lazy activation, pending UI polls, unknown manifest, export refusal and 8-sector batching, cancel/exit, sleep-resume PASS");
}
