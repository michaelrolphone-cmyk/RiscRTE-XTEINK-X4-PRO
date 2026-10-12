#!/usr/bin/env python3
"""Compose the qualified shared keyboard pair over frozen X4 .99, offline."""
import argparse,copy,hashlib,json,tempfile,zipfile
from pathlib import Path,PurePosixPath
from compose_desk_wake_093 import read_tree,clean_source
from compose_files_092 import require,sha,encoded,inventory,git,write_files,load_assembly_tools,BOOTFS,BANK_STATE,PRESERVED_FLASH
from compose_shared_settings_090 import audit_selected_images
from boot_order_spiffs import build as ordered_build

ROOT=Path(__file__).resolve().parents[2]
BASE='199e231d962c401c5d20617e2f5e4da07bffd780'
BASE_SHA='3d6aba3cf67285c469254e380084d7ccb079f4bb12a7f27341949e5f983f66b4'
BASE_RECEIPT='91262b2ccdc1809f81f1be61908808789ee28580ed65c2831221f6dbe985ab7e'
RUNTIME='1c1ed8661ea30d47e7e9707c41d492ce3a2b4d70'
SYSTEM='c2889adff2a06bcd6c6207f11fbd0795fbbd99fa'
SYSTEM_TREE='6046e7a65d0ea1f97f8821be65154199eb4012bf'
VERSION='0.1.100'
IMAGE='X4-0.1.100-FULL-INITIAL-ERASES-DATA.bin'
ZIP='X4-0.1.100-OBD-Memory-Keyboard-SD-Overlay.zip'
PROVIDERS={'scene':('ui-scene','scene-host','0.4.2'),'text':('ui-text','text-input-host','0.1.4')}
TARGETS={'scene':'717d91d591ba1f1b8f666211c889147c9d4441cddd6edd1c8c0d62c610ea23b8','text':'f7d3f99ebf20c52d8f35ff8edd6260c9c0371e624486e814ed727061d50a4fef'}
CHANGED={'boot.json','cohort.json','ui-scene/driver.elf','ui-scene/manifest.json','ui-text/driver.elf','ui-text/manifest.json'}

def baseline(folder):
 raw=(folder/'receipts/memory-composition.json').read_bytes();require(sha(raw)==BASE_RECEIPT,'Wrong frozen .99 receipt')
 receipt=json.loads(raw);full=(folder/'X4-0.1.99-FULL-INITIAL-ERASES-DATA.bin').read_bytes()
 old,sd,parts=read_tree(folder/'store'),read_tree(folder/'SD'),read_tree(folder/'components')
 require(len(full)==0x1000000 and sha(full)==BASE_SHA==receipt['full_image_sha256'],'Wrong frozen .99 image')
 require(receipt['product_source']==BASE and inventory(old)==receipt['store'] and inventory(sd)==receipt['sd'],'Wrong .99 source/inventory')
 require(len(old)==106 and len(sd)==85 and set(parts)==set(receipt['components']),'Wrong baseline count')
 for name,row in receipt['components'].items():
  data=parts[name];offset=row['offset'];require(len(data)==row['bytes'] and sha(data)==row['sha256'] and full[offset:offset+len(data)]==data,'Wrong component: '+name)
 return receipt,old,sd,parts,full

# The paired module custody validator below is carried forward from the preserved
# .91 corrective recipe. It checks every compiled source and SDK header hash.
def validate_module(directory, kind, old, system, runtime):
    folder, identity, version = PROVIDERS[kind]
    manifest_raw = (directory / 'manifest.json').read_bytes()
    manifest = json.loads(manifest_raw)
    previous = json.loads(old[folder + '/manifest.json'])
    require(manifest.get('id') == identity and manifest.get('version') == version,
            'Wrong provider identity/version: ' + kind)
    require({k: v for k, v in manifest.items() if k != 'version'} ==
            {k: v for k, v in previous.items() if k != 'version'},
            'Provider manifest authority changed: ' + kind)
    raw = (directory / 'driver.elf').read_bytes()
    build_raw = (directory / 'build.json').read_bytes()
    build = json.loads(build_raw)
    require(build['sha256'] == sha(raw) and build['size_bytes'] == len(raw) and
            build['id'] == identity and build['version'] == version and build['defines'] == [],
            'Provider build receipt mismatch: ' + kind)
    sources = build['source_sha256']
    require(sources, 'Missing provider source custody')
    normalized = {}
    for name, digest in sources.items():
        path = Path(name)
        if path.is_absolute():
            # A build path may move with the same committed checkout. Resolve only
            # the source-owned suffix, never read arbitrary recorded host paths.
            parts = path.parts
            require('Services' in parts, 'Unexpected provider source path')
            relative = Path(*parts[parts.index('Services'):])
        else:
            relative = path
        require('..' not in relative.parts and not relative.is_absolute(), 'Unsafe source path')
        require(sha((system / relative).read_bytes()) == digest, 'Provider source changed: ' + str(relative))
        normalized[str(relative)] = digest
    require(('Services/scene_host/host.c' if kind == 'scene' else 'Services/text_input/host.c') in normalized,
            'Missing provider translation unit')
    sdk = build['sdk_sha256']
    require('SceneKeyboardV1.h' in sdk, 'Missing shared keyboard ABI witness')
    for name, digest in sdk.items():
        require(Path(name).name == name, 'Unsafe SDK header name')
        candidates = [system / 'Services/text_input' / name,
                      system / 'Services/scene_profile' / name]
        candidates += [root / 'sdk' / d / name for root in (runtime, system) for d in ('app', 'driver', 'hardware')]
        candidates += [system / 'lib/PortableApps/include' / name]
        require(any(p.is_file() and sha(p.read_bytes()) == digest for p in candidates),
                'Unmatched exact-source SDK header: ' + name)
    return manifest_raw, raw, build_raw, normalized

