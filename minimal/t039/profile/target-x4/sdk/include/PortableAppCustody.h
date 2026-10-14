#pragma once
#include "RiscRuntimeV1.h"
#ifdef PORTABLE_NATIVE_TIME_TOOLBAR
#include "PortableNativeCustody.h"
#define PORTABLE_APP_RUNTIME() portable_app_custody_runtime()
#define PORTABLE_APP_RETAINED() portable_adapter_retained()
#define PORTABLE_APP_RETAIN() portable_adapter_retain()
#else
#define PORTABLE_APP_RUNTIME() risc_runtime_get_api(1)
#define PORTABLE_APP_RETAINED() false
#define PORTABLE_APP_RETAIN() ((void)0)
#endif
