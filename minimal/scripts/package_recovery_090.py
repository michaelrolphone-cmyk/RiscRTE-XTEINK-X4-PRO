#!/usr/bin/env python3
"""Package already qualified offline artifacts. Does not flash or publish."""
import argparse,hashlib,json,pathlib,shutil,subprocess,zipfile
p=argparse.ArgumentParser()
for k in ('bundle','composition','admission','clients','proof','output','system-source','selected-admission','contexts-proof'):
 p.add_argument('--'+k,type=pathlib.Path,required=True)
a=p.parse_args()
assert not a.output.exists()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
r=json.loads((a.bundle/'receipts/composition.json').read_text())
c=json.loads((a.composition/'receipts/shared-settings-composition.json').read_text())
proof=json.loads((a.proof/'build/receipt.json').read_text())
assert r['independent_full_image_verified'] and r['apps']==26 and r['providers']==32
assert subprocess.check_output(['git','-C',str(a.system_source),'rev-parse','HEAD'],text=True).strip()==c['system_commit']
assert not subprocess.check_output(['git','-C',str(a.system_source),'status','--porcelain'],text=True).strip()
baseline=json.loads((pathlib.Path(__file__).resolve().parents[1]/'shared-settings-090-sd-baseline.json').read_text())
assert len(baseline['files'])==76
for path,digest in baseline['files'].items():assert sha(a.bundle/'SD'/path)==digest
packaged={str(f.relative_to(a.bundle/'SD')) for f in (a.bundle/'SD').rglob('*') if f.is_file()}
assert packaged==set(baseline['files'])|set(c['added_sd_files']) and len(packaged)==81
assert c['product_version']=='0.1.90' and c['shared_settings_enabled'] is False and c['shared_settings']==[]
assert len(c['selected_sd_images'])==46 and c['preserved_sd_files']==76
assert all(x['passed'] for x in proof['cases']) and len(proof['cases'])==12
ad=json.loads((a.admission/'evidence.json').read_text());assert ad['admission']['cohort_validated'] and ad['native_usb_phy']
assert ad['native']['firmware_sha256']==r['firmware_sha256']
selected=json.loads(a.selected_admission.read_text())
assert selected['runtime_commit']==r['runtime_commit'] and len(selected['selected_images'])==46
assert selected['native_firmware_sha256']==r['firmware_sha256']
assert ad['selected_sd_admission_sha256']==sha(a.selected_admission)
expected={(x['manifest'],x['path'],x['sha256']) for x in c['selected_sd_images']}
actual={(x['manifest'],x['path'],x['sha256']) for x in selected['selected_images']}
assert expected==actual and all(x['strict_admission_passed'] for x in selected['selected_images'])
for row in selected['selected_images']:
 assert sha(a.bundle/'SD'/row['path'])==row['sha256']
 if row['role']=='driver':assert row['matches_internal_fallback']
for path,digest in r['store'].items():assert sha(a.bundle/'store'/path)==digest
for path,entry in r['components'].items():assert sha(a.bundle/'components'/path)==entry['sha256']
assert 'shared_settings' not in json.loads((a.bundle/'store/boot.json').read_text())['installation']
clients=json.loads((a.clients/'client-builds.json').read_text())
assert clients['sources']['system']==c['system_commit'] and clients['sources']['runtime']==r['runtime_commit']
assert clients['sources']['utilities']==c['utilities_commit']
assert clients['product_source']==r['product_source']
contexts=json.loads((a.contexts_proof/'qualification.json').read_text())
equivalence=json.loads((a.contexts_proof/'x4-service-equivalence.json').read_text())
assert contexts['published_commit']==c['utilities_commit'] and contexts['client_version']=='0.4.2'
assert equivalence['allocated_sections_identical'] and equivalence['manifest_semantically_identical']
assert sha(a.clients/'contexts/contexts.elf')==contexts['x4_target']['elf_sha256']
# Older proof source labels remain explicit. Never relabel proof as a new build.
for name in ('build','build-sanitized'):
 verified=json.loads((a.proof/name/'receipt.json').read_text())
 assert verified['runtime']==r['runtime_commit'] and len(verified['cases'])==12 and all(x['passed'] for x in verified['cases'])
 for path,digest in verified['proof_source_sha256'].items():assert sha(a.proof/path)==digest
 for row in verified['providers']:
  assert sha(a.bundle/'SD'/row['current_path'])==row['current_sha256']
