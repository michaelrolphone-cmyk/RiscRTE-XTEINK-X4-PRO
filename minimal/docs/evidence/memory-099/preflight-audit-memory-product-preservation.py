#!/usr/bin/env python3
"""Read-only independent .99 versus frozen .98 artifact/source preservation audit."""
import sys
sys.dont_write_bytecode=True
import hashlib,json,os,struct,subprocess,zipfile,zlib
from pathlib import Path
W=Path('/workspace/shared/x4-https-099-20261012')
C=W/'combined-preflight'; B=Path('/workspace/shared/x4-obd-098-final-delivery'); D=Path('/workspace/shared/x4-lifecycle-096-delivery')
P=W/'product';R=W/'runtime';N=W/'native-candidate';E=W/'evidence'
TOOLS=Path('/workspace/shared/watch-lifecycle-custody-20261012')
sha=lambda x:hashlib.sha256(x).hexdigest()
read=lambda p:json.loads(p.read_bytes())
def tree(p):return {str(f.relative_to(p)):f.read_bytes() for f in p.rglob('*') if f.is_file()}
def inv(t):return {p:sha(b) for p,b in sorted(t.items())}
def git(p,*args):return subprocess.check_output(['git','-C',str(p),*args],text=True).strip()
def identity(p):return {'commit':git(p,'rev-parse','HEAD'),'tree':git(p,'rev-parse','HEAD^{tree}'),'clean':not git(p,'status','--porcelain')}
checks=[]
def ck(name,value,detail=None):
 checks.append(dict(name=name,pass_=bool(value),detail=detail))
 if not value:raise AssertionError(name)
sources={'product':identity(P),'runtime':identity(R),'utilities':identity(W/'utilities-hollow'),'system':identity(Path('/workspace/shared/x4-obd-integration-20261012/system')),'native_platform':identity(Path('/workspace/shared/x4-obd-098-final-source'))}
lock=read(P/'minimal/memory-099-inputs.json');cr=read(C/'receipts/memory-composition.json');br=read(B/'receipts/obd-composition.json')
cb=next(C.glob('*FULL*.bin')).read_bytes();bb=next(B.glob('*FULL*.bin')).read_bytes()
cs,bs=tree(C/'store'),tree(B/'store');sd,bsd=tree(C/'SD'),tree(B/'SD');cp,bp=tree(C/'components'),tree(B/'components')
ck('frozen_098_identity',sha(bb)=='4f7be9d66fd9461c89f8df7d48b07bdd4da53870b8276d6ddf08ce9da9fd1797' and sha((B/'receipts/obd-composition.json').read_bytes())=='b6ea82b2e4acbb2f46d2310fe4ea447b1754c86722df9d8a95040a9e42263758')
ck('candidate_full_identity',len(cb)==len(bb)==0x1000000 and sha(cb)==cr['full_image_sha256'])
ck('source_lock',all(sources[k]['commit']==lock[k]['commit'] and sources[k]['tree']==lock[k]['tree'] and sources[k]['clean'] for k in ('runtime','utilities','system')))
ck('product_source',sources['product']['commit']==cr['product_source'] and sources['product']['tree']==cr['product_tree'] and git(P,'merge-base',cr['product_source'],lock['baseline_product'])==lock['baseline_product'])
ck('recipe_and_lock_identity',sha(subprocess.check_output(['git','-C',str(P),'show',cr['product_source']+':minimal/scripts/compose_memory_099.py']))==cr['recipe_sha256'] and sha((P/'minimal/memory-099-inputs.json').read_bytes())==cr['qualification_lock_sha256'] and (P/'minimal/memory-099-inputs.json').read_bytes()==(C/'receipts/qualification-lock.json').read_bytes())
for name,x,y,allowed,count in [('store',bs,cs,{'cohort.json','hollow_trail.json'},106),('SD',bsd,sd,{'Apps/hollow_trail/hollow_trail.elf','Apps/hollow_trail/manifest.json'},85)]:
 ck(name+'_exact_change_set',len(x)==len(y)==count and x.keys()==y.keys() and {k for k in x if x[k]!=y[k]}==allowed,{'paths':sorted(allowed),'preserved_files':count-len(allowed)})
 ck(name+'_receipts',inv(x)==br[name.lower()] and inv(y)==cr[name.lower()])