def payload(old,old_sd,modules,revision):
 new,sd=dict(old),dict(old_sd);boot=json.loads(old['boot.json']);original=copy.deepcopy(boot);details=[]
 require('shared_settings' not in boot.get('installation',{}),'Unfinished shared settings must remain disabled')
 for kind in ('scene','text'):
  folder,identity,version=PROVIDERS[kind];manifest,raw,build,sources=modules[kind]
  require(sha(raw)==TARGETS[kind],'Wrong qualified keyboard ELF')
  new[folder+'/manifest.json']=manifest;new[folder+'/driver.elf']=raw
  row=next(r for r in boot['drivers'] if r['manifest']==folder+'/manifest.json');source=row['image_source']
  require(source['internal_fallback'] is True and source['volume_instance']==9,'Unexpected fallback authority')
  previous=source['path'];require(old_sd[previous]==old[folder+'/driver.elf'],'Baseline SD/fallback pair differs')
  path=str(PurePosixPath(previous).parent/('image-'+sha(raw)+'.elf'))
  require(path not in old_sd,'Immutable image collision');source['path']=path;sd[path]=raw
  details.append(dict(manifest=folder+'/manifest.json',version=version,previous_path=previous,path=path,sha256=sha(raw),size_bytes=len(raw),source_sha256=sources,build_receipt_sha256=sha(build)))
 check=copy.deepcopy(boot)
 for row in details:next(r for r in check['drivers'] if r['manifest']==row['manifest'])['image_source']['path']=row['previous_path']
 require(check==original,'Boot authority or non-keyboard selection changed')
 new['boot.json']=encoded(boot);cohort=json.loads(old['cohort.json'])
 require(cohort['version']=='0.1.99' and cohort['source_revision']==BASE and cohort['runtime_version']=='0.2.28','Wrong predecessor cohort')
 cohort.update(version=VERSION,source_revision=revision);new['cohort.json']=encoded(cohort)
 require(set(new)==set(old) and {n for n in old if old[n]!=new[n]}==CHANGED,'Unrelated store change')
 require(len(sd)==len(old_sd)+2 and all(sd[n]==v for n,v in old_sd.items()),'Existing SD bytes changed')
 return new,sd,details

def verify_image(full,previous,old,new,firmware,decode,parse):
 require(len(full)==len(previous)==0x1000000,'Wrong flash size')
 for start,end in PRESERVED_FLASH:require(full[start:end]==previous[start:end],'Unrelated native/flash change')
 require(decode(previous[slice(*BOOTFS)],0x510000)==old and decode(full[slice(*BOOTFS)],0x510000)==new,'Independent decode differs')
 state=full[slice(*BANK_STATE)];pair=parse(state[:96],True)
 require(pair[2]==0 and pair[3]==len(firmware) and pair[6]==hashlib.sha256(firmware).digest() and pair[7]==hashlib.sha256(full[slice(*BOOTFS)]).digest() and state[96:]==b'\xff'*(8192-96),'Wrong initial bank authentication')

