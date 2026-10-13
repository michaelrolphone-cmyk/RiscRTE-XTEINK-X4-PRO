#include <cassert>
#include "cohort_elf_admission.h"
int main(int argc,char**argv){
 assert(argc>=3);bool driver=!strcmp(argv[1],"driver");unsigned n=0;
 assert(CohortElf::file(&n,argv[2],driver)&&n==1);
 CohortElf::safe=false;assert(!CohortElf::file(&n,argv[2],driver));CohortElf::safe=true;
 assert(!CohortElf::file(&n,argv[2],!driver));
 for(int i=3;i<argc;++i){CohortElf::missing=argv[i];assert(!CohortElf::file(&n,argv[2],driver));}return 0;
}