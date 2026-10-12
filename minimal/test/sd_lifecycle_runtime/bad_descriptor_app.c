// Deliberately invalid descriptor; callbacks match the repository fixture.
#include <RiscResidentShellV1.h>
extern int test_resident_init(unsigned);
extern void test_resident_main(unsigned,unsigned*);
extern void test_resident_fini(unsigned);
extern void test_resident_map(unsigned);
extern void test_resident_unmap(unsigned);
static unsigned visits;
__attribute__((visibility("default"))) const risc_resident_app_descriptor_v1_t risc_resident_app_descriptor_v1={2,sizeof(risc_resident_app_descriptor_v1_t),RISC_RESIDENT_ROLE_FOREGROUND,0};
__attribute__((constructor)) static void mapped(void){test_resident_map(1);}
__attribute__((destructor)) static void unmapped(void){test_resident_unmap(1);}
__attribute__((visibility("default"))) int app_module_init(void){return test_resident_init(1);}
__attribute__((visibility("default"))) void app_main(void){test_resident_main(1,&visits);}
__attribute__((visibility("default"))) void app_module_fini(void){test_resident_fini(1);}
