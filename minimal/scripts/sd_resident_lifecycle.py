"""Correct only source-bound, already-selected SD foreground app metadata."""
import json
from pathlib import PurePosixPath
from compose_files_092 import require,sha,encoded
from package_resident_cohort import descriptor

EXPECTED={'ble_scanner','points_in_time','calculator','stopwatch','countdown','timecard',
          'ble_touchpad','ble_buttons','waterfall','contexts','lists','ebook-reader','daily-digest'}

def selected(store,sd):
    boot=json.loads(store['boot.json']);foreground=set(boot['resident_shell']['foreground'])
    legacy=set(boot['resident_shell']['legacy']);rows=[]
    for policy in boot['app_capabilities']:
        if not policy.get('catalog_authority'):continue
        manifest=policy['manifest'];m=json.loads(store[manifest]);source=policy['image_source']
        require(source['volume_instance']==9,'Wrong SD authority volume')
        image=source['path'];sd_manifest=str(PurePosixPath(image).with_name('manifest.json'))
        require(json.loads(sd[sd_manifest])==m,'SD/internal authority metadata differ')
        require(m['file_name']==PurePosixPath(image).name and m['entry']=='app_main','Changed application identity')
        if m['file_name'] in legacy:
            require(m.get('runtime_lifecycle','legacy')=='legacy','Legacy app was converted implicitly')
            continue
        require(m['file_name'] in foreground,'Unselected SD lifecycle')
        descriptor(sd[image],2,check_renderer=False)
        rows.append(dict(id=m['id'],version=m['version'],manifest=manifest,sd_manifest=sd_manifest,
                         image=image,elf_sha256=sha(sd[image]),descriptor_role=2))
    require(len(rows)==13 and {r['id'] for r in rows}==EXPECTED,'Foreground SD identity set differs')
    return rows

def repair(store,sd):
    rows=selected(store,sd);new=dict(store);new_sd=dict(sd)
    for row in rows:
        previous=json.loads(store[row['manifest']])
        require('runtime_lifecycle' not in previous,'Lifecycle already selected; wrong baseline')
        changed=dict(previous,runtime_lifecycle='foreground')
        raw=encoded(changed);new[row['manifest']]=new_sd[row['sd_manifest']]=raw
    validate(new,new_sd)
    return new,new_sd,rows

def validate(store,sd):
    rows=selected(store,sd)
    for row in rows:
        require(json.loads(sd[row['sd_manifest']]).get('runtime_lifecycle')=='foreground',
                'Resident ELF would be dynamically launched as legacy: '+row['id'])
    return rows
