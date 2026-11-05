#!/usr/bin/env python3
"""Inspect exact retained rejected Xtensa ELFs; never rebuild or qualify firmware."""
import argparse,hashlib,json
from pathlib import Path
from elftools.elf.elffile import ELFFile
from elftools.dwarf.dwarf_expr import DWARFExprParser
EXPECTED={
 'successor':{'profile':'profiles/native-wifi.cmake','bytes':23954616,'sha256':'2343bfc3f692be3136faf3bca98d9ce08126eed2913842421de41f8ebb3c3452','map_sha256':'8ae07a344c7029e569e0f70cd0ae0823320e708899d9e55baa43e47e9aea1647'},
 'previous':{'profile':'profiles/native-provision-123.cmake','bytes':23928192,'sha256':'a26c49f3bceec4ddbef691b53fa1dd046dee402c3301766d87374a45a262908e','map_sha256':'e5e2cc8120baa7022f1baa34d327ba0013c51c08609b477c683873b6bc5c7221'}}
RUNTIME='4a04f85223d87d54fc6b9defb3ef4453b4fcc690'
PRODUCT='2e00e1fee1b5070861a628092e7662ea48a4344a'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def name(d):
 a=d.attributes.get('DW_AT_name')
 return a.value.decode('utf-8','replace') if a and isinstance(a.value,bytes) else str(a.value) if a else ''
def qualified(d):
 parts=[];p=d
 while p is not None:
  if p.tag in ('DW_TAG_namespace','DW_TAG_structure_type','DW_TAG_class_type','DW_TAG_enumeration_type'):
   parts.append(name(p) or '(anonymous)')
  p=p.get_parent()
 return '::'.join(reversed(parts))
def target(d):
 return d.get_DIE_from_attribute('DW_AT_type') if 'DW_AT_type' in d.attributes else None
def typename(d,depth=0):
 if d is None:return 'void'
 if depth>12:return '<recursive>'
 if name(d):return qualified(d) if d.tag in ('DW_TAG_structure_type','DW_TAG_class_type','DW_TAG_enumeration_type') else name(d)
 if d.tag=='DW_TAG_pointer_type':return typename(target(d),depth+1)+'*'
 if d.tag=='DW_TAG_array_type':return typename(target(d),depth+1)+'[]'
 return typename(target(d),depth+1) if target(d) is not None else d.tag
def size(d):
 if d is None:return None
 a=d.attributes.get('DW_AT_byte_size')
 if a:return int(a.value)
 if d.tag in ('DW_TAG_typedef','DW_TAG_const_type','DW_TAG_volatile_type'):return size(target(d))
 if d.tag=='DW_TAG_array_type':
  n=1
  for child in d.iter_children():
   if child.tag!='DW_TAG_subrange_type':continue
   count=child.attributes.get('DW_AT_count');upper=child.attributes.get('DW_AT_upper_bound')
   lower=child.attributes.get('DW_AT_lower_bound')
   if count:n*=int(count.value)
   elif upper:n*=int(upper.value)-(int(lower.value) if lower else 0)+1
   else:return None
  inner=size(target(d));return None if inner is None else n*inner
 return None
def offset(d,parser):
 a=d.attributes.get('DW_AT_data_member_location')
 if a is None:return None
 if isinstance(a.value,int):return a.value
 ops=parser.parse_expr(a.value)
 if len(ops)==1 and ops[0].op_name in ('DW_OP_plus_uconst','DW_OP_constu'):return int(ops[0].args[0])
 raise ValueError('Unsupported member location expression for '+name(d)+': '+repr(ops))
def describe(d,parser):
 members=[]
 for child in d.iter_children():
  if child.tag not in ('DW_TAG_member','DW_TAG_inheritance'):continue
  # Static members have no object offset.
  if 'DW_AT_data_member_location' not in child.attributes:continue
  item={'name':name(child) or '<base>','offset':offset(child,parser),'type':typename(target(child)),'bytes':size(target(child))}
  for attr in ('DW_AT_bit_size','DW_AT_data_bit_offset','DW_AT_bit_offset'):
   if attr in child.attributes:item[attr]=child.attributes[attr].value
  members.append(item)
 out={'name':qualified(d),'bytes':size(d),'members':members}
 if d.tag=='DW_TAG_enumeration_type':
  out['enumerators']={name(c):c.attributes['DW_AT_const_value'].value for c in d.iter_children() if c.tag=='DW_TAG_enumerator'}
 return out
