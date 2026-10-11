import hashlib,importlib.util,json,struct,sys,zlib
from pathlib import Path
import argparse
p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);a=p.parse_args()
import os
os.chdir(a.workspace)
sys.path[:0]=[str(a.workspace/'runtime/scripts'),str(Path(__file__).resolve().parents[1]/'scripts')]
from paired_bank_images import parse_record,record
from prepare_preserving_serial import plan,ota

def selected(b):
 rows=[(v[0],(v[0]-1)%2)for i in range(2)if (v:=ota(b[0xff0000+i*4096:0xff0000+i*4096+32]))]
 return max(rows)[1]
def entry(seq,state):
 s=struct.pack('<I',seq);return s+b'\xff'*20+struct.pack('<II',state,zlib.crc32(s,0xffffffff)&0xffffffff)+b'\xff'*(4096-32)
rows=[]
for version in ['081','083']:
 baseline=Path('build/deployment-baselines/'+version+'/full.bin').read_bytes();target=Path('build/increment-085-from-'+version+'-verified/components');fw=(target/'firmware.bin').read_bytes();store=(target/'bootfs.bin').read_bytes();old=parse_record(baseline[0xff2000:0xff2060],True)
 for active in [0,1]:
  snapshot=bytearray(baseline);snapshot[0x9000:0xf000]=bytes((i*17+3)%256 for i in range(0x6000));snapshot[0x270000:0x2f0000]=bytes((i*23+7)%256 for i in range(0x80000))
  if active:
   snapshot[0x800000:0x800000+old[3]]=baseline[0x10000:0x10000+old[3]];snapshot[0xae0000:0xff0000]=baseline[0x2f0000:0x800000];snapshot[0xff3000:0xff3060]=record(1,baseline[0x10000:0x10000+old[3]],baseline[0x2f0000:0x800000],True);snapshot[0xff1000:0xff2000]=entry(2,2)
  writes,receipt=plan(bytes(snapshot),baseline,fw,store,parse_record);assert(selected(snapshot)==active)
  staged=bytearray(snapshot);sectors=0
  for name,off,b in writes[:-1]:
   end=off+(len(b)+4095)//4096*4096
   for sector in range(off,end,4096):
    assert all(not(sector<stop and sector+4096>start)for start,stop in receipt['preserved_ranges']);sectors+=1
   staged[off:end]=b'\xff'*(end-off);staged[off:off+len(b)]=b
   assert(selected(staged)==active)
  for start,end in receipt['preserved_ranges']:assert staged[start:end]==snapshot[start:end]
  name,off,b=writes[-1]
  for cut in range(33):
   interrupted=bytearray(staged);interrupted[off:off+4096]=b'\xff'*4096;interrupted[off:off+cut]=b[:cut]
   assert selected(interrupted)==(1-active if cut==32 else active)
  complete=bytearray(staged);complete[off:off+4096]=b;assert selected(complete)==1-active
  for start,end in receipt['preserved_ranges']:assert complete[start:end]==snapshot[start:end]
  # Existing bootloader lifecycle: NEW -> PENDING_VERIFY -> ABORTED returns old pair.
  complete[off+24:off+28]=struct.pack('<I',1);assert selected(complete)==1-active
  complete[off+24:off+28]=struct.pack('<I',4);assert selected(complete)==active
  for name,offset in [('bootloader',0),('firmware',(0x10000,0x800000)[active]),('store',(0x2f0000,0xae0000)[active])]:
   bad=bytearray(snapshot);bad[offset]^=1
   try:plan(bytes(bad),baseline,fw,store,parse_record);raise AssertionError('accepted '+name)
   except ValueError:pass
  rows.append(dict(delivered=version,active_bank=active,staged_sector_boundaries=sectors,selection_byte_cuts=33,protected_bytes_unchanged=True,rollback_selection_model=True))
Path('build/increment-serial-qualification.json').write_text(json.dumps(dict(hardware_tested=False,scope='Offline range/integrity and existing OTA record selection model; no ROM transport or hardware execution',cases=rows),indent=2)+'\n')
print(json.dumps(rows,indent=2))
