#!/usr/bin/env python3
"""Compose Reader/Files regression repairs over the exact delivered X4 .100."""
import argparse, copy, json, tempfile, zipfile
from pathlib import Path
from compose_desk_wake_093 import read_tree, clean_source
from compose_files_092 import require, sha, encoded, inventory, git, write_files, load_assembly_tools, BOOTFS, BANK_STATE, safe_name
from compose_keyboard_100 import verify_image
from compose_shared_settings_090 import audit_selected_images
from compose_mounted_files_097 import resolved_grants
from boot_order_spiffs import build as ordered_build
ROOT=Path(__file__).resolve().parents[2]
BASE='e8d10469f981a1f7ec6b1cf84e5da48f4b66dbc2'
BASE_SHA='fdc7f3eca69932cf32a1e0bd66ac46f92a00252d8d81e86668324970f10fa3f2'
BASE_RECEIPT='c3795ee40a92f65d298ef55c28ba3a45f426cf1f6c392260c0ff6bc661118b63'
VERSION='0.1.101'
IMAGE='X4-0.1.101-FULL-INITIAL-ERASES-DATA.bin'
ZIP='X4-0.1.101-Reader-Files-Changed-SD.zip'
CHANGED={'cohort.json','file_browser.json','file_browser.elf','ebook_reader.json'}
SD_CHANGED={'Apps/ebook-reader/ebook_reader.elf','Apps/ebook-reader/manifest.json'}
LOCK=ROOT/'minimal/reader-files-101-inputs.json'

