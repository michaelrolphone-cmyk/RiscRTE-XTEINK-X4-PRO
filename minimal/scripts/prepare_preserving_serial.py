#!/usr/bin/env python3
"""Offline inactive-bank serial bootstrap plan. Never opens a port or flashes.

Require a current full-device readback and the exact admitted delivery baseline.
Never reuse a fixture-generated plan on hardware without fresh readback checks.
"""
import argparse,hashlib,json,struct,sys,zlib
from pathlib import Path

def sha(b):return hashlib.sha256(b).hexdigest()
def ota(entry):
 seq=struct.unpack_from('<I',entry)[0];state,crc=struct.unpack_from('<II',entry,24)
 if seq==0xffffffff or state in (3,4) or crc!=zlib.crc32(entry[:4],0xffffffff)&0xffffffff:return None
 if state not in (0,1,2):raise ValueError('unknown OTA state')
 return seq,state

def plan(snapshot,baseline,firmware,store,record):
 if sha(baseline) not in ('4764cfc487ab6ab88353a586c2bad1954e82fe0cb9951d93f51a36d60c918855','0902c78c9408a7138134e9e1ca8925000270270b86f3accf01fa6a8ab041ceef'):raise ValueError('baseline is not an admitted actual .81/.83 delivery')
 if len(snapshot)!=0x1000000 or len(baseline)!=len(snapshot):raise ValueError('16 MiB readback required')
 if snapshot[:0x9000]!=baseline[:0x9000]:raise ValueError('bootloader/partition table mismatch')
 entries=[ota(snapshot[0xff0000+i*4096:0xff0000+i*4096+32]) for i in range(2)]
 valid=[(v[0],i,v[1])for i,v in enumerate(entries)if v]
 if not valid:raise ValueError('no valid source OTA selection')
 seq,selected,state=max(valid)
 if state!=2 or seq>=0xfffffffe:raise ValueError('source must be confirmed and sequence incrementable')
 active=(seq-1)%2;target=1-active
 native=[0x10000,0x800000];stores=[0x2f0000,0xae0000]
 old=record(snapshot[0xff2000+active*4096:0xff2000+active*4096+96],True)
 base=record(baseline[0xff2000:0xff2060],True)
 if old[2]!=active or old[3:8]!=base[3:8]:raise ValueError('active source differs from admitted delivery')
 if hashlib.sha256(snapshot[native[active]:native[active]+old[3]]).digest()!=old[6] or hashlib.sha256(snapshot[stores[active]:stores[active]+0x510000]).digest()!=old[7]:raise ValueError('active pair readback integrity')
 if not 32<=len(firmware)<=0x260000 or len(store)!=0x510000:raise ValueError('candidate bounds')
 from paired_bank_images import record as make_record
 sector=make_record(target,firmware,store,True)+b'\xff'*(4096-96)
 sequence=struct.pack('<I',seq+1)
 # NEW is changed to PENDING_VERIFY by the existing rollback bootloader.
 selection=sequence+b'\xff'*20+struct.pack('<II',0,zlib.crc32(sequence,0xffffffff)&0xffffffff)+b'\xff'*(4096-32)
 rows=[('firmware.bin',native[target],firmware),('store.bin',stores[target],store),('bank-state.bin',0xff2000+target*4096,sector),('ota-selection-LAST.bin',0xff0000+(1-selected)*4096,selection)]
 protected=[(0,0x10000),(native[active],native[active]+0x260000),(stores[active],stores[active]+0x510000),(0x270000,0x2f0000),(0xff2000+active*4096,0xff3000+active*4096),(0xff0000+selected*4096,0xff1000+selected*4096)]
 for _,offset,data in rows:
  end=offset+(len(data)+4095)//4096*4096
  if any(offset<b and end>a for a,b in protected):raise ValueError('erase/write range intersects preserved data')
 return rows,dict(active_bank=active,target_bank=target,old_sequence=seq,new_sequence=seq+1,source_sha256=sha(snapshot),source_firmware_sha256=old[6].hex(),source_store_sha256=old[7].hex(),preserved_ranges=protected)

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ['runtime','snapshot','baseline','firmware','store','output']:p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--software-fixture',action='store_true',help='Mark this plan as a model fixture, never a hardware readback')
 a=p.parse_args();sys.path.insert(0,str(a.runtime.resolve()/'scripts'))
 from paired_bank_images import parse_record
 rows,receipt=plan(a.snapshot.read_bytes(),a.baseline.read_bytes(),a.firmware.read_bytes(),a.store.read_bytes(),parse_record)
 a.output.mkdir(parents=True,exist_ok=False)
 for name,_,data in rows:(a.output/name).write_bytes(data)
 receipt.update(software_fixture=a.software_fixture,hardware_tested=False,device_accessed=False,writes=[dict(file=n,offset=off,bytes=len(b),sha256=sha(b))for n,off,b in rows],protocol=['Obtain a fresh full readback using the existing esptool read_flash mechanism; validate this exact snapshot before preparing a plan.','Remain in ROM download mode: write firmware, store and bank-state using esptool write_flash with --after no_reset.','Read back each staged region and require exact candidate hashes before continuing. On any mismatch stop; do not select it.','Write the separate OTA selection sector LAST; never combine it with staging. Read it back exactly.','Reset only after verified selection. Existing rollback bootloader boots the NEW candidate, which must confirm health. Never erase_flash.'])
 (a.output/'plan.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps(receipt))
if __name__=='__main__':main()
