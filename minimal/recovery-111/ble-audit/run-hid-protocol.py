import subprocess,re,json,os
from pathlib import Path
root=Path(__file__).resolve().parents[1]
drivers=root/'RiscRTE-Drivers-ble-audit'
scenarios=re.search(r'for scenario in (.*?); do',(drivers/'test/run_ble_hid_test.sh').read_text()).group(1).split()
mode=os.environ.get('AUDIT_SANITIZE','normal')
out=root/'x4-ble-audit'/('protocol-'+mode);out.mkdir(exist_ok=True)
lib=drivers/'build'/('ble-hid-san' if mode!='normal' else 'ble-hid-host')/'driver.so'
results=[]
for s in scenarios:
 r=subprocess.run([str(root/'x4-ble-audit/venv/bin/python'),str(drivers/'test/ble_hid_protocol_test.py'),str(lib),s],capture_output=True,text=True)
 (out/(s+'.log')).write_text(r.stdout+r.stderr);results.append({'case':s,'exit':r.returncode});print(s,r.returncode,flush=True)
(out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
assert all(r['exit']==0 for r in results)
