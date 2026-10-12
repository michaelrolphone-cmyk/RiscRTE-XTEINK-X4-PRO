#!/usr/bin/env python3
"""Source-bound positive and fault-injected .100 pairing/preservation checks."""
import argparse,copy,json,tempfile
from pathlib import Path
import compose_keyboard_100 as c
p=argparse.ArgumentParser()
for n in ('baseline','scene','text','system-source','runtime-source'):p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args();base,old,sd,parts,full=c.baseline(a.baseline)
modules={k:c.validate_module(getattr(a,k),k,old,a.system_source,a.runtime_source) for k in c.PROVIDERS}
new,new_sd,details=c.payload(old,sd,modules,'a'*40)
assert len(new)==len(old)==106 and len(new_sd)==87
assert {n for n in old if old[n]!=new[n]}==c.CHANGED
assert all(new_sd[n]==v for n,v in sd.items())
assert json.loads(new['cohort.json'])==dict(json.loads(old['cohort.json']),version=c.VERSION,source_revision='a'*40)
assert all(new[n]==old[n] for n in old if n not in c.CHANGED)
def rejected(fn):
 try:fn()
 except (ValueError,KeyError):return
 raise AssertionError('Fault was accepted')
bad=dict(modules);v=list(bad['scene']);v[1]=v[1]+b'x';bad['scene']=tuple(v);rejected(lambda:c.payload(old,sd,bad,'a'*40))
bad=dict(sd);previous=details[0]['previous_path'];bad[previous]=b'wrong';rejected(lambda:c.payload(old,bad,modules,'a'*40))
bad=dict(sd);bad[details[0]['path']]=modules['scene'][1];rejected(lambda:c.payload(old,bad,modules,'a'*40))
bad=dict(old);boot=json.loads(old['boot.json']);next(r for r in boot['drivers'] if r['manifest']=='ui-text/manifest.json')['image_source']['internal_fallback']=False;bad['boot.json']=c.encoded(boot);rejected(lambda:c.payload(bad,sd,modules,'a'*40))
with tempfile.TemporaryDirectory(prefix='keyboard-provider-fault-') as tmp:
 out=Path(tmp)
 for name in ('manifest.json','driver.elf','build.json'):(out/name).write_bytes((a.scene/name).read_bytes())
 manifest=json.loads((out/'manifest.json').read_bytes());manifest['version']='0.4.1';(out/'manifest.json').write_bytes(c.encoded(manifest));rejected(lambda:c.validate_module(out,'scene',old,a.system_source,a.runtime_source))
 manifest['version']='0.4.2';manifest['requires'].append({'api':1,'capability':'extra.authority'});(out/'manifest.json').write_bytes(c.encoded(manifest));rejected(lambda:c.validate_module(out,'scene',old,a.system_source,a.runtime_source))
 (out/'manifest.json').write_bytes((a.scene/'manifest.json').read_bytes());record=json.loads((out/'build.json').read_bytes());record['sdk_sha256']['SceneKeyboardV1.h']='0'*64;(out/'build.json').write_bytes(c.encoded(record));rejected(lambda:c.validate_module(out,'scene',old,a.system_source,a.runtime_source))
print('PASS: paired source/SDK, exact .99 preservation and seven wrong-payload/authority/lineage/SDK faults')