ck('component_change_set',cp.keys()==bp.keys() and {k for k in cp if cp[k]!=bp[k]}=={'bank_state.bin','bootfs.bin','firmware.bin'})
for folder,image,receipt,parts in [(B,bb,br,bp),(C,cb,cr,cp)]:
 for name,row in receipt['components'].items():
  raw=parts[name];ck(str(folder.name)+'_'+name,sha(raw)==row['sha256'] and len(raw)==row['bytes'] and image[row['offset']:row['offset']+len(raw)]==raw)
ranges=[(0,0x10000),(0x270000,0x2f0000),(0x800000,0xff2000),(0xff4000,0x1000000)]
ck('all_unrelated_flash_bytes',all(cb[lo:hi]==bb[lo:hi] for lo,hi in ranges),{'bytes':sum(hi-lo for lo,hi in ranges),'ranges':ranges})
ck('firmware_padding',cb[0x10000:0x270000]==cp['firmware.bin']+b'\xff'*(0x260000-len(cp['firmware.bin'])))
sys.path[:0]=[str(TOOLS/'scripts'),str(P/'minimal/scripts')]
from read_only_spiffs import read_image
ck('independent_flash_decode',read_image(cb[0x2f0000:0x800000],0x510000)==cs and read_image(bb[0x2f0000:0x800000],0x510000)==bs)
f=struct.unpack('<6I32s32sII',cp['bank_state.bin'][:96])
ck('independent_bank_state',f[:6]==(0x314b4252,1,0,len(cp['firmware.bin']),0x510000,2) and f[6]==hashlib.sha256(cp['firmware.bin']).digest() and f[7]==hashlib.sha256(cp['bootfs.bin']).digest() and f[8]==0 and f[9]==zlib.crc32(cp['bank_state.bin'][:92])&0xffffffff and cp['bank_state.bin'][96:]==b'\xff'*(8192-96))
def physical_map(data):
 names={};pages={}
 for base in range(0,len(data),4096):
  for k in range(15):
   obj=struct.unpack_from('<H',data,base+2*k)[0]
   if obj in (0,65535):continue
   ix=base//256+1+k;raw=data[ix*256:(ix+1)*256];ident,span,flags=struct.unpack_from('<HHB',raw);pages[ix]=(obj,span)
   if obj&0x8000 and span==0:names[obj&0x7fff]=raw[13:45].split(b'\0')[0].decode()[1:]
 return names,pages
