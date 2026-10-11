#!/usr/bin/env python3
"""Offline source-backed test bundle; never accesses devices or credentials."""
import argparse,hashlib,io,json,pathlib,shutil,struct,subprocess,sys,zipfile,zlib,re
p=argparse.ArgumentParser()
for n in ('runtime','tools','native','store','initial-image','output'):p.add_argument('--'+n,type=pathlib.Path,required=True)
p.add_argument('--target',choices=['x4','watch'],required=True);p.add_argument('--sd',type=pathlib.Path);p.add_argument('--product-source',required=True);p.add_argument('--x4-source',type=pathlib.Path)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
sys.path[:0]=[str(a.runtime.resolve()/'scripts'),str(a.tools.resolve()/'scripts')]
from paired_candidate import partitions,APP_DATA_EXPECTED,native_proof,policy_rows_proof
from paired_bank_images import initial_otadata,initial_bank_state,parse_record
from radio_iq_proof import prove as iq_proof
from release_assets import esp_image
from current_bootfs import build
from read_only_spiffs import read_image
from app_data_image import INITIAL_IMAGE_SHA256
from elftools.elf.elffile import ELFFile
sha=lambda b:hashlib.sha256(b).hexdigest()
def write(name,data):
 f=a.output/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(data)
def record(name,obj):write(name,(json.dumps(obj,indent=2,sort_keys=True)+'\n').encode())
native={n:(a.native/n).read_bytes() for n in ('firmware.bin','firmware.elf','bootloader.bin','partitions.bin')}
for n in ('firmware.bin','bootloader.bin'):esp_image(native[n]);assert native[n][3]>>4==4
parts=partitions(native['partitions.bin'],APP_DATA_EXPECTED)
proof=native_proof(native['firmware.elf']);proof['iq']=iq_proof(native['firmware.elf']);proof['policy']=policy_rows_proof(native,24,24)
revision=subprocess.check_output(['git','-C',str(a.runtime),'rev-parse','HEAD'],text=True).strip()
for b in (native['firmware.elf'],native['firmware.bin']):assert ('RTE_SOURCE='+revision).encode()+b'\0' in b and b'RISC_PAIRED_STORE_ABI:2\0' in b
versions=set(re.findall(rb'RISC_RUNTIME_VERSION:(\d+\.\d+\.\d+)\x00',native['firmware.bin']));assert len(versions)==1
version=versions.pop().decode()
if a.target=='x4':
 sys.path.insert(0,str(a.x4_source.resolve()/'minimal/scripts'));import prepare_native_runtime as x4
 composition=json.loads((a.native.parents[2]/'x4-native-composition.json').read_text())
 proof['x4_startup']=x4.startup_proof(native['firmware.elf'],composition)
 proof['x4_options']=x4.runtime_options_proof(native,composition)
 x4.verify_source_custody(a.runtime,composition,a.x4_source)
 record('receipts/x4-native-composition.json',composition)
store={str(f.relative_to(a.store)):f.read_bytes() for f in a.store.rglob('*') if f.is_file()}
old_cohort=json.loads(store['cohort.json']);cohort=dict(old_cohort,firmware_sha256=sha(native['firmware.bin']),firmware_size=len(native['firmware.bin']),runtime_version=version,source_revision=a.product_source)
if a.target=='watch':cohort['version']='1.1.1'
store['cohort.json']=(json.dumps(cohort,sort_keys=True,indent=2)+'\n').encode()
image,packing=build(store)
for n,b in store.items():write('store/'+n,b)
record('receipts/cohort-transition.json',dict(before=old_cohort,after=cohort,scope='Development shared Files test composition; version label is not a release identity. Exact source and hashes identify this bundle.'))
appdata=a.initial_image.read_bytes();assert len(appdata)==0x80000 and sha(appdata)==INITIAL_IMAGE_SHA256
components={**{k:v for k,v in native.items() if k.endswith('.bin')},'bootfs.bin':image,'appdata.bin':appdata,'otadata.bin':initial_otadata(),'bank_state.bin':initial_bank_state(native['firmware.bin'],image,True)}
offsets={'bootloader.bin':(0,0x8000),'partitions.bin':(0x8000,0x9000),'firmware.bin':(0x10000,0x270000),'appdata.bin':(0x270000,0x2f0000),'bootfs.bin':(0x2f0000,0x800000),'otadata.bin':(0xff0000,0xff2000),'bank_state.bin':(0xff2000,0xff4000)}
full=bytearray(b'\xff'*0x1000000);ranges=[]
for n,(offset,end) in offsets.items():
 b=components[n];assert offset+len(b)<=end
 full[offset:offset+len(b)]=b;write('components/'+n,b);ranges.append((offset,offset+len(b),n))