def inspect(path):
 with path.open('rb') as f:
  elf=ELFFile(f)
  assert elf['e_machine']=='EM_XTENSA' and elf.elfclass==32 and elf.little_endian
  assert elf.has_dwarf_info(),'Required target DWARF is absent'
  dwarf=elf.get_dwarf_info();parser=DWARFExprParser(dwarf.structs)
  alltypes=[d for cu in dwarf.iter_CUs() for d in cu.iter_DIEs() if d.tag in ('DW_TAG_structure_type','DW_TAG_class_type','DW_TAG_enumeration_type') and size(d) is not None]
  required={
   'Backend':lambda d:name(d)=='Backend' and 'NativeSettingsBackend::' in qualified(d),
   'CheckedNvsFreshSources':lambda d:name(d)=='CheckedNvsFreshSources',
   'CheckedNvsLegacySources':lambda d:name(d)=='CheckedNvsLegacySources',
   'BackendState':lambda d:name(d)=='State' and 'NativeSettingsBackend::' in qualified(d),
   'DurabilityPolicy':lambda d:name(d)=='DurabilityPolicy' and 'NativeReplicaCore::' in qualified(d)}
  selected={};roots=[]
  for label,predicate in required.items():
   found=[d for d in alltypes if predicate(d)]
   assert found,'Required target type absent: '+label
   variants={json.dumps(describe(d,parser),sort_keys=True):d for d in found}
   assert len(variants)==1,'Inconsistent target layouts: '+label
   d=next(iter(variants.values()));roots.append(d);selected[label]=describe(d,parser)
  # Include directly embedded classes and their immediate embedded dependencies.
  seen=set();queue=[(d,0) for d in roots];nested={}
  while queue:
   d,depth=queue.pop(0);identity=(d.cu.cu_offset,d.offset)
   if identity in seen:continue
   seen.add(identity)
   if depth>0:nested[qualified(d)]=describe(d,parser)
   if depth>=2:continue
   for child in d.iter_children():
    if child.tag!='DW_TAG_member' or 'DW_AT_data_member_location' not in child.attributes:continue
    t=target(child)
    while t is not None and t.tag in ('DW_TAG_typedef','DW_TAG_const_type','DW_TAG_volatile_type','DW_TAG_array_type'):t=target(t)
    if t is not None and t.tag in ('DW_TAG_structure_type','DW_TAG_class_type') and size(t) is not None:queue.append((t,depth+1))
  section=elf.get_section_by_name('.dram0.bss');assert section
  return {'required_types':selected,'nested_types':nested,'bss':{'address':section['sh_addr'],'bytes':section['sh_size'],'end':section['sh_addr']+section['sh_size']}}
def main():
 p=argparse.ArgumentParser();p.add_argument('--artifact',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 a.output.mkdir(parents=True,exist_ok=True);root=a.artifact.resolve()
 receipts=list(root.rglob('rejected-build-measurement.json'));assert len(receipts)==2
 elfs=list(root.rglob('riscrte_native.elf'));assert len(elfs)==2
 maps=list(root.rglob('riscrte_native.map'));assert len(maps)==2
 report={'schema':1,'source_artifact_id':13413944176,'source_run_id':42026962629,'runtime_commit':RUNTIME,'product_commit':PRODUCT,'firmware_status':'rejected IQ overlap','admission':False,'roles':{}}
 for role,e in EXPECTED.items():
  matches=[(p,json.loads(p.read_text())) for p in receipts if json.loads(p.read_text()).get('selected_profile')==e['profile']]
  assert len(matches)==1;receipt_path,r=matches[0]
  assert r['status']=='build_rejected' and r['runtime_commit']==RUNTIME and r['product_commit']==PRODUCT
  files=[p for p in elfs if p.stat().st_size==e['bytes'] and digest(p)==e['sha256']];assert len(files)==1
  matching_maps=[p for p in maps if digest(p)==e['map_sha256']];assert len(matching_maps)==1
  assert r['artifacts']['riscrte_native.elf']['sha256']==e['sha256'] and r['artifacts']['riscrte_native.map']['sha256']==e['map_sha256']
  info=inspect(files[0]);assert info['bss']=={'address':0x3fcaa0d8,'bytes':24376,'end':0x3fcb0010}
  info.update(elf_sha256=e['sha256'],map_sha256=e['map_sha256'],receipt_sha256=digest(receipt_path))
  report['roles'][role]=info
  print(role+' exact rejected target layouts: '+json.dumps(info['required_types'],sort_keys=True),flush=True)
 (a.output/'target-member-layouts.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
 print('Verified rejected target member layouts; no build, placement or admission change')
if __name__=='__main__':main()