def compose(a):
 require(not a.output.exists(),'Output must be new')
 lock=json.loads(LOCK.read_bytes())
 clean_source(ROOT,a.product_revision,'Product')
 require(git(ROOT,'merge-base',BASE,a.product_revision)==BASE,'Product must descend from .100')
 for name in ('runtime','system','productivity'):
  root=getattr(a,name+'_source');actual=git(root,'rev-parse','HEAD')
  require(actual in {lock[name+'_commit'],lock.get(name+'_published_commit')},'Wrong '+name+' source commit');clean_source(root,actual,name)
  require(git(root,'rev-parse','HEAD^{tree}')==lock[name+'_tree'],'Wrong '+name+' tree')
 raw=(a.baseline/'receipts/keyboard-composition.json').read_bytes()
 require(sha(raw)==BASE_RECEIPT,'Wrong .100 receipt');base=json.loads(raw)
 old,sd,parts=read_tree(a.baseline/'store'),read_tree(a.baseline/'SD'),read_tree(a.baseline/'components')
 previous=(a.baseline/'X4-0.1.100-FULL-INITIAL-ERASES-DATA.bin').read_bytes()
 require(sha(previous)==BASE_SHA==base['full_image_sha256'] and base['product_source']==BASE,'Wrong delivered image')
 require(inventory(old)==base['store'] and inventory(sd)==base['sd'] and len(old)==106 and len(sd)==87,'Wrong baseline inventories')
 require(set(parts)==set(base['components']),'Wrong baseline components')
 for n,row in base['components'].items():
  v=parts[n];require(sha(v)==row['sha256'] and len(v)==row['bytes'] and previous[row['offset']:row['offset']+len(v)]==v,'Wrong component '+n)
 files={n:(a.files/n).read_bytes() for n in ('file_browser.elf','file_browser.json','file_browser-build-record.json')}
 require(inventory(files)==lock['files_artifacts'],'Wrong Files build artifacts')
 record=json.loads(files['file_browser-build-record.json'])
 require(record['repository_commit']==lock['system_commit'] and not record['working_tree_dirty'] and record['sha256']==sha(files['file_browser.elf']) and record['size_bytes']==len(files['file_browser.elf']),'Files source custody mismatch')
 require(json.loads(files['file_browser.json'])==dict(json.loads(old['file_browser.json']),version=lock['files_version']),'Files authority changed')
 profile=json.loads((ROOT/'minimal/files-mounted-097-final-inputs.json').read_bytes())['profile_invariants']
 for k,v in profile.items():require(record[k]==v,'Files profile changed: '+k)
 require(len(record['source_sha256'])==312,'Incomplete Files sources')
 for n,h in record['source_sha256'].items():
  safe_name(n);require(sha((a.system_source/n).read_bytes())==h,'Files compiled source changed: '+n)
 rows=[r for r in json.loads(old['boot.json'])['app_capabilities'] if r['manifest']=='file_browser.json']
 keys=lambda grants:sorted((r['capability'],r['api'],r['instance_id']) for r in grants)
 require(len(rows)==1 and len(rows[0]['grants'])==16 and keys(resolved_grants(record['required_grants'],rows[0]['grants']))==keys(rows[0]['grants']),'Files grant authority changed')
 reader={n:(a.reader/n).read_bytes() for n in ('ebook_reader.elf','ebook_reader.json','build.json')}
 require(inventory(reader)==lock['reader_artifacts'],'Wrong Reader artifacts')
 rb=json.loads(reader['build.json']);rm=json.loads(reader['ebook_reader.json']);rm['runtime_lifecycle']='foreground';reader['ebook_reader.json']=encoded(rm)
 require(rb['sha256']==sha(reader['ebook_reader.elf']) and rb['bytes']==len(reader['ebook_reader.elf']) and rb['sources']==lock['reader_build_sources'] and not any(rb['tracked_source_dirty'].values()),'Reader source custody mismatch')
 require(rm==dict(json.loads(old['ebook_reader.json']),version='0.1.9') and json.loads(sd['Apps/ebook-reader/manifest.json'])==json.loads(old['ebook_reader.json']),'Reader authority changed')
 new=dict(old);old_sd=dict(sd)
 new['file_browser.elf']=files['file_browser.elf'];new['file_browser.json']=files['file_browser.json'];new['ebook_reader.json']=reader['ebook_reader.json']
 sd['Apps/ebook-reader/ebook_reader.elf']=reader['ebook_reader.elf'];sd['Apps/ebook-reader/manifest.json']=reader['ebook_reader.json']
 cohort=json.loads(old['cohort.json']);require(cohort['version']=='0.1.100' and cohort['source_revision']==BASE,'Wrong predecessor cohort')
 cohort.update(version=VERSION,source_revision=a.product_revision);new['cohort.json']=encoded(cohort)
 require(set(new)==set(old) and {n for n in old if old[n]!=new[n]}==CHANGED,'Unrelated store changes')
 require(set(sd)==set(old_sd) and {n for n in sd if sd[n]!=old_sd[n]}==SD_CHANGED,'Unrelated SD changes')
 pack,decode,bank,parse=load_assembly_tools(a.tools,a.runtime_source);image,packing=ordered_build(new,pack)
 previous_packing=json.loads((a.baseline/'receipts/packing.json').read_bytes())
 for k in ('ordered_paths','order_recipe_sha256','generator_sha256','config','metadata','file_count','image_bytes'):
  require(packing[k]==previous_packing[k],'Accepted startup packing changed: '+k)
 firmware=parts['firmware.bin'];state=bank(firmware,image,True);full=bytearray(previous);full[slice(*BOOTFS)]=image;full[slice(*BANK_STATE)]=state
 verify_image(bytes(full),previous,old,new,firmware,decode,parse)
 with tempfile.TemporaryDirectory(prefix='x4-101-selected-') as tmp:
  root=Path(tmp);write_files(root/'store',new);write_files(root/'SD',sd);selected=audit_selected_images(json.loads(new['boot.json']),root/'store',root/'SD')
 before={r['manifest']:r for r in base['selected_sd_images']};after={r['manifest']:r for r in selected}
 require(len(selected)==48 and set(before)==set(after) and {n for n in before if before[n]!=after[n]}=={'ebook_reader.json'},'Unrelated SD selection changed')
 overlay_paths=set(base['sd_overlay']['files'])|SD_CHANGED;require(len(overlay_paths)==9,'Wrong cumulative overlay')
 overlay={n:sd[n] for n in sorted(overlay_paths)}
 parts=dict(parts,**{'bootfs.bin':image,'bank_state.bin':state})
 receipt=copy.deepcopy(base)
 receipt.update(schema='x4.reader-files-composition',product_version=VERSION,product_source=a.product_revision,product_tree=git(ROOT,'rev-parse','HEAD^{tree}'),product_base=BASE,baseline_full_image_sha256=BASE_SHA,baseline_receipt_sha256=BASE_RECEIPT,recipe_sha256=sha(Path(__file__).read_bytes()),source_lock=lock,system_commit=lock['system_commit'],system_tree=lock['system_tree'],native_rebuilt=False,native_unchanged=True,store=inventory(new),sd=inventory(sd),selected_sd_images=selected,changed_store_paths=sorted(CHANGED),changed_sd_paths=sorted(SD_CHANGED),added_sd_files=[],original_sd_files_preserved=len(sd)-2,boot_authority_unchanged=True,installation_envelope_unchanged=True,shared_settings_enabled=False,files_build=record,reader_build=rb,components={n:dict(bytes=len(v),sha256=sha(v),offset=base['components'][n]['offset']) for n,v in parts.items()},packing_sha256=sha(encoded(packing)),full_image_bytes=len(full),full_image_sha256=sha(full),independent_full_image_verified=True,hardware_tested=False)
 receipt['component_sources']['product_version']=VERSION;receipt['component_sources']['baseline_product']=BASE;receipt['component_sources']['system'].update(commit=lock['system_commit'],tree=lock['system_tree'])
 receipt['component_sources']['reader']=dict(version='0.1.9',commit=lock['productivity_commit'],elf_sha256=sha(reader['ebook_reader.elf']))
 a.output.mkdir(parents=True);write_files(a.output/'store',new);write_files(a.output/'SD',sd);write_files(a.output/'components',parts);(a.output/IMAGE).write_bytes(full)
 with zipfile.ZipFile(a.output/ZIP,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for n,v in overlay.items():
   entry=zipfile.ZipInfo(n,(2026,10,12,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;entry.external_attr=0o100644<<16;z.writestr(entry,v)
 with zipfile.ZipFile(a.output/ZIP) as z:require(z.testzip() is None and {n:z.read(n) for n in z.namelist()}==overlay,'SD overlay readback failed')
 receipt['sd_overlay']=dict(name=ZIP,sha256=sha((a.output/ZIP).read_bytes()),files=inventory(overlay),cumulative_from_delivered_product='0.1.96')
 write_files(a.output/'receipts',{'reader-files-composition.json':encoded(receipt),'packing.json':encoded(packing),'reader-build.json':reader['build.json'],'files-build.json':files['file_browser-build-record.json']})
 require(read_tree(a.output/'store')==new and read_tree(a.output/'SD')==sd and (a.output/IMAGE).read_bytes()==full,'Output readback failed')
 print(json.dumps(dict(version=VERSION,sha256=sha(full),sd_files=len(overlay),native_unchanged=True,hardware_tested=False)))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('baseline','files','reader','runtime-source','system-source','productivity-source','tools','output'):p.add_argument('--'+n,type=lambda v:Path(v).resolve(),required=True)
 p.add_argument('--product-revision',required=True);compose(p.parse_args())
