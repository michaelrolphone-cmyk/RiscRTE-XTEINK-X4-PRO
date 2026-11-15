#!/usr/bin/env python3
"""Actual complete-product Runtime admission; positive singleton and duplicate-owner negatives."""
import argparse,hashlib,json,pathlib,shutil,subprocess,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[2]
def require(ok,message):
 if not ok:raise ValueError(message)
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def tree(root):return {p.relative_to(root).as_posix():digest(p) for p in sorted(root.rglob('*')) if p.is_file()}
def source(root,path):
 p=root/path
 require(not pathlib.Path(path).is_absolute() and p.resolve().is_relative_to(root.resolve()),'Unsafe manifest path')
 return p
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('admission','before','after','output'):p.add_argument('--'+name,type=pathlib.Path,required=True)
 a=p.parse_args();a.before=a.before.resolve();a.after=a.after.resolve();a.admission=a.admission.resolve()
 require(not a.output.exists(),'New receipt directory required');a.output.mkdir(parents=True)
 original_before,original_after=tree(a.before),tree(a.after)
 boot=json.loads((a.after/'boot.json').read_bytes());rows=boot['drivers'];selected={}
 expected={
  'x4pro-home-power-singleton':{'x4.power':17,'display.power':0},
  'x4pro-home-display-power-singleton':{'display.output':3,'storage.volume':9,'display.frontlight':5,'x4.power':17}}
 for row in rows:
  manifest=json.loads(source(a.after,row['manifest']).read_bytes())
  if manifest['id'] not in expected:continue
  ident=manifest['id'];require(ident not in selected,'Duplicate bridge')
  require(row.get('instance_id',0)==0,'Bridge claims physical owner')
  require(not manifest.get('hardware_compatibility') and all(r['capability'] not in ('hardware.device','platform.sync') for r in manifest['requires']),'Singleton has hardware/sync authority')
  bindings=row.get('bindings',[])
  require(all(b['api']==1 for b in bindings) and len(bindings)==len(expected[ident]) and
    {b['capability']:b['instance_id'] for b in bindings}==expected[ident],'Wrong exact forwarding bindings')
  selected[ident]=row
 require(set(selected)==set(expected),'Both singleton bridges required')
 for instance in (3,5,9,17):
  require(sum(row.get('instance_id',0)==instance for row in rows)==1,'Original physical ownership must remain unique')
 receipts=[]
 def run(label,after,valid):
  q=subprocess.run([str(a.admission),str(a.before),str(after)],capture_output=True,text=True)
  (a.output/(label+'.log')).write_text(q.stdout+q.stderr)
  require(q.returncode==0,'Admission harness failed '+label)
  result=json.loads(q.stdout)
  require(result['prepared'] and result['hardware_calls']==result['storage_calls']==0,'Unexpected native I/O or baseline failure')
  if valid:require(result['cohort_validated'] and result['elf_count']>0 and result['retained_sd_serial_graph_bound'],'Singleton full graph rejected')
  else:require(not result['cohort_validated'] and result['error']=='duplicate package singleton/hardware owner','Expected precise duplicate-owner refusal')
  receipts.append({'case':label,'result':result})
 run('singleton-complete-product',a.after,True)
 for ident,instance,folder in [('x4pro-home-power-singleton',17,'x4pro_home_power'),('x4pro-home-display-power-singleton',3,'x4pro_home_display_power')]:
  with tempfile.TemporaryDirectory(prefix='home-duplicate-owner-') as tmp:
   candidate=pathlib.Path(tmp)/'after';shutil.copytree(a.after,candidate)
   changed=json.loads((candidate/'boot.json').read_bytes())
   row=next(r for r in changed['drivers'] if r['manifest']==selected[ident]['manifest'])
   row['instance_id']=instance;row.pop('bindings',None)
   manifest=json.loads((ROOT/'minimal/drivers'/folder/'manifest.json').read_bytes())
   manifest['id']=ident
   source(candidate,row['manifest']).write_text(json.dumps(manifest))
   (candidate/'boot.json').write_text(json.dumps(changed))
   run('duplicate-'+str(instance),candidate,False)
 require(tree(a.before)==original_before and tree(a.after)==original_after,'Product input mutated')
 (a.output/'receipt.json').write_text(json.dumps({'schema':1,'admission_sha256':digest(a.admission),
  'before':original_before,'after':original_after,'cases':receipts,'hardware_tested':False},indent=2)+'\n')
 print('Actual complete-product singleton graph and physical-owner collision negatives PASS')
if __name__=='__main__':main()
