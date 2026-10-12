#!/usr/bin/env python3
"""Inspect actual selected resident owner policy entry frames and static custody."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--baseline-elf',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
r=json.loads((a.build/'owner-build-record.json').read_text());elf=a.build/'default.elf';debug=elf;prefix=r['compiler_path'].removesuffix('gcc');sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(elf)==r['sha256'];functions={};symbols={}
for line in subprocess.check_output([prefix+'nm','-S',str(debug)],text=True).splitlines():
 c=line.split()
 if len(c)!=4:continue
 address,size,kind,name=c
 if kind in 'tT':functions.setdefault(int(address,16),[]).append(name)
 if name in {'resident_policy_requested','resident_policy_input_continuity'} and kind in 'bBdD':symbols[name]={'bytes':int(size,16),'static_storage':True,'symbol_kind':kind}
frames={}
for line in subprocess.check_output([prefix+'objdump','-d',str(debug)],text=True).splitlines():
 m=re.match(r'^\s*([0-9a-f]+):.*\bentry\s+a1,\s*(0x[0-9a-f]+|[0-9]+)',line)
 if m and int(m[1],16) in functions:
  for name in functions[int(m[1],16)]:frames[name]=int(m[2],0)
checkpoint={n:v for n,v in frames.items() if n in {'resident_dispatch','resident_policy_dispatch','resident_policy_due','portable_resident_run_foreground'}}
assert {'resident_dispatch','portable_resident_run_foreground'}<=set(checkpoint)
assert sha(a.baseline_elf)==r['predecessor']['sha256']
baseline_functions={};baseline_frames={}
for line in subprocess.check_output([prefix+'nm','-S',str(a.baseline_elf)],text=True).splitlines():
 c=line.split()
 if len(c)==4 and c[2] in 'tT':baseline_functions[int(c[0],16)]=c[3]
for line in subprocess.check_output([prefix+'objdump','-d',str(a.baseline_elf)],text=True).splitlines():
 m=re.match(r'^\s*([0-9a-f]+):.*\bentry\s+a1,\s*(0x[0-9a-f]+|[0-9]+)',line)
 if m and int(m[1],16) in baseline_functions:baseline_frames[baseline_functions[int(m[1],16)]]=int(m[2],0)
assert all(v==baseline_frames[n] for n,v in checkpoint.items()) and symbols and all(s['bytes']<=4 for s in symbols.values())
result=dict(schema='lists.resident-owner.target-stack.v1',device=r['device'],system_source=r['system_overlay_commit'],target_elf_sha256=sha(elf),debug_elf_sha256=sha(debug),continuity_entry_frames_bytes=checkpoint,maximum_continuity_frame_bytes=max(checkpoint.values()),all_entry_frames_maximum_bytes=max(frames.values()),static_continuity_storage=symbols,per_frame_regression_checks_passed=True,target_instructions_executed=False,peak_call_chain_stack_usage_proven=False,policy_helper_inlined_into='resident_dispatch',baseline_elf_sha256=sha(a.baseline_elf),baseline_entry_frames_bytes={n:baseline_frames[n] for n in checkpoint},all_relevant_frames_identical_to_predecessor=True)
a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
