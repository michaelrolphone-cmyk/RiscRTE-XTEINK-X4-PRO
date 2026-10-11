#!/usr/bin/env python3
import hashlib,json,pathlib,subprocess,sys,os
repo,build,old,new=map(pathlib.Path,sys.argv[1:])
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()=='3b90cd11cf0ff4e8116bb54d2d9eb9c7c67a148b'
assert not subprocess.check_output(['git','-C',str(repo),'status','--porcelain','--untracked-files=no'],text=True).strip()
result={'sanitizer_environment':{k:os.environ.get(k) for k in ('SANITIZE','ASAN_OPTIONS','UBSAN_OPTIONS')},'compiler':subprocess.check_output(['c++','--version'],text=True).splitlines()[0],'runtime':'3b90cd11cf0ff4e8116bb54d2d9eb9c7c67a148b','scope':'actual Runtime/Graph/ModuleV2 selected bytes, production ELF validator; host provider substitutes final Xtensa execution','cases':[],'providers':[]}
oldboot=json.loads((old/'store/boot.json').read_text());newboot=json.loads((new/'store/boot.json').read_text())
for manifest,required in [('wifi/manifest.json',['async_begin','async_poll','async_cancel','service_begin']),('sharing-ble/manifest.json',['api_open_network','api_peer_network'])]:
 previous=next(d for d in oldboot['drivers'] if d['manifest']==manifest)
 candidate=next(d for d in newboot['drivers'] if d['manifest']==manifest)
 assert previous['image_source']['internal_fallback'] is True and candidate['image_source']['internal_fallback'] is True
 assert previous['image_source']['volume_instance']==candidate['image_source']['volume_instance']==9
 oldpath=previous['image_source']['path'];newpath=candidate['image_source']['path']
 m=json.loads((new/'store'/manifest).read_text())
 current=new/'store'/pathlib.Path(manifest).parent/m['file_name']
 stale=old/'SD'/oldpath;selected=new/'SD'/newpath
 assert sha(current)==sha(selected) and sha(stale)!=sha(current)
 assert sha(new/'SD'/oldpath)==sha(stale)
 assert 'image-'+sha(selected)+'.elf'==selected.name
 symbols=subprocess.check_output(['readelf','-Ws',str(selected)],text=True)
 assert all(any(line.split()[-1:]==[name] and ' FUNC ' in line for line in symbols.splitlines()) for name in required)
 result['providers'].append({'manifest':manifest,'version':m['version'],'old_path':oldpath,'old_sha256':sha(stale),'current_path':newpath,'current_sha256':sha(current),'required_contract_symbols':required})
 cases=[('stale-sd-current-internal',old/'SD',oldpath,'present',stale),('old-policy-card-absent',old/'SD',oldpath,'absent',current),('immutable-current-sd-with-stale-present',new/'SD',newpath,'present',selected),('current-policy-card-absent',new/'SD',newpath,'absent',current),('current-file-missing-stale-present',new/'SD',newpath,'missing',current),('current-file-corrupt-stale-present',new/'SD',newpath,'corrupt',current)]
 for name,sd,path,mode,expected in cases:
  out=subprocess.check_output([str(build/'test'),str(build),str(sd),path,mode,str(expected),str(current)],text=True)
  print(manifest,name,out.strip(),flush=True)
  result['cases'].append({'provider':manifest,'case':name,'mode':mode,'expected_sha256':sha(expected),'passed':True,'output':out.strip()})
result['proof_source_sha256']={p.name:sha(p) for p in pathlib.Path(__file__).parent.iterdir() if p.is_file() and p.suffix in ('.cpp','.c','.py','.sh')}
(build/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
print('12 exact-byte SD/internal selection cases PASS; final Xtensa provider execution remains device-only')
