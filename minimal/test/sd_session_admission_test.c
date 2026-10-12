/* Real X4 provider and FatFs. The fixture replaces native transport only and
 * uses no threads/OS primitives, so this unit also compiles for Xtensa. Native
 * Port mailbox/Sync-lock attachment fences are tested independently upstream. */
#define X4_SD_ASYNC_FIXTURE_ONLY
#include "sd_async_test.c"

_Static_assert(offsetof(risc_storage_volume_api_v1_admission, base) == 0,
               "download prefix must stay at offset zero");
_Static_assert(offsetof(risc_storage_volume_api_v1_admission, admission_tag) ==
               sizeof(risc_storage_volume_api_v1_download), "append only");

static const risc_storage_volume_api_v1_admission *admission;
static const char retained_text[] = "ordinary data survives warm checkpoints";

static int32_t checked_begin(uint64_t *out) {
    unsigned checked=owner_checks, took=locks, released=unlocks;
    unsigned reads=work_reads, writes=work_writes, opens=work_opens;
    unsigned native_calls=calls, clock_sleeps=sleeps, clock_calls=clock_reads;
    unsigned io_calls=work_io_calls, control_calls=work_control_calls;
    uint64_t clock=now_ms, cursor=bootlog_cursor;
    int32_t result=admission->begin_checked(NULL,out);
    assert(owner_checks==checked+1 && locks==took && unlocks==released);
    assert(work_reads==reads && work_writes==writes && work_opens==opens);
    assert(calls==native_calls && sleeps==clock_sleeps && now_ms==clock && clock_reads==clock_calls);
    assert(work_io_calls==io_calls && work_control_calls==control_calls);
    assert(bootlog_cursor==cursor);
    return result;
}

static void refused(int32_t expected) {
    /* Verify byte-for-byte preservation of all live filesystem/adaptor state,
     * including file positions, buffered writes and retained generations. */
    file_slot before_files[FILE_SLOTS]; dir_slot before_dirs[DIR_SLOTS];
    risc_storage_async_adapter_v1 before_adapter;
    FATFS before_fs;
    memcpy(before_files,files,sizeof(files)); memcpy(before_dirs,dirs,sizeof(dirs));
    memcpy(&before_adapter,&async_adapter,sizeof(async_adapter));
    memcpy(&before_fs,&filesystem,sizeof(filesystem));
    uint64_t out=UINT64_MAX, token=export_token;
    uint64_t native_token=work_token;unsigned native_state=work_state;
    unsigned exports=export_state, sleep=sleep_state;
    bool prepared=power_down_prepared, committed=power_down_committed;
    assert(checked_begin(&out)==expected && out==0);
    assert(!memcmp(before_files,files,sizeof(files)) && !memcmp(before_dirs,dirs,sizeof(dirs)));
    assert(!memcmp(&before_adapter,&async_adapter,sizeof(async_adapter)));
    assert(!memcmp(&before_fs,&filesystem,sizeof(filesystem)));
    assert(export_state==exports && export_token==token && sleep_state==sleep);
    assert(power_down_prepared==prepared && power_down_committed==committed);
    assert(work_token==native_token && work_state==native_state);
}

static void verify_data(void) {
    uint64_t n=0; char bytes[sizeof(retained_text)]={0};
    uint32_t h=file_open_read(NULL,"/ordinary.txt",&n);
    assert(h && n==sizeof(retained_text));
    assert(file_read(NULL,h,bytes,sizeof(bytes))==sizeof(bytes));
    assert(!memcmp(bytes,retained_text,sizeof(bytes)) && file_close(NULL,h,false));
}

