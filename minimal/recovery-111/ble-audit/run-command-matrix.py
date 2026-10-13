"""Use selected historical fixtures, adapting only a redundant SDK typedef."""
from pathlib import Path
import sys
root=Path(__file__).resolve().parents[1]
script=root/'RiscRTE-Utilities-ble-selected/scripts/test_hid_buttons_universal_recovery.py'
body=script.read_text()
needle="src = (root / 'test/native_apps/hid_renderer_test.c').read_text()"
assert body.count(needle)==1
body=body.replace(needle,needle+"\nsrc=src.replace('typedef struct {alarm_service_v1 service;uint32_t output_modes;} alarm_service_outputs_v1;', '')")
exec(compile(body,str(script),'exec'),{'__file__':str(script),'__name__':'__main__'})