oldnames,oldpages=physical_map(bp['bootfs.bin']);names,pages=physical_map(cp['bootfs.bin'])
changed_pages=[ix for ix in range(0x510000//256) if cp['bootfs.bin'][ix*256:(ix+1)*256]!=bp['bootfs.bin'][ix*256:(ix+1)*256]]
ck('physical_boot_packing',oldnames==names and oldpages==pages and all(ix in pages and not pages[ix][0]&0x8000 and names[pages[ix][0]] in {'cohort.json','hollow_trail.json'} for ix in changed_pages),{'changed_pages':changed_pages,'changed_files':[names[pages[ix][0]] for ix in changed_pages]})
packing,priorpacking=read(C/'receipts/packing.json'),read(B/'receipts/packing.json')
ck('packing_receipt',sha((C/'receipts/packing.json').read_bytes())==cr['packing_sha256'] and {k for k in packing if packing[k]!=priorpacking[k]}=={'sha256','alphabetical_reference_sha256'})
from current_bootfs import build
from boot_order_spiffs import build as ordered_build
packed,packrecord=ordered_build(cs,build)
ck('independent_packing_replay',packed==cp['bootfs.bin'] and packrecord==packing)
boot=json.loads(cs['boot.json']);oldboot=json.loads(bs['boot.json'])
ck('boot_authority_installation',cs['boot.json']==bs['boot.json'] and len(boot['drivers'])==33 and len(boot['app_capabilities'])==27 and 'shared_settings' not in boot['installation'])
for key,manifest,version in [('Home','default.json','0.4.13'),('Files97','file_browser.json','1.5.31'),('OBD98','obd_dashboard.json','0.2.1')]:
 ck(key+'_version_bytes_authority',json.loads(cs[manifest])['version']==version and cs[manifest]==bs[manifest])
ck('Home_Files_receipt_and_ELFs',all(cr[k]==br[k] for k in ('home_client','files_client')) and all(cs[f]==bs[f] for f in ('default.elf','file_browser.elf')) and len(next(r for r in boot['app_capabilities'] if r['manifest']=='file_browser.json')['grants'])==16)
ck('OBD_scene_serial_provenance',all(cr[k]==br[k] for k in ('obd_build','scene_build','serial_build')))
lifecycle=[]
for row in br['sd_lifecycle']:
 manifest=row['manifest'];smanifest=row['sd_manifest'];elf=row['image']
 ck('096_lifecycle_'+row['id'],cs[manifest]==(D/'store'/manifest).read_bytes()==sd[smanifest]==(D/'SD'/smanifest).read_bytes() and sd[elf]==(D/'SD'/elf).read_bytes() and sha(sd[elf])==row['elf_sha256'] and json.loads(cs[manifest])['version']==row['version'])
 lifecycle.append({'id':row['id'],'version':row['version'],'elf_sha256':sha(sd[elf]),'manifest_sha256':sha(cs[manifest])})
ck('096_lifecycle_receipt',cr['sd_lifecycle']==br['sd_lifecycle'])
oldh=json.loads(bs['hollow_trail.json']);newh=json.loads(cs['hollow_trail.json'])
ck('Hollow_manifest_only_version',oldh['version']=='1.2.1' and newh==dict(oldh,version='1.2.2') and cs['hollow_trail.json']==sd['Apps/hollow_trail/manifest.json'])
ck('Hollow_locked_artifacts',sha(cs['hollow_trail.json'])==lock['hollow']['manifest_sha256'] and sha(sd['Apps/hollow_trail/hollow_trail.elf'])==lock['hollow']['elf_sha256'] and sha((W/'hollow-target/hollow_trail/build.json').read_bytes())==lock['hollow']['build_receipt_sha256'])
cohort=json.loads(cs['cohort.json']);oldco=json.loads(bs['cohort.json']);ck('cohort_only_intended_identity_fields',{k for k in cohort if cohort[k]!=oldco.get(k)}=={'version','source_revision','runtime_version','firmware_sha256','firmware_size'} and cohort['version']=='0.1.99' and cohort['runtime_version']=='0.2.28' and cohort['source_revision']==cr['product_source'] and cohort['firmware_sha256']==sha(cp['firmware.bin']) and cohort['firmware_size']==len(cp['firmware.bin']))
selected=[]
for kind in ('drivers','app_capabilities'):
 for row in boot[kind]:
  if 'image_source' not in row:continue
  manifest=json.loads(cs[row['manifest']]);path=row['image_source']['path'];raw=sd[path]
  if kind=='drivers':ck('provider_selected_fallback_'+manifest['id'],raw==cs[str(Path(row['manifest']).parent/manifest['file_name'])])
  else:ck('app_selected_manifest_'+manifest['id'],manifest==json.loads(sd[str(Path(path).parent/'manifest.json')]))
  selected.append(dict(role='driver' if kind=='drivers' else 'app',manifest=row['manifest'],path=path,sha256=sha(raw),size_bytes=len(raw),matches_internal_fallback=kind=='drivers'))
ck('selected_images',len(selected)==48 and selected==cr['selected_sd_images'] and [r['path'] for r in selected if r not in br['selected_sd_images']]==['Apps/hollow_trail/hollow_trail.elf'])
overlaypaths=set(br['sd_overlay']['files'])|{'Apps/hollow_trail/hollow_trail.elf','Apps/hollow_trail/manifest.json'}
with zipfile.ZipFile(C/cr['sd_overlay']['name']) as z:
 zipsd={k:z.read(k) for k in z.namelist()};ck('cumulative_zip',len(z.namelist())==len(zipsd)==6 and z.testzip() is None and zipsd=={k:sd[k] for k in overlaypaths} and sha((C/cr['sd_overlay']['name']).read_bytes())==cr['sd_overlay']['sha256'])
base96=tree(D/'SD');merged=dict(base96);merged.update(zipsd)
ck('delivered_096_plus_cumulative_zip_equals_099_SD',merged==sd)
ck('no_new_keyboard',not any('keyboard' in p.lower() for p in overlaypaths) and cs['ui-scene/driver.elf']==bs['ui-scene/driver.elf'])
ck('native_candidate_lock',sha((N/'candidate.json').read_bytes())==lock['native_candidate_sha256']==cr['native_candidate_sha256'] and (N/'candidate.json').read_bytes()==(C/'receipts/native-candidate.json').read_bytes())
os.environ['X4_XTENSA_OBJDUMP']='/workspace/scratch/c744abbbbd60/watch-build-tools/platformio-core/packages/toolchain-xtensa-esp32s3/bin/xtensa-esp32s3-elf-objdump'
from build_test_bundle import validate_native_composition
native=validate_native_composition(N,read(N/'candidate.json'),R,native_source_root=Path('/workspace/shared/x4-obd-098-final-source'),expected_runtime={k:lock['runtime'][k] for k in ('repository','commit','version')})
ck('native_custody_compiled_startup_options',native==cr['native_composition'] and native['build_options']==br['native_composition']['build_options']==lock['native_build_options'])
ck('native_ELF_firmware_identity',(N/'firmware.bin').read_bytes()==cp['firmware.bin'] and sha((N/'firmware.elf').read_bytes())==cr['firmware_elf_sha256'])
rbase=br['runtime_commit'];diff=git(R,'diff','--name-only',rbase,lock['runtime']['commit']).splitlines();prod=[p for p in diff if p.startswith(('src/','sdk/','lib/'))]
ck('runtime_forward_port_only_TLS_no_ABI',prod==['src/main.cpp','src/ports/esp32s3/NativeHttp.h','src/ports/esp32s3/NativeTlsMemory.h'] and git(R,'rev-parse','HEAD^')==rbase,prod)
ck('hardware_limits_disclosed',all(cr[k] is False for k in ('hardware_tested','physical_daily_paper_tested','physical_hollow_trail_tested','physical_adapter_verified')))
result={'schema':'x4.memory-product-preservation-audit','schema_version':1,'status':'pass','sources':sources,'concurrent_product_worktree_changes':git(P,'status','--porcelain').splitlines(),'audit_script_sha256':sha(Path(__file__).read_bytes()),'candidate_full_sha256':sha(cb),'baseline_full_sha256':sha(bb),'recipe_sha256':cr['recipe_sha256'],'lock_sha256':cr['qualification_lock_sha256'],'candidate_receipt_sha256':sha((C/'receipts/memory-composition.json').read_bytes()),'checks':checks,'lifecycle_096':lifecycle,'runtime_source_changes':diff,'findings':[],'limits':['Read-only artifact/source/host audit; no device access, firmware flash or real TLS handshake.','Recipe replay reproduces preflight source identity; final published product revision requires recomposition and a fresh audit.','The cumulative overlay presumes the existing delivered .96 SD baseline, including its lifecycle manifests.']}
(E/'audit-memory-product-preservation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'status':'pass','checks':len(checks),'sha256':sha(cb),'source':sources['product']['commit'],'artifact':str(E/'audit-memory-product-preservation.json')}))