static void warm_checkpoint(void) {
    assert(checked_begin(&session)==RISC_STORAGE_ASYNC_OK && session);
    assert(observe_state(NULL)==RISC_STORAGE_STATE_UNAVAILABLE);
    refused(RISC_STORAGE_ASYNC_BUSY);
    rejected_calls(); /* Includes ordinary, export and sleep APIs. */
    request(RISC_STORAGE_ASYNC_READ_SMALL_FILE,"/ordinary.txt");
    refused(RISC_STORAGE_ASYNC_BUSY); /* Pending raw mailbox must survive. */
    assert(finish()==RISC_STORAGE_ASYNC_OK);
    assert(async_result.size==sizeof(retained_text));
    assert(!memcmp(async_result.data,retained_text,sizeof(retained_text)));
    assert(observe_state(NULL)==RISC_STORAGE_STATE_UNAVAILABLE);
    end_session();
    assert(observe_state(NULL)==RISC_STORAGE_STATE_READY);
    verify_data();
}

static void abi_checks(void) {
    const risc_storage_volume_api_v1 *v=&logging_api.prepared.base.sleep.terminal.power.volume.base;
    admission=risc_storage_volume_session_admission(v);
    assert(admission && risc_storage_volume_async(v) && risc_storage_volume_packages(v) && risc_storage_volume_download(v));
    risc_storage_volume_api_v1_admission copy; memcpy(&copy,admission,sizeof(copy));
    risc_storage_volume_api_v1 *base=(risc_storage_volume_api_v1 *)&copy;
    base->struct_size=sizeof(risc_storage_volume_api_v1_download);
    assert(risc_storage_volume_download(base) && !risc_storage_volume_session_admission(base));
    base->struct_size=sizeof(copy);copy.admission_version=2;
    assert(!risc_storage_volume_session_admission(base));copy.admission_version=1;
    copy.admission_tag=0;assert(!risc_storage_volume_session_admission(base));
    copy.admission_tag=RISC_STORAGE_SESSION_ADMISSION_TAG;copy.begin_checked=NULL;
    assert(!risc_storage_volume_session_admission(base));
    assert(!risc_storage_volume_session_admission(NULL));
}

