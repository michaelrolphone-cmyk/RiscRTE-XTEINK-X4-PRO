#!/usr/bin/env python3
"""Compose qualified HTTPS/Hollow fixes over the frozen OBD .98 product."""
import argparse,copy,hashlib,json,tempfile,zipfile
from pathlib import Path
from compose_desk_wake_093 import read_tree,clean_source
from compose_files_092 import require,sha,encoded,inventory,git,write_files,load_assembly_tools,BOOTFS,BANK_STATE
from compose_shared_settings_090 import audit_selected_images
from compose_fast_boot_094 import FIRMWARE,PRESERVED
from boot_order_spiffs import build as ordered_build
from build_test_bundle import validate_native_composition

ROOT=Path(__file__).resolve().parents[2]
BASE='922ac6b490fb6d3b22f642106bb1edd522c6ff4b'
BASE_SHA='4f7be9d66fd9461c89f8df7d48b07bdd4da53870b8276d6ddf08ce9da9fd1797'
BASE_RECEIPT='b6ea82b2e4acbb2f46d2310fe4ea447b1754c86722df9d8a95040a9e42263758'
VERSION='0.1.99'
IMAGE='X4-0.1.99-FULL-INITIAL-ERASES-DATA.bin'
ZIP='X4-0.1.99-OBD-Memory-SD-Overlay.zip'
CHANGED={'cohort.json','hollow_trail.json'}
SD_CHANGED={'Apps/hollow_trail/hollow_trail.elf','Apps/hollow_trail/manifest.json'}
LOCK=ROOT/'minimal/memory-099-inputs.json'


def baseline(folder):
 raw=(folder/'receipts/obd-composition.json').read_bytes()
 require(sha(raw)==BASE_RECEIPT,'Wrong frozen .98 composition receipt')
 receipt=json.loads(raw);full=(folder/'X4-0.1.98-OBD-FULL-INITIAL-ERASES-DATA.bin').read_bytes()
 old,sd,parts=read_tree(folder/'store'),read_tree(folder/'SD'),read_tree(folder/'components')
 require(len(full)==0x1000000 and sha(full)==BASE_SHA==receipt['full_image_sha256'],'Wrong frozen .98 image')
 require(receipt['product_source']==BASE and inventory(old)==receipt['store'] and inventory(sd)==receipt['sd'],'Wrong .98 source or inventories')
 require(len(old)==106 and len(sd)==85 and set(parts)==set(receipt['components']),'Wrong baseline count')
 for name,row in receipt['components'].items():
  data=parts[name];offset=row['offset']
  require(len(data)==row['bytes'] and sha(data)==row['sha256'] and full[offset:offset+len(data)]==data,'Wrong baseline component: '+name)
 return receipt,old,sd,parts,full


def payload(old,old_sd,hollow,firmware,revision,lock):
 require(sha(hollow['hollow_trail.elf'])==lock['hollow']['elf_sha256'] and sha(hollow['hollow_trail.json'])==lock['hollow']['manifest_sha256'],'Unqualified Hollow artifacts')
 manifest=json.loads(hollow['hollow_trail.json']);prior=json.loads(old['hollow_trail.json'])
 require(prior['version']=='1.2.1' and manifest==dict(prior,version='1.2.2'),'Hollow feature/authority change')
 require(old_sd['Apps/hollow_trail/manifest.json']==old['hollow_trail.json'],'Baseline internal/SD Hollow manifest differs')
 new=dict(old);sd=dict(old_sd)
 new['hollow_trail.json']=hollow['hollow_trail.json']
 sd.update({'Apps/hollow_trail/hollow_trail.elf':hollow['hollow_trail.elf'],'Apps/hollow_trail/manifest.json':hollow['hollow_trail.json']})
 cohort=json.loads(old['cohort.json'])
 require(cohort['version']=='0.1.98' and cohort['source_revision']==BASE and cohort['runtime_version']=='0.2.24','Wrong baseline cohort')
 cohort.update(version=VERSION,source_revision=revision,runtime_version=lock['runtime']['version'],firmware_sha256=sha(firmware),firmware_size=len(firmware))
 new['cohort.json']=encoded(cohort)
 require(set(new)==set(old) and {p for p in old if old[p]!=new[p]}==CHANGED,'Unrelated internal file change')
 require(set(sd)==set(old_sd) and {p for p in old_sd if old_sd[p]!=sd[p]}==SD_CHANGED,'Unrelated SD file change')
 require(new['boot.json']==old['boot.json'],'Boot authority changed')
 return new,sd


