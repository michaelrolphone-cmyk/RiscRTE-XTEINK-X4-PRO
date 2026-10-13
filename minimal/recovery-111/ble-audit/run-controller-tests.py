import subprocess,json
from pathlib import Path
root=Path(__file__).resolve().parents[1];u=root/'RiscRTE-Utilities-ble-selected';s=root/'RiscRTE-System-ble-selected';out=root/'x4-ble-audit/controller';out.mkdir(exist_ok=True)
includes=[u/'Apps',u/'lib/Bluetooth/include',s/'lib/PortableApps/include',s/'lib/NativeApps/include',s/'lib/PortableApps/src']
results=[]
for san in (False,True):
 for name,source,pad in [('model','hid_model_test.c',None),('gestures','hid_touchpad_gesture_test.c',None),('touchpad','hid_app_test.c',1),('buttons','hid_app_test.c',0),('resident-touchpad','hid_resident_gate_test.c',1),('resident-buttons','hid_resident_gate_test.c',0)]:
  exe=out/(name+('-ubsan' if san else '-normal'))
  cmd=[str(root/'x4-ble-audit/host-cc.py'),'-std=c11','-O1','-Wall','-Wextra','-Werror',*['-I'+str(p) for p in includes]]
  if san:cmd+=['-fsanitize=undefined','-fno-sanitize-recover=all']
  if pad is not None:cmd+=['-DHID_TOUCHPAD='+str(pad)]
  subprocess.run([*cmd,str(u/'tests'/source),'-o',str(exe)],check=True)
  r=subprocess.run([str(exe)],capture_output=True,text=True);exe.with_suffix('.log').write_text(r.stdout+r.stderr);results.append({'test':exe.name,'exit':r.returncode});print(exe.name,r.returncode,flush=True)
(out/'results.json').write_text(json.dumps(results,indent=2)+'\n');assert all(r['exit']==0 for r in results)
