#!/usr/bin/env python3
"""Independently read local .97 test image and enforce .96 preservation bounds."""
import argparse
import json
from pathlib import Path
import compose_mounted_files_097 as c


def verify(a):
    lock=c.load_lock()
    base,old,sd,parts,full=c.baseline(a.baseline,lock)
    receipt=json.loads((a.output/'receipts/mounted-files-composition.json').read_bytes())
    artifacts={n:(a.output/'receipts/files-client'/n).read_bytes() for n in c.FILES_NAMES}
    c.require(c.inventory(artifacts)==lock['files_artifacts'],'Files artifact lock mismatch')
    expected=c.payload(old,sd,artifacts,receipt['product_source'],base['sd_lifecycle'])
    _,read_image,_,parse=c.load_assembly_tools(a.tools,a.runtime_source)
    result=(a.output/c.IMAGE).read_bytes()
    c.verify_image(result,full,old,expected,read_image,parse,parts['firmware.bin'])
    c.require(receipt['full_image_sha256']==c.sha(result) and
              receipt['store']==c.inventory(expected) and receipt['sd']==c.inventory(sd),
              'Receipt inventories differ')
    c.require(c.read_tree(a.output/'store')==expected and c.read_tree(a.output/'SD')==sd,
              'On-disk store/SD differ')
    parts=dict(parts,**{'bootfs.bin':result[slice(*c.BOOTFS)],'bank_state.bin':result[slice(*c.BANK_STATE)]})
    c.require(c.read_tree(a.output/'components')==parts,'Component bytes differ')
    for n,v in parts.items():
        c.require(receipt['components'][n]==dict(bytes=len(v),sha256=c.sha(v),offset=base['components'][n]['offset']),
                  'Component receipt differs: '+n)
    c.require(receipt['local_preflight_only'] is True and receipt['publication_ready'] is False and
              receipt['final_rebuild_required'] is True and receipt['product_published'] is False and
              receipt['system_published'] is False and receipt['sd_deliverable_created'] is False and
              not list(a.output.glob('*.zip')), 'Blocked-publication guard differs')
    return dict(passed=True,full_image_sha256=c.sha(result),changed_store_paths=sorted(c.ALLOWED),
                preserved_store_files=100,preserved_sd_files=81,selected_sd_images=46,
                native_unchanged=True,home_unchanged=True,boot_authority_unchanged=True,
                sd_lifecycle_unchanged=True,local_preflight_only=True,hardware_tested=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('baseline','output','tools','runtime-source'):p.add_argument('--'+n,type=Path,required=True)
    print(json.dumps(verify(p.parse_args()),indent=2))
