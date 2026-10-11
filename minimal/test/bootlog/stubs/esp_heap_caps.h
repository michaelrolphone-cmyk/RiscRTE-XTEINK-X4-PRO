#pragma once
#include <cstdlib>
#define MALLOC_CAP_SPIRAM 1
#define MALLOC_CAP_8BIT 2
#define MALLOC_CAP_INTERNAL 4
inline bool heap_caps_test_fail=false;
inline bool heap_caps_test_internal_fail=false;
inline void* heap_caps_malloc(size_t n,unsigned caps){return ((caps&MALLOC_CAP_INTERNAL)?heap_caps_test_internal_fail:heap_caps_test_fail)?nullptr:std::malloc(n);}
