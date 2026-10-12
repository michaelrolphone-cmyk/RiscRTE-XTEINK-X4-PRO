#!/usr/bin/env python3
"""Qualify the full RF union and exact selected immutable client in both modes."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
from build_rf_policy import SELECTION
p=argparse.ArgumentParser(description=__doc__)
for n in ('runtime','tools','delivery','output'):p.add_argument('--'+n,type=lambda v:Path(v).resolve(),required=True)
a=p.parse_args();r=json.loads((a.delivery/'receipts/evening-composition.json').read_text())
assert r['schema']=='x4.waterfall-input-lifecycle-composition' and r['native_unchanged'] and r['old_waterfall_image_preserved']
assert len(r['store'])==106 and len(r['sd'])==SELECTION['baseline']['sd_file_count']+2 and r['changed_sd_paths']==[] and r['original_sd_files_preserved']==SELECTION['baseline']['sd_file_count']
assert len(r['added_sd_files'])==2 and r['boot_image_selection_changed']==['waterfall.json']
row=next(v for v in r['selected_sd_images'] if v['manifest']=='waterfall.json');assert row['sha256']==r['rf_build']['sha256'] and row['path']=='Apps/waterfall/image-'+row['sha256']+'/waterfall.elf'
assert hashlib.sha256((a.delivery/'SD'/row['path']).read_bytes()).hexdigest()==row['sha256']
command=[sys.executable,str(Path(__file__).with_name('qualify_evening_102.py'))]
for n in ('runtime','tools','delivery','output'):command+=['--'+n,str(getattr(a,n))]
subprocess.run(command,check=True)
results={name:json.loads((a.output/name/'result.json').read_text()) for name in ('normal','asan-ubsan')}
assert results['normal']['admission']==results['asan-ubsan']['admission']
for result in results.values():assert len(result['internal_images'])==43 and len(result['selected_sd_images'])==48
report=dict(schema='waterfall.lifecycle-complete-cohort-qualification.v1',source=r['rf_build']['sources']['utilities'],product_source=r['product_source'],normal_sanitized_admission_identical=True,internal_elfs=43,selected_sd_elfs=48,selected_waterfall=row,all_existing_sd_files_preserved=SELECTION['baseline']['sd_file_count'],immutable_files_added=2,exact_obd_hollow_catalogs_passed=True,native_unchanged=True,hardware_tested=False,target_instructions_executed=False)
(a.output/'waterfall-qualification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