def compose(a):
 require(not a.output.exists(),'Output must be new');clean_source(ROOT,a.product_revision,'Product')
 require(git(ROOT,'merge-base',BASE,a.product_revision)==BASE,'Product must descend from frozen .99')
 clean_source(a.system_source,SYSTEM,'System');clean_source(a.runtime_source,RUNTIME,'Runtime')
 require(git(a.system_source,'rev-parse','HEAD^{tree}')==SYSTEM_TREE,'Wrong System source tree')
 base,old,old_sd,parts,previous=baseline(a.baseline)
 modules={kind:validate_module(getattr(a,kind),kind,old,a.system_source,a.runtime_source) for kind in PROVIDERS}
 builds={k:json.loads(v[2]) for k,v in modules.items()}
 require(builds['scene']['sdk_sha256']['SceneKeyboardV1.h']==builds['text']['sdk_sha256']['SceneKeyboardV1.h'],'Keyboard ABI pair differs')
 new,sd,details=payload(old,old_sd,modules,a.product_revision)
 pack,decode,bank,parse=load_assembly_tools(a.tools,a.runtime_source);image,packing=ordered_build(new,pack)
 require(ordered_build(dict(reversed(list(new.items()))),pack)==(image,packing),'Nondeterministic boot-order packing')
 firmware=parts['firmware.bin'];state=bank(firmware,image,True);result=bytearray(previous)
 result[slice(*BOOTFS)]=image;result[slice(*BANK_STATE)]=state
 verify_image(bytes(result),previous,old,new,firmware,decode,parse)
 with tempfile.TemporaryDirectory(prefix='x4-keyboard-selection-') as tmp:
  root=Path(tmp);write_files(root/'store',new);write_files(root/'SD',sd);selected=audit_selected_images(json.loads(new['boot.json']),root/'store',root/'SD')
 require(len(selected)==48,'Incomplete selected SD graph')
 expected={r['manifest']:r for r in base['selected_sd_images']};actual={r['manifest']:r for r in selected}
 require(set(expected)==set(actual),'Selected SD graph changed')
 require({n for n in expected if expected[n]!=actual[n]}=={'ui-scene/manifest.json','ui-text/manifest.json'},'Unrelated SD selection changed')
 require(all(actual[n]['matches_internal_fallback'] for n in ('ui-scene/manifest.json','ui-text/manifest.json')),'Keyboard SD/internal pair mismatch')
 overlay_paths=set(base['sd_overlay']['files'])-{r['previous_path'] for r in details};overlay_paths.update(r['path'] for r in details)
 overlay={p:sd[p] for p in sorted(overlay_paths)};require(len(overlay)==7,'Wrong cumulative overlay')
 parts=dict(parts,**{'bootfs.bin':image,'bank_state.bin':state});receipt=copy.deepcopy(base)
 receipt.update(schema='x4.keyboard-composition',product_version=VERSION,product_source=a.product_revision,product_tree=git(ROOT,'rev-parse','HEAD^{tree}'),product_base=BASE,
  baseline_full_image_sha256=BASE_SHA,baseline_receipt_sha256=BASE_RECEIPT,recipe_sha256=sha(Path(__file__).read_bytes()),system_commit=SYSTEM,system_tree=SYSTEM_TREE,
  native_rebuilt=False,native_unchanged=True,store=inventory(new),sd=inventory(sd),selected_sd_images=selected,changed_store_paths=sorted(CHANGED),changed_sd_paths=[],added_sd_files=sorted(sd.keys()-old_sd.keys()),original_sd_files_preserved=len(old_sd),
  boot_authority_unchanged=True,installation_envelope_unchanged=True,shared_settings_enabled=False,corrected_providers=details,scene_build=builds['scene'],text_build=builds['text'],
  components={n:dict(bytes=len(v),sha256=sha(v),offset=base['components'][n]['offset']) for n,v in parts.items()},packing_sha256=sha(encoded(packing)),preserved_flash_ranges=[list(x) for x in PRESERVED_FLASH],
  full_image_bytes=len(result),full_image_sha256=sha(result),independent_full_image_verified=True,hardware_tested=False)
 receipt['baseline_qualification_lock_sha256']=receipt.pop('qualification_lock_sha256')
 receipt['component_sources']['product_version']=VERSION;receipt['component_sources']['baseline_product']=BASE
 receipt['component_sources']['system'].update(commit=SYSTEM,tree=SYSTEM_TREE)
 receipt['component_sources']['keyboard']={k:dict(id=PROVIDERS[k][1],version=PROVIDERS[k][2],elf_sha256=TARGETS[k]) for k in PROVIDERS}
 a.output.mkdir(parents=True);write_files(a.output/'store',new);write_files(a.output/'SD',sd);write_files(a.output/'components',parts);(a.output/IMAGE).write_bytes(result)
 with zipfile.ZipFile(a.output/ZIP,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p,data in sorted(overlay.items()):
   entry=zipfile.ZipInfo(p,(2026,10,12,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED;entry.external_attr=0o100644<<16;z.writestr(entry,data)
 with zipfile.ZipFile(a.output/ZIP) as z:require(z.testzip() is None and {n:z.read(n) for n in z.namelist()}==overlay,'Cumulative overlay readback failed')
 receipt['sd_overlay']=dict(name=ZIP,sha256=sha((a.output/ZIP).read_bytes()),files=inventory(overlay),cumulative_from_delivered_product='0.1.96')
 write_files(a.output/'receipts',{'keyboard-composition.json':encoded(receipt),'packing.json':encoded(packing),'scene-build.json':modules['scene'][2],'text-build.json':modules['text'][2]})
 print(json.dumps(dict(version=VERSION,sha256=sha(result),sd_files=len(overlay),native_unchanged=True,hardware_tested=False)))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('baseline','scene','text','runtime-source','system-source','tools','output'):p.add_argument('--'+n,type=lambda v:Path(v).resolve(),required=True)
 p.add_argument('--product-revision',required=True);compose(p.parse_args())