def verify_image(result,prior,old,new,firmware,decode,parse):
 require(len(result)==len(prior)==0x1000000,'Wrong complete image length')
 require(all(result[lo:hi]==prior[lo:hi] for lo,hi in PRESERVED),'Unrelated flash range changed')
 require(len(firmware)<=FIRMWARE[1]-FIRMWARE[0] and result[slice(*FIRMWARE)]==firmware+b'\xff'*(FIRMWARE[1]-FIRMWARE[0]-len(firmware)),'Wrong native partition or padding')
 require(decode(prior[slice(*BOOTFS)],0x510000)==old and decode(result[slice(*BOOTFS)],0x510000)==new,'Flash readback differs')
 require(set(new)==set(old) and {p for p in old if old[p]!=new[p]}==CHANGED,'Unrelated internal mutation')
 cohort=json.loads(new['cohort.json'])
 require(cohort['version']==VERSION and cohort['runtime_version']=='0.2.28' and cohort['firmware_sha256']==sha(firmware) and cohort['firmware_size']==len(firmware),'Cohort native identity differs')
 state=result[slice(*BANK_STATE)];pair=parse(state[:96],True)
 require(pair[2]==0 and pair[3]==len(firmware) and pair[6]==hashlib.sha256(firmware).digest() and pair[7]==hashlib.sha256(result[slice(*BOOTFS)]).digest() and state[96:]==b'\xff'*(8192-96),'Bank authentication differs')