a.output.mkdir(parents=True)
readme='''X4 0.1.90 recovery diagnostic

Hardware testing remains pending. This package was validated offline; no device was flashed.

FULL INITIAL IMAGE WARNING
The full image is written at offset 0 and erases internal settings, Wi-Fi profiles and app data. It is not a preserving update. Shared general/Wi-Fi settings are NOT SD-backed in this build. Full flashing still loses native-only saved networks and preferences. The Wi-Fi UI reports local save without claiming confirmed SD backup. Durable native fallback and SD reconciliation remain unfinished.

SD PACKAGE
Merge the SD folder from this .90 package into the card, preserving existing files and user data. Do not format or replace the whole card. All 76 packaged .89 files remain unchanged. Five files are added: immutable installed-app catalog, Wi-Fi and BLE setup images, plus Contexts 0.4.2 and its matching manifest in a new directory. Their selected paths are updated to prevent older SD providers from shadowing qualified internal providers. The .89 SD package alone is not the complete qualified .90 set; install the .90 overlay too.

SCOPE
Complete 26-app/32-provider composition retained, including Reader, Daily Paper and the existing SD apps. Home retained wake remains 512 bytes native / 408 bytes snapshot. Staged GPIO1 startup, USB PHY ownership and private-AP support are preserved. Files keeps 16 grants by substituting the unused volume-only AppData-export grant with BLE HCI16 and removing its unused export map. The matched common Runtime/System sources contain crown, entropy bootstrap and Quick Controls corrections. Contexts 0.4.2 preserves the delivered learning completion and adds crown cleanup; its RF-only service remains unchanged.

VERIFICATION LIMITS
Offline checks cover complete full-image decoding and partitions, source custody, target ELF/import admission, selected SD inventory, real Runtime selected-byte loading/fallback, and policy negatives. Final Xtensa provider execution, wake/current draw, live heap and real device behavior remain untested.

PRIVACY
No real credentials or live user-card data were read or included. /RTECFG is excluded from Files, WebDAV and peer operations. Experimental recovery records are plaintext; physical card access and raw USB block export can expose them. These guards are not encryption.
'''
(a.output/'README.txt').write_text(readme)
sources={'version':'0.1.90','runtime_commit':r['runtime_commit'],'native_platform_commit':json.loads((a.bundle/'receipts/x4-native-composition.json').read_text())['platform']['commit'],'product_recipe_commit':r['product_source'],'system_commit':c['system_commit'],'client_sources':json.loads((a.clients/'client-builds.json').read_text())['sources'],'shared_settings_enabled':False,'hardware_tested':False,'full_image_sha256':r['full_image_sha256'],'firmware_sha256':r['firmware_sha256']}
(a.output/'SOURCES.json').write_text(json.dumps(sources,indent=2)+'\n')
def pack(name,items):
 dest=a.output/name
 with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for path,arc in items:
   info=zipfile.ZipInfo(arc,(2026,10,11,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16;z.writestr(info,path.read_bytes())
 return dest
common=[(a.output/'README.txt','README.txt'),(a.output/'SOURCES.json','SOURCES.json')]
full=a.bundle/'X4-Shared-Files-FULL-INITIAL-ERASES-DATA.bin';assert sha(full)==r['full_image_sha256'] and full.stat().st_size==16777216
pack('X4-0.1.90-Recovery-Full-Image.zip',common+[(full,'X4-0.1.90-FULL-INITIAL-ERASES-DATA.bin')])
pack('X4-0.1.90-SD-Overlay-Keep-Existing.zip',common+[(f,'SD/'+str(f.relative_to(a.bundle/'SD'))) for f in sorted((a.bundle/'SD').rglob('*')) if f.is_file()])
evidence=common[:]+[(pathlib.Path(__file__).resolve(),'scripts/package_recovery_090.py')]
for root,label in [(a.bundle/'components','components'),(a.bundle/'receipts','receipts/native'),(a.bundle/'store','store'),(a.composition/'receipts','receipts/composition')]:
 evidence += [(f,label+'/'+str(f.relative_to(root))) for f in sorted(root.rglob('*')) if f.is_file()]
evidence += [(a.admission/'evidence.json','receipts/admission.json'),(a.clients/'client-builds.json','receipts/client-builds.json'),(a.selected_admission,'receipts/selected-sd-admission.json')]
for name in ('qualification.json','x4-service-equivalence.json','hosted-ci.json'):
 evidence.append((a.contexts_proof/name,'receipts/contexts/'+name))
for f in a.proof.iterdir():
 if f.is_file() and f.suffix in ('.c','.cpp','.py','.sh','.md'):evidence.append((f,'selection-proof/'+f.name))
for name in ('build','build-sanitized'):
 receipt=a.proof/name/'receipt.json'
 assert receipt.is_file();evidence.append((receipt,'selection-proof/'+name+'-receipt.json'))
pack('X4-0.1.90-Evidence-and-Components.zip',evidence)
pack('X4-0.1.90-Native-Symbols.zip',common+[(f,'debug/'+f.name) for f in sorted((a.bundle/'debug').iterdir()) if f.is_file()]+[(a.bundle/'receipts/x4-native-composition.json','x4-native-composition.json')])
files={f.name:dict(bytes=f.stat().st_size,sha256=sha(f)) for f in a.output.glob('*.zip')}
(a.output/'SHA256.json').write_text(json.dumps(files,indent=2)+'\n')
for name in files:
 with zipfile.ZipFile(a.output/name) as z:assert z.testzip() is None
print(json.dumps(files,indent=2))
