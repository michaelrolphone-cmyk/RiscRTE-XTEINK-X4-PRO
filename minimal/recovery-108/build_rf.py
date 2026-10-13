#!/usr/bin/env python3
"""Reproduce the qualified X4 RF 0.3.5 component, never its historical image."""
import argparse,hashlib,importlib.util,json,shlex,shutil,subprocess,sys
from pathlib import Path
from compact_current_elf import compact
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def git(p,*args):return subprocess.check_output(['git','-C',str(p),*args],text=True).strip()
def require(ok,msg):
 if not ok:raise ValueError(msg)
p=argparse.ArgumentParser(description=__doc__)
for n in ['system','utilities','runtime-sdk','compiler','output']:p.add_argument('--'+n,type=Path,required=True)
a=p.parse_args()
for n,v in vars(a).items():setattr(a,n,v.resolve())
q=json.loads((HERE/'qualified-target.json').read_text())
roots={'system-apps':a.system,'utilities':a.utilities,'runtime':a.runtime_sdk,'generated':a.output}
for owner in ['system-apps','utilities','runtime']:
 require(git(roots[owner],'rev-parse','HEAD')==q['sources'][owner],'Wrong source '+owner)
 require(not git(roots[owner],'status','--porcelain','--untracked-files=no'),'Dirty source '+owner)
require(not a.output.exists(),'Use a fresh output directory')
a.output.mkdir(parents=True);(a.output/'sdk/include').mkdir(parents=True)
provenance={}
for key,row in q['target_dependencies'].items():
 owner,rel=key.split(':',1)
 if owner!='generated':
  require(owner in roots and sha(roots[owner]/rel)==row['sha256'],'Qualified source differs: '+key)
 elif rel.startswith('sdk/include/'):
  name=Path(rel).name;found=[]
  for source_owner in ['system-apps','utilities','runtime']:
   for source in roots[source_owner].rglob(name):
    if source.is_file() and sha(source)==row['sha256']:found.append((source_owner,source))
  require(found,'Qualified header unavailable: '+rel)
  source_owner,source=found[0];shutil.copyfile(source,a.output/rel)
  provenance[rel]={'owner':source_owner,'path':str(source.relative_to(roots[source_owner])),'sha256':row['sha256']}
 else:
  require(rel=='catalog.c' and sha(HERE/rel)==row['sha256'],'Unexpected generated input: '+rel)
  shutil.copyfile(HERE/rel,a.output/rel)
shutil.copytree(a.system/'lib/PortableApps/time',a.output/'sdk/time')
def mapped(value):
 for owner,root in roots.items():value=value.replace(q['source_roots'][owner],str(root))
 return value
command=[mapped(v) for v in q['command']];command[0]=str(a.compiler)
(a.output/'exports.map').write_text('{global:'+';'.join(sorted(q['exports']))+';local:*;};\n')
compiler=subprocess.check_output([str(a.compiler),'--version'],text=True).splitlines()[0]
require(compiler==q['compiler'],'Wrong compiler generation')
subprocess.run(command,check=True)
normalizer=a.utilities/'scripts/normalize_xtensa_relocations.py'
require(sha(normalizer)=='f71d9ca3b267166bc69d0e4853463774a8dde5384924132e1aca0e0c2f3a965f','Wrong relocation normalizer')
spec=importlib.util.spec_from_file_location('rf_normalizer',normalizer);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
elf=a.output/'waterfall.elf';normalization=m.normalize(elf);compaction=compact(elf,str(a.compiler),debug_path=a.output/'debug/waterfall.elf')
require(sha(elf)==q['sha256'] and elf.stat().st_size==q['bytes'],'Target is not byte-identical to qualified X4 RF 0.3.5')
manifest=json.loads((HERE/'predecessor-manifest.json').read_text());require(manifest['version']=='0.3.4','Wrong delivered RF version');manifest['version']='0.3.5'
(a.output/'waterfall.json').write_text(json.dumps(manifest,indent=2)+'\n')
require(sha(a.output/'waterfall.json')==q['manifest_sha256'],'Qualified manifest differs')
record=dict(schema='x4.rf-035-source-reproduction',sources={k:q['sources'][k] for k in ['system-apps','utilities','runtime']},compiler=compiler,command=command,defines=q['defines'],target_sha256=sha(elf),manifest_sha256=sha(a.output/'waterfall.json'),target_bytes=elf.stat().st_size,qualified_component_byte_identical=True,generated_header_provenance=provenance,relocation_normalization=normalization,compaction=compaction,native_rebuilt=False,hardware_tested=False)
(a.output/'build-record.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({k:v for k,v in record.items() if k not in ['command','generated_header_provenance','compaction']},indent=2))
