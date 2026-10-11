/* Count production MSC/TinyUSB/SD/FatFs boundaries without in-loop logging.
 * USB DCD and physical SDMMC are test doubles: this is not a speed measurement. */
#define main unused_owner_main
#include USB_OWNER_TEST_SOURCE
#undef main
extern const risc_storage_volume_api_v1_export_prepare *directory_sd_start(void);
extern void directory_sd_frozen(void),directory_sd_finish(void);
extern unsigned directory_sd_reads(void),directory_sd_writes(void);
extern uint32_t directory_sd_hash(void);
extern uint8_t *card_image;
extern void bulk_fault(unsigned),bulk_retained(void);
static const risc_storage_volume_api_v1_export_prepare *real_volume;
static uint64_t sd_token;
static bool queue_reset_in_read;
static unsigned read_calls,write_calls,read_blocks,write_blocks,max_blocks,transfers;
static int32_t real_begin(void*c,uint64_t*t){int32_t r=real_volume->begin_prepare(c,t);assert(r==RISC_STORAGE_EXPORT_PREPARING);sd_token=*t;sd_owned=true;mark('M');return r;}
static int32_t real_end(void*c,uint64_t t){assert(!usb_live);int32_t r=real_volume->base.export_end(c,t);if(!r){sd_owned=false;mark('E');}return r;}
static int32_t tracked_read(void*c,uint64_t t,uint64_t lba,uint32_t n,void*out){++read_calls;read_blocks+=n;now_ms+=2+n;if(n>max_blocks)max_blocks=n;int32_t r=real_volume->base.export_read(c,t,lba,n,out);if(queue_reset_in_read){queue_reset_in_read=false;dcd_event_bus_reset(0,TUSB_SPEED_FULL,false);}return r;}
static int32_t tracked_write(void*c,uint64_t t,uint64_t lba,uint32_t n,const void*in){++write_calls;write_blocks+=n;now_ms+=2+n;if(n>max_blocks)max_blocks=n;return real_volume->base.export_write(c,t,lba,n,in);}
static void sized_transfer(bool writing,uint8_t *data,uint32_t lba,unsigned blocks){
 const unsigned bytes=blocks*512;command(writing?0x2a:0x28,bytes,!writing,lba,blocks,0);
 for(unsigned at=0;at<bytes;){
  unsigned dir=writing?0:1;assert(ep[1][dir].pending&&!ep[1][dir].stalled);
  unsigned n=ep[1][dir].length;assert(n && !(n%512) && n<=bytes-at);
  if(!writing)memcpy(data+at,ep[1][dir].buffer,n);
  complete(writing?1:0x81,writing?data+at:NULL,n);assert(poll()==0);at+=n;++transfers;
 }
 assert(csw(true)==0);directory_sd_frozen();
}
static void transfer(bool writing,uint8_t *data){sized_transfer(writing,data,100000,128);}
int main(int argc,char **argv){
 real_volume=directory_sd_start();volume=*real_volume;
 volume.begin_prepare=real_begin;volume.base.export_end=real_end;
 volume.base.export_read=tracked_read;volume.base.export_write=tracked_write;
 connect_provider();configure();directory_sd_frozen();
 if(argc==2) {
  const char *mode=argv[1];uint8_t bytes[4096];memset(bytes,0xa5,sizeof(bytes));
  uint8_t original[4096];memcpy(original,card_image+100000u*512,sizeof(original));
  unsigned rd=directory_sd_reads(),wr=directory_sd_writes();
  if(!strcmp(mode,"deadline")) {
   queue_reset_in_read=true;command(0x28,4096,true,100000,8,0);
   assert(directory_sd_reads()==rd+1 && !risc_msc_command_pending() && tud_task_event_ready());
   risc_usb_device_msc_diagnostics_v2 info={.base={.struct_size=sizeof(info)}};
   assert(risc_usb_device_msc_diagnostics(api)->diagnostics(NULL,token,&info.base)==0);
   assert(info.base.last_pump_passes==1 && info.max_io_ms==10);
   assert(poll()==0 && !risc_msc_command_pending() && directory_sd_reads()==rd+1);
   assert(sd_owned && phy_owned);assert(api->end(NULL,token,RISC_USB_MSC_END_CABLE_REMOVED)==0);
   assert(t5_driver_get(2)->quiesce());directory_sd_finish();puts("PASS deadline: one ten-ms modeled IO returns before queued reset processing; event hook aborts immediately");return 0;
  }
  if(strstr(mode,"error")) {
   bool reading=!strcmp(mode,"read-error");bulk_fault(reading?1:!strcmp(mode,"write-error")?2:3);
   if(reading) { /* command() expects success: enqueue the same production CBW manually. */
    msc_cbw_t cbw={.signature=MSC_CBW_SIGNATURE,.tag=++tag,.total_bytes=4096,.dir=0x80,.cmd_len=10};
    cbw.command[0]=0x28;cbw.command[3]=1;cbw.command[4]=0x86;cbw.command[5]=0xa0;cbw.command[8]=8;
    complete(1,&cbw,sizeof(cbw));assert(poll()==RISC_USB_MSC_RETAINED);
   } else {command(0x2a,4096,false,100000,8,0);complete(1,bytes,4096);assert(poll()==RISC_USB_MSC_RETAINED);}
   assert(sd_owned && phy_owned && usb_live && status.state==RISC_USB_MSC_FAULT_RETAINED);bulk_retained();
   assert(directory_sd_reads()-rd==(reading?1u:0u) && directory_sd_writes()-wr==(reading?0u:1u));
   assert(tud_msc_read10_cb(0,100000,0,bytes,4096)<0 && tud_msc_write10_cb(0,100000,0,bytes,4096)<0);
   assert(directory_sd_reads()-rd==(reading?1u:0u) && directory_sd_writes()-wr==(reading?0u:1u));
   if(!strcmp(mode,"partial-write-error")){assert(!memcmp(card_image+100000u*512,bytes,512));assert(!memcmp(card_image+100000u*512+512,original+512,3584));}
   else assert(!memcmp(card_image+100000u*512,original,4096));
   assert(!t5_driver_get(2)->quiesce());printf("PASS %s: one native attempt, custody retained, no replay\n",mode);return 0;
  }
  const bool reading=!strcmp(mode,"short-in");
  command(reading?0x28:0x2a,4096,reading,100000,8,0);
  if(!strcmp(mode,"queued-reset")) {
   memset(ep,0,sizeof(ep));dcd_event_bus_reset(0,TUSB_SPEED_FULL,false);assert(poll()==0);
   assert(!risc_msc_command_pending() && sd_owned && phy_owned && directory_sd_writes()==wr);
  } else {
   if(!strcmp(mode,"failed-out")) {memcpy(ep[1][0].buffer,bytes,4096);ep[1][0].pending=false;dcd_event_xfer_complete(0,1,4096,XFER_RESULT_FAILED,false);}
   else complete(reading?0x81:1,reading?NULL:bytes,!strcmp(mode,"aligned-short-out")?512:511);
   assert(poll()==0);
   if(reading){uint8_t clear[8]={2,TUSB_REQ_CLEAR_FEATURE,0,0,0x81,0,0,0};dcd_event_setup_received(0,clear,false);assert(poll()==0);complete(0x80,NULL,0);assert(poll()==0);}
   assert(csw(false)==MSC_CSW_STATUS_PHASE_ERROR);
   assert(directory_sd_writes()==wr && !memcmp(card_image+100000u*512,original,4096));
   assert(sd_owned && phy_owned && usb_live);
  }
  assert(api->end(NULL,token,RISC_USB_MSC_END_CABLE_REMOVED)==0);assert(t5_driver_get(2)->quiesce());directory_sd_finish();
  printf("PASS %s: no incomplete write, explicit disconnect cleanup\n",mode);return 0;
 }
 uint8_t original[65536],pattern[65536],result[65536],eight[4096];
 memcpy(original,card_image+100000u*512u,sizeof(original));
 for(unsigned i=0;i<sizeof(pattern);++i)pattern[i]=(uint8_t)(i*37u+19u);
 const uint32_t before_hash=directory_sd_hash();
 const unsigned rd=directory_sd_reads(),wr=directory_sd_writes();
 /* Each phase moves one MiB using sixteen host READ/WRITE10 64 KiB commands. */
 for(unsigned i=0;i<16;++i){
  transfer(false,result);assert(!memcmp(original,result,sizeof(result)));
  transfer(true,pattern);transfer(false,result);assert(!memcmp(pattern,result,sizeof(result)));
  transfer(true,original);
 }
 const unsigned native_reads=directory_sd_reads()-rd,native_writes=directory_sd_writes()-wr;
 assert(read_blocks==4096 && write_blocks==4096 && read_calls==512 && write_calls==512 && max_blocks==8);
 assert(native_reads==512 && native_writes==512 && transfers==1024);
 unsigned before=directory_sd_reads();
 assert(real_volume->base.export_read(NULL,sd_token,100000,8,eight)==RISC_STORAGE_EXPORT_READY);
 unsigned direct_eight_calls=directory_sd_reads()-before;assert(direct_eight_calls==1);
 assert(directory_sd_hash()==before_hash);
 const unsigned bulk_reads=read_calls,bulk_writes=write_calls,bulk_transfers=transfers;
 /* Unaligned client addresses, non-batch-aligned LBAs, final short batches,
  * and the very last card sector, with guard bytes and exact restoration. */
 uint8_t unaligned[17*512+2],saved[17*512];
 const unsigned sizes[]={1,2,7,8,9,15,17};
 for(unsigned i=0;i<sizeof(sizes)/sizeof(sizes[0]);++i){unsigned n=sizes[i];uint32_t lba=i?100001:131071;
  memcpy(saved,card_image+lba*512u,n*512);memset(unaligned,0x6d,sizeof(unaligned));
  sized_transfer(true,unaligned+1,lba,n);memset(unaligned+1,0,n*512);sized_transfer(false,unaligned+1,lba,n);
  for(unsigned j=0;j<n*512;++j)assert(unaligned[1+j]==0x6d);assert(unaligned[0]==0x6d && unaligned[n*512+1]==0x6d);
  sized_transfer(true,saved,lba,n);
 }
 unsigned no_io=read_calls+write_calls;
 assert(tud_msc_read10_cb(0,100000,1,eight,512)<0 && tud_msc_write10_cb(0,100000,1,eight,512)<0);
 assert(tud_msc_read10_cb(0,100000,0,eight,511)<0 && tud_msc_write10_cb(0,100000,0,eight,511)<0);
 assert(tud_msc_read10_cb(0,100000,0,eight,0)<0 && tud_msc_write10_cb(0,100000,0,eight,4608)<0);
 assert(tud_msc_read10_cb(0,131071,0,eight,1024)<0 && tud_msc_write10_cb(0,UINT32_MAX,0,eight,512)<0);
 assert(no_io==read_calls+write_calls && directory_sd_hash()==before_hash);

 command(0x1b,0,false,0,0,2);assert(csw(false)==0 && sd_owned && phy_owned);
 complete(0x81,NULL,13);assert(poll()==0 && status.state==RISC_USB_MSC_EJECTED);
 assert(!sd_owned&&!phy_owned&&!usb_live);
 risc_usb_device_msc_diagnostics_v2 timing={.base={.struct_size=sizeof(timing)}};
 assert(risc_usb_device_msc_diagnostics(api)->diagnostics(NULL,token,&timing.base)==0);
 assert(timing.total_io_ms>0 && timing.max_io_ms==10 && timing.eject_complete);
 assert(api->end(NULL,token,RISC_USB_MSC_END_CANCEL_WAITING)==0);assert(t5_driver_get(2)->quiesce());directory_sd_finish();
 printf("{\"hardware_timing\":false,\"host_commands\":64,\"command_bytes\":65536,\"read_bytes\":2097152,\"write_bytes\":2097152,\"export_read_calls\":%u,\"export_write_calls\":%u,\"max_export_blocks\":%u,\"sdmmc_read_calls\":%u,\"sdmmc_write_calls\":%u,\"data_endpoint_transfers\":%u,\"direct_8block_sdmmc_calls\":%u,\"card_restored\":true,\"host_eject_remount\":true}\n",bulk_reads,bulk_writes,max_blocks,native_reads,native_writes,bulk_transfers,direct_eight_calls);
}