# Verify independently by parsing the final image and its metadata.
assert partitions(full[0x8000:0x8c00],APP_DATA_EXPECTED)==parts
assert read_image(bytes(full[0x2f0000:0x800000]),0x510000)==store
cursor=0
for start,end,n in sorted(ranges):
 assert all(x==255 for x in full[cursor:start]);assert full[start:end]==components[n];cursor=end
assert all(x==255 for x in full[cursor:]);assert all(x==255 for x in full[0x800000:0xff0000])
state=parse_record(bytes(full[0xff2000:0xff2060]),True)
assert state[6]==hashlib.sha256(native['firmware.bin']).digest() and state[7]==hashlib.sha256(image).digest()
ota=full[0xff0000:0xff0020];assert struct.unpack_from('<I',ota)[0]==1 and struct.unpack_from('<I',ota,24)[0]==2 and struct.unpack_from('<I',ota,28)[0]==zlib.crc32(ota[:4],0xffffffff)&0xffffffff
write(a.target.upper()+'-Shared-Files-FULL-INITIAL-ERASES-DATA.bin',full)
for n in ('firmware.elf','firmware.map'):
 if (a.native/n).exists():write('debug/'+n,(a.native/n).read_bytes())
sdproof=[];boot=json.loads(store['boot.json'])
external=[r for r in boot['app_capabilities'] if 'image_source' in r]
if external:
 assert a.sd is not None;shutil.copytree(a.sd,a.output/'SD')
 for r in external:
  path=r['image_source']['path'];b=(a.output/'SD'/path).read_bytes();m=json.loads(store[r['manifest']]);sm=json.loads((a.output/'SD'/pathlib.Path(path).parent/'manifest.json').read_bytes());assert m==sm
  sdproof.append(dict(path=path,manifest=r['manifest'],sha256=sha(b),size=len(b),manifest_matches=True))
else:write('SD/README.txt',b'This complete Watch baseline has no SD provider or SD-resident applications. No SD contents are required. Files shares the explicit AppData test map.\n')
elf=ELFFile(io.BytesIO(native['firmware.elf']));syms={s.name:s for s in elf.get_section_by_name('.symtab').iter_symbols()}
sections={s.name:dict(bytes=s['sh_size'],address=s['sh_addr']) for s in elf.iter_sections() if s['sh_flags']&2 and s['sh_size']}
heap=syms['_heap_start']['st_value'];ir=syms['_iram_end']['st_value'];dram_end=0x3fc88000+0x54700
memory=dict(static_dram_bytes=proof['static_dram_bytes'],static_dram_sections=proof['static_dram_sections'],native_bin_bytes=len(native['firmware.bin']),native_slot_bytes=0x260000,native_slot_margin_bytes=0x260000-len(native['firmware.bin']),heap_start=heap,iq_bank_base=0x3fcb0000,iq_bank_bytes=65536,static_dram_gap_before_iq_bytes=0x3fcb0000-heap,iram_gap_before_iq_alias_bytes=0x403a0000-ir,linker_dram_region_remainder_excluding_iq_bytes=dram_end-heap-65536,nominal_psram_bytes=8*1024*1024,x4_diagnostic_psram_bytes=131072 if a.target=='x4' else 0,x4_early_internal_heap_bytes=8192 if a.target=='x4' else 0,boot_store_empty_blocks=packing['empty_blocks'],allocated_sections=sections,live_heap_and_largest_allocation_measured=False,scope='Linker gaps are address-space bounds, not free heap or contiguous allocation guarantees. PSRAM ledger excludes resident provider/app images, graphics, networking, allocator metadata and transient buffers. Hardware allocation margins remain untested.')
record('receipts/native-proof.json',proof);record('receipts/memory.json',memory);record('receipts/packing.json',packing);record('receipts/sd-matching.json',sdproof)
record('receipts/composition.json',dict(target=a.target,runtime_commit=revision,product_source=a.product_source,firmware_sha256=sha(native['firmware.bin']),full_image_sha256=sha(full),full_image_bytes=len(full),components={n:dict(offset=offsets[n][0],bytes=len(b),sha256=sha(b)) for n,b in components.items()},apps=len(boot['app_capabilities']),providers=len(boot['drivers']),store={n:sha(b) for n,b in store.items()},independent_full_image_verified=True,inactive_bank_erased=True,unfinished_installer_included=False,hardware_tested=False))
print(json.dumps({k:v for k,v in memory.items() if k!='allocated_sections'},indent=2))
