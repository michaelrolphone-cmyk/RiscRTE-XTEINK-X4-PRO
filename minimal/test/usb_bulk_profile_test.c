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
static const risc_storage_volume_api_v1_export_prepare *real_volume;
static uint64_t sd_token;
static unsigned read_calls,write_calls,read_blocks,write_blocks,max_blocks,transfers;
static int32_t real_begin(void*c,uint64_t*t){int32_t r=real_volume->begin_prepare(c,t);assert(r==RISC_STORAGE_EXPORT_PREPARING);sd_token=*t;sd_owned=true;mark('M');return r;}
static int32_t real_end(void*c,uint64_t t){assert(!usb_live);int32_t r=real_volume->base.export_end(c,t);if(!r){sd_owned=false;mark('E');}return r;}
static int32_t tracked_read(void*c,uint64_t t,uint64_t lba,uint32_t n,void*out){++read_calls;read_blocks+=n;if(n>max_blocks)max_blocks=n;return real_volume->base.export_read(c,t,lba,n,out);}
static int32_t tracked_write(void*c,uint64_t t,uint64_t lba,uint32_t n,const void*in){++write_calls;write_blocks+=n;if(n>max_blocks)max_blocks=n;return real_volume->base.export_write(c,t,lba,n,in);}
static void transfer(bool writing,uint8_t *data){
 command(writing?0x2a:0x28,65536,!writing,100000,128,0);
 for(unsigned at=0;at<65536;){
  unsigned dir=writing?0:1;assert(ep[1][dir].pending&&!ep[1][dir].stalled);
  unsigned n=ep[1][dir].length;assert(n && !(n%512) && n<=65536-at);
  if(!writing)memcpy(data+at,ep[1][dir].buffer,n);
  complete(writing?1:0x81,writing?data+at:NULL,n);assert(poll()==0);at+=n;++transfers;
 }
 assert(csw(true)==0);directory_sd_frozen();
}
int main(void){
 real_volume=directory_sd_start();volume=*real_volume;
 volume.begin_prepare=real_begin;volume.base.export_end=real_end;
 volume.base.export_read=tracked_read;volume.base.export_write=tracked_write;
 connect_provider();configure();directory_sd_frozen();
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
 assert(read_blocks==4096 && write_blocks==4096 && read_calls==4096 && write_calls==4096 && max_blocks==1);
 assert(native_reads==4096 && native_writes==4096 && transfers==8192);
 unsigned before=directory_sd_reads();
 assert(real_volume->base.export_read(NULL,sd_token,100000,8,eight)==RISC_STORAGE_EXPORT_READY);
 unsigned direct_eight_calls=directory_sd_reads()-before;assert(direct_eight_calls==8);
 assert(directory_sd_hash()==before_hash);
 command(0x1b,0,false,0,0,2);assert(csw(false)==0 && sd_owned && phy_owned);
 complete(0x81,NULL,13);assert(poll()==0 && status.state==RISC_USB_MSC_EJECTED);
 assert(!sd_owned&&!phy_owned&&!usb_live);
 assert(api->end(NULL,token,RISC_USB_MSC_END_CANCEL_WAITING)==0);assert(t5_driver_get(2)->quiesce());directory_sd_finish();
 printf("{\"hardware_timing\":false,\"host_commands\":64,\"command_bytes\":65536,\"read_bytes\":2097152,\"write_bytes\":2097152,\"export_read_calls\":%u,\"export_write_calls\":%u,\"max_export_blocks\":%u,\"sdmmc_read_calls\":%u,\"sdmmc_write_calls\":%u,\"data_endpoint_transfers\":%u,\"direct_8block_sdmmc_calls\":%u,\"card_restored\":true,\"host_eject_remount\":true}\n",read_calls,write_calls,max_blocks,native_reads,native_writes,transfers,direct_eight_calls);
}
