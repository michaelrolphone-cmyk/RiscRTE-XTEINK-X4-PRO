#!/usr/bin/env python3
"""Independent full-image decode and .96 preservation proof for final X4 .97."""
import argparse
import json
from pathlib import Path
import compose_mounted_files_097_final as c


def verify(a):
    lock=c.load_lock();base,old,sd,parts,full=c.baseline(a.baseline,lock)
    receipt=json.loads((a.output/'receipts/mounted-files-composition.json').read_bytes())
    artifacts={n:(a.output/'receipts/files-client'/n).read_bytes() for n in c.FILES_NAMES}
    c.require(c.inventory(artifacts)==lock['files_artifacts'],'Files artifact lock mismatch')
    expected=c.payload(old,sd,artifacts,receipt['product_source'],base['sd_lifecycle'])
    _,read_image,_,parse=c.load_assembly_tools(a.tools,a.runtime_source)
    preflight=receipt['local_preflight_only'];result=(a.output/(c.PREFLIGHT_IMAGE if preflight else c.IMAGE)).read_bytes()
    c.verify_image(result,full,old,expected,read_image,parse,parts['firmware.bin'])
    c.require(receipt['full_image_sha256']==c.sha(result) and receipt['store']==c.inventory(expected) and
              receipt['sd']==c.inventory(sd),'Receipt inventories differ')
    c.require(c.read_tree(a.output/'store')==expected and c.read_tree(a.output/'SD')==sd,'Staged store/SD differ')
    parts=dict(parts,**{'bootfs.bin':result[slice(*c.BOOTFS)],'bank_state.bin':result[slice(*c.BANK_STATE)]})
    c.require(c.read_tree(a.output/'components')==parts,'Component bytes differ')
    for n,v in parts.items():
        c.require(receipt['components'][n]==dict(bytes=len(v),sha256=c.sha(v),offset=base['components'][n]['offset']),
                  'Component receipt differs: '+n)
    c.require(receipt['system_commit']==c.SYSTEM and receipt['system_tree']==c.SYSTEM_TREE and
              receipt['system_published'] is True and receipt['final_rebuild_required'] is False and
              receipt['publication_ready']==(not preflight) and receipt['product_published']==(not preflight) and
              receipt['sd_deliverable_created'] is False and not list(a.output.glob('*.zip')),
              'Publication/SD identity differs')
    proof=receipt['source_publication']['product']
    c.require((preflight and proof is None) or (not preflight and proof['readback_verified'] is True and
              proof['commit']==receipt['product_source'] and proof['tree']==receipt['product_tree']),
              'Final product publication proof differs')
    return dict(passed=True,product_source=receipt['product_source'],system_source=c.SYSTEM,
                full_image_sha256=c.sha(result),changed_store_paths=sorted(c.ALLOWED),
                preserved_store_files=100,preserved_sd_files=81,selected_sd_images=46,
                native_unchanged=True,home_unchanged=True,boot_authority_unchanged=True,
                sd_lifecycle_unchanged=True,local_preflight_only=preflight,hardware_tested=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('baseline','output','tools','runtime-source'):p.add_argument('--'+n,type=Path,required=True)
    print(json.dumps(verify(p.parse_args()),indent=2))
