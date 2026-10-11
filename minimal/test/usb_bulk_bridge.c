/* Reuse the selected SD/FatFs ownership fixture and expose native failure
 * injection only. Production code and native API geometry remain unchanged. */
#include USB_DIRECTORY_BRIDGE_SOURCE
static bool partial_failure;
static bool partial_write(void *ctx,uint64_t t,uint64_t lba,uint32_t count,const void *in) {
 if(!partial_failure)return native_write(ctx,t,lba,count,in);
 native_check(t,lba,count);++native_writes;
 memcpy(card_image+lba*512,in,512); /* uncertain media may have accepted a prefix */
 return false;
}
void bulk_fault(unsigned mode) {
 native_read_bad=mode==1;native_write_bad=mode==2;
 partial_failure=mode==3;
 native_extension.sdmmc.write=partial_write;
}
void bulk_retained(void) {
 assert(export_state==EXPORT_RETAINED && !mounted && native_live && sdmmc_token);
 assert_export_frozen();
}
