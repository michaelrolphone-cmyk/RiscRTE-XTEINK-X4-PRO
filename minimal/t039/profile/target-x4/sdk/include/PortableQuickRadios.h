#pragma once
#include "PortableQuickActions.h"
#include "PortableRadioPolicy.h"
#include "PortableBluetoothControl.h"
#include "WifiApi.h"
typedef struct {uint8_t flags;bool valid,available;} pqa_radios;
bool pqa_radios_load(pqa_radios*,pqa_state*,const risc_runtime_api_v1*);
bool pqa_radios_apply(pqa_radios*,pqa_state*,const risc_runtime_api_v1*,uint32_t);
bool pqa_radios_suspend(const risc_runtime_api_v1*);
bool pqa_radios_resume(pqa_radios*,pqa_state*,const risc_runtime_api_v1*);