int main(int argc,char **argv) {
    format(false);assert(t5_driver_get(2));abi_checks();assert(START());
    assert(checked_begin(&session)==0);request(RISC_STORAGE_ASYNC_REFRESH,NULL);
    assert(finish()==0);end_session();
    uint32_t writer=file_open_write(NULL,"/ordinary.txt");assert(writer);
    assert(file_write(NULL,writer,retained_text,sizeof(retained_text))==sizeof(retained_text));
    refused(RISC_STORAGE_ASYNC_BUSY); /* Buffered, unclosed ordinary writer. */
    assert(file_close(NULL,writer,true));verify_data();
    if(argc>1 && !strcmp(argv[1],"retained-writer")) {
        writer=file_open_write(NULL,"/uncertain.txt");assert(writer);
        unsigned char failed_bytes[1024];memset(failed_bytes,0x4e,sizeof(failed_bytes));
        work_fail_write=true;
        assert(file_write(NULL,writer,failed_bytes,sizeof(failed_bytes))<sizeof(failed_bytes));
        assert(io_failed && sdmmc_fault);
        assert(!file_close(NULL,writer,true));
        assert(observe_state(NULL)==RISC_STORAGE_STATE_RETAINED);
        refused(RISC_STORAGE_ASYNC_RETAINED);
        assert(file_for(writer) && !quiesce());
        puts("warm admission: retained ordinary writer remains owned PASS");
        free(card_image);return 0;
    }
    if(argc>1 && !strcmp(argv[1],"retained-unlock")) {
        fail_unlock=true;assert(!ready(NULL));
        assert(owner_guard && mutex_poisoned && locked);
        refused(RISC_STORAGE_ASYNC_RETAINED);assert(!quiesce());
        puts("warm admission: failed ordinary unlock retains native custody PASS");
        free(card_image);return 0;
    }
    warm_checkpoint();
    uint64_t n=0;uint32_t reader=file_open_read(NULL,"/ordinary.txt",&n);assert(reader);
    char prefix[8];assert(file_read(NULL,reader,prefix,sizeof(prefix))==sizeof(prefix));
    refused(RISC_STORAGE_ASYNC_BUSY);
    uint64_t position=0;assert(file_info(NULL,reader,&n,&position) && position==sizeof(prefix));
    assert(file_close(NULL,reader,false));
    uint32_t directory=dir_open(NULL,"/");assert(directory);
    refused(RISC_STORAGE_ASYNC_BUSY);assert(dir_close_checked(NULL,directory));
    warm_checkpoint();
    assert(enter_lifecycle() && owner_guard);refused(RISC_STORAGE_ASYNC_BUSY);assert(leave());
    owner=false;refused(RISC_STORAGE_ASYNC_BUSY);owner=true;
    assert(checked_begin(NULL)==RISC_STORAGE_ASYNC_INVALID);
    risc_storage_export_token_t exported=0;uint64_t blocks=0;uint32_t block_size=0;
    assert(export_begin_prepare(NULL,&exported)==RISC_STORAGE_EXPORT_PREPARING);
    refused(RISC_STORAGE_ASYNC_BUSY);assert(export_end(NULL,exported)==RISC_STORAGE_EXPORT_READY);
    assert(export_begin(NULL,&exported,&blocks,&block_size)==RISC_STORAGE_EXPORT_READY);
    refused(RISC_STORAGE_ASYNC_BUSY);assert(export_end(NULL,exported)==RISC_STORAGE_EXPORT_READY);
    warm_checkpoint();
    assert(prepare_sleep(NULL));refused(RISC_STORAGE_ASYNC_BUSY);
    assert(commit_sleep(NULL));refused(RISC_STORAGE_ASYNC_BUSY);
    assert(resume_sleep(NULL)==RISC_STORAGE_SLEEP_READY);warm_checkpoint();
    /* Exhaustive metadata blockers. No test clears real failed custody. */
    bool *busy[]={&quiescing,&quiesced,&owner_guard,&worker_guard,&power_down_prepared,
                 &power_down_committed,&bootlog_servicing,&bootlog_paused,
                 &async_adapter.writing,&async_adapter.ending,&async_adapter.cleanup};
    for(unsigned i=0;i<sizeof(busy)/sizeof(*busy);++i){assert(!*busy[i]);*busy[i]=true;refused(RISC_STORAGE_ASYNC_BUSY);*busy[i]=false;}
    bool *retained[]={&mutex_poisoned,&gpio_fault,&gpio_retained,&sdmmc_fault,&bootlog_retained,&async_adapter.retained};
    for(unsigned i=0;i<sizeof(retained)/sizeof(*retained);++i){assert(!*retained[i]);*retained[i]=true;refused(RISC_STORAGE_ASYNC_RETAINED);*retained[i]=false;}
    sleep_state=SLEEP_RETAINED;refused(RISC_STORAGE_ASYNC_RETAINED);sleep_state=SLEEP_ACTIVE;
    export_state=EXPORT_RETAINED;refused(RISC_STORAGE_ASYNC_RETAINED);export_state=EXPORT_LOCAL;
    async_adapter.operation=7;refused(RISC_STORAGE_ASYNC_BUSY);async_adapter.operation=0;
    async_adapter.file=7;refused(RISC_STORAGE_ASYNC_BUSY);async_adapter.file=0;
    async_adapter.directory=7;refused(RISC_STORAGE_ASYNC_BUSY);async_adapter.directory=0;
    async_adapter.written=7;refused(RISC_STORAGE_ASYNC_BUSY);async_adapter.written=0;
    async_adapter.serial=UINT64_MAX;refused(RISC_STORAGE_ASYNC_INVALID);
    verify_data();assert(quiesce());stop();free(card_image);
    puts("warm admission: ordinary read/write/directory, export/sleep return, async refusal, zero-I/O owner check, truthful observation, data preservation PASS");
}