def compose(a):
 require(not a.output.exists(),'Output must be new');clean_source(ROOT,a.product_revision,'Product')
 require(git(ROOT,'merge-base',BASE,a.product_revision)==BASE,'Product must descend from frozen .98')
 lock_raw=LOCK.read_bytes();lock=json.loads(lock_raw)
 require(lock['product_version']==VERSION,'Wrong component lock')
 for name in ('runtime','utilities','system'):
  root=getattr(a,name+'_source');clean_source(root,lock[name]['commit'],name)
  require(git(root,'rev-parse','HEAD^{tree}')==lock[name]['tree'],'Wrong source tree: '+name)
 base,old,old_sd,parts,prior=baseline(a.baseline)
 candidate_raw=(a.native/'candidate.json').read_bytes();candidate=json.loads(candidate_raw)
 require(sha(candidate_raw)==lock['native_candidate_sha256'],'Wrong qualified native candidate')
 native=validate_native_composition(a.native,candidate,a.runtime_source,native_source_root=a.native_product_source,expected_runtime={k:lock['runtime'][k] for k in ('repository','commit','version')})
 require(native['build_options']==base['native_composition']['build_options'],'Native features changed')
 for n in ('bootloader.bin','partitions.bin','appdata.bin'):
  require((a.native/n).read_bytes()==parts[n],'Unrelated native component changed: '+n)
 firmware=(a.native/'firmware.bin').read_bytes();hollow=read_tree(a.hollow)
 build=json.loads(hollow['build.json'])
 require(build['repository_commit']==lock['utilities']['commit'] and build['repository_tree']==lock['utilities']['tree'] and build['sha256']==lock['hollow']['elf_sha256'],'Wrong Hollow build source')
 require(sha(hollow['build.json'])==lock['hollow']['build_receipt_sha256'],'Wrong Hollow build closure')
 new,sd=payload(old,old_sd,hollow,firmware,a.product_revision,lock)
 pack,decode,bank,parse=load_assembly_tools(a.tools,a.runtime_source)
 bootfs,packing=ordered_build(new,pack)
 require(ordered_build(dict(reversed(list(new.items()))),pack)==(bootfs,packing),'Nondeterministic ordered packing')
 state=bank(firmware,bootfs,True);result=bytearray(prior)
 result[slice(*FIRMWARE)]=firmware+b'\xff'*(FIRMWARE[1]-FIRMWARE[0]-len(firmware))
 result[slice(*BOOTFS)]=bootfs;result[slice(*BANK_STATE)]=state
 verify_image(bytes(result),prior,old,new,firmware,decode,parse)
 with tempfile.TemporaryDirectory(prefix='x4-099-selected-') as tmp:
  root=Path(tmp);write_files(root/'store',new);write_files(root/'SD',sd)
  selected=audit_selected_images(json.loads(new['boot.json']),root/'store',root/'SD')
 require(len(selected)==48,'Wrong selected SD count')
 changed_selected=[r['path'] for r in selected if r not in base['selected_sd_images']]
 require(changed_selected==['Apps/hollow_trail/hollow_trail.elf'],'Unrelated selected image changed')
 # Include .98's four additions because the preceding delivered image was .96.
 overlay_paths=set(base['sd_overlay']['files'])|SD_CHANGED
 require(len(overlay_paths)==6,'Wrong cumulative .98/.99 SD overlay')
 overlay={p:sd[p] for p in overlay_paths}
 parts=dict(parts,**{'firmware.bin':firmware,'bootfs.bin':bootfs,'bank_state.bin':state})
 receipt=dict(schema='x4.memory-composition',schema_version=1,product='X4',product_version=VERSION,product_source=a.product_revision,product_tree=git(ROOT,'rev-parse','HEAD^{tree}'),product_base=BASE,
  baseline_full_image_sha256=BASE_SHA,baseline_receipt_sha256=BASE_RECEIPT,qualification_lock_sha256=sha(lock_raw),recipe_sha256=sha(Path(__file__).read_bytes()),
  runtime_commit=lock['runtime']['commit'],runtime_tree=lock['runtime']['tree'],runtime_version=lock['runtime']['version'],native_platform_commit=native['platform']['commit'],native_composition=native,native_candidate_sha256=sha(candidate_raw),native_rebuilt=True,native_unchanged=False,
  firmware_sha256=sha(firmware),firmware_elf_sha256=sha((a.native/'firmware.elf').read_bytes()),store=inventory(new),sd=inventory(sd),selected_sd_images=selected,
  changed_store_paths=sorted(CHANGED),changed_sd_paths=sorted(SD_CHANGED),added_store_paths=[],added_sd_files=[],original_sd_files_preserved=len(old_sd)-len(SD_CHANGED),
  providers=33,apps=27,boot_authority_unchanged=True,installation_envelope_unchanged=True,home_0_4_13_unchanged=True,files_1_5_31_unchanged=True,obd_0_2_1_unchanged=True,shared_settings_enabled=False,
  sd_lifecycle=base['sd_lifecycle'],sd_baseline_requires_delivered_096_overlay=True,home_client=base['home_client'],files_client=base['files_client'],obd_build=base['obd_build'],scene_build=base['scene_build'],serial_build=base['serial_build'],hollow_build=build,component_sources=lock,
  components={n:dict(bytes=len(v),sha256=sha(v),offset=base['components'][n]['offset']) for n,v in parts.items()},packing_sha256=sha(encoded(packing)),preserved_flash_ranges=[list(x) for x in PRESERVED],full_image_bytes=len(result),full_image_sha256=sha(result),independent_full_image_verified=True,
  sd_overlay_required=True,sd_deliverable_created=True,full_initial_image_erases_internal_data=True,hardware_tested=False,physical_daily_paper_tested=False,physical_hollow_trail_tested=False,physical_adapter_verified=False)
 a.output.mkdir(parents=True);write_files(a.output/'store',new);write_files(a.output/'SD',sd);write_files(a.output/'components',parts);(a.output/IMAGE).write_bytes(result)
 with zipfile.ZipFile(a.output/ZIP,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p,data in sorted(overlay.items()):
   entry=zipfile.ZipInfo(p,(2026,10,12,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;entry.external_attr=0o100644<<16;z.writestr(entry,data)
 with zipfile.ZipFile(a.output/ZIP) as z:require(z.testzip() is None and {n:z.read(n) for n in z.namelist()}==overlay,'SD overlay roundtrip failed')
 receipt['sd_overlay']=dict(name=ZIP,sha256=sha((a.output/ZIP).read_bytes()),files=inventory(overlay),cumulative_from_delivered_product='0.1.96')
 write_files(a.output/'receipts',{'memory-composition.json':encoded(receipt),'packing.json':encoded(packing),'qualification-lock.json':lock_raw,'native-candidate.json':candidate_raw})
 print(json.dumps(dict(version=VERSION,sha256=sha(result),sd_files=len(overlay),hardware_tested=False)))


if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('baseline','native','hollow','runtime-source','utilities-source','system-source','native-product-source','tools','output'):p.add_argument('--'+n,type=lambda v:Path(v).resolve(),required=True)
 p.add_argument('--product-revision',required=True);compose(p.parse_args())
