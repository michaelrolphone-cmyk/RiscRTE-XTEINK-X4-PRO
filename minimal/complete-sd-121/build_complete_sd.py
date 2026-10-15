#!/usr/bin/env python3
"""Assemble exactly the SD images selected by frozen X4 0.1.121 firmware.

This copies qualified bytes, never rebuilds firmware and never creates settings.
Only Apps, Drivers and fonts are installed. Source/validation sidecars stay outside
of the card archive. The deterministic archive uses ZIP_STORED deliberately.
"""
from pathlib import Path, PurePosixPath
import argparse, hashlib, importlib.util, io, json, re, sys, zipfile

ROOT = Path(__file__).resolve().parent
NAME = 'X4-0.1.121-Complete-SD-Keep-Existing.zip'
MANIFEST = 'X4-0.1.121-Complete-SD-Manifest.json'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def safe_path(path):
    p = PurePosixPath(path)
    if not path or p.is_absolute() or '\\' in path or '..' in p.parts or str(p) != path:
        raise ValueError('Unsafe archive member: ' + path)
    return path

def read_zip(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if len(z.namelist()) != len(set(z.namelist())):
            raise ValueError('Duplicate archive names')
        return {safe_path(i.filename): z.read(i) for i in z.infolist() if not i.is_dir()}

def checked_input(path, pin):
    data = path.read_bytes()
    if len(data) != pin['bytes'] or sha(data) != pin['sha256']:
        raise ValueError('Input digest/size mismatch: ' + path.name)
    return data

def select_files(store, inputs, lock):
    boot = json.loads(store['boot.json'])
    cohort = json.loads(store['cohort.json'])
    assert cohort['version'] == '0.1.121' and cohort['product'] == 'xteink-x4-pro'
    archive = {}; origins = {}; closure = []
    for key in ('base87', 'recovered103', 'overlay120'):
        for name, value in read_zip(inputs[key]).items():
            archive[name] = value; origins[name] = key
    selected = {}; rows = []
    for group in ('app_capabilities', 'drivers'):
        for entry in boot[group]:
            source = entry.get('image_source')
            if not source:
                continue
            assert source['volume_instance'] == 9
            path = safe_path(source['path']); manifest = json.loads(store[entry['manifest']])
            is_app = group == 'app_capabilities'
            if is_app:
                assert path.startswith('Apps/')
                pin = lock['apps'][manifest['id']]
                data = archive[path]
                assert len(data) == pin['size'] and sha(data) == pin['sha256'], path
                origin = origins[path]
                manifest_path = str(PurePosixPath(path).parent / 'manifest.json')
                # Exact firmware manifest bytes carry foreground lifecycle metadata.
                selected[manifest_path] = store[entry['manifest']]
                rows.append(dict(path=manifest_path, kind='application-manifest',
                                 source='firmware121:' + entry['manifest']))
            else:
                assert path.startswith('Drivers/')
                # All SD driver bytes must also match their exact internal fallback.
                internal = str(PurePosixPath(entry['manifest']).parent / manifest['file_name'])
                data = store[internal]
                origin = 'firmware121:' + internal
                if path in archive:
                    assert archive[path] == data, path
            identity = re.search(r'(?:^|/)image-([0-9a-f]{64})(?:/|\.elf$)', path)
            if identity:
                assert sha(data) == identity.group(1), path
            assert data[:4] == b'\x7fELF' and data[4:7] == b'\x01\x01\x01', path
            assert int.from_bytes(data[18:20], 'little') == 94, path  # Xtensa
            selected[path] = data
            rows.append(dict(path=path, kind='application' if is_app else 'driver', source=origin,
                             id=manifest['id'], version=manifest['version'],
                             boot_manifest=entry['manifest']))
            closure.append(path)
    # These are the complete font resources from the pinned complete .87 SD input.
    base = read_zip(inputs['base87'])
    resources = {name:data for name,data in base.items() if name.startswith('fonts/')}
    assert len(resources) == 10 and sum(name.endswith('.ttf') for name in resources) == 8
    for path, data in resources.items():
        selected[path] = data
        rows.append(dict(path=path, kind='font-resource', source='base87'))
    assert len(closure) == len(set(closure)) == 49
    assert sum(r['kind'] == 'application' for r in rows) == 18
    assert sum(r['kind'] == 'driver' for r in rows) == 31
    assert len(selected) == len(rows) == 77
    for row in rows:
        data = selected[row['path']]
        row.update(size_bytes=len(data), sha256=sha(data))
    return selected, sorted(rows, key=lambda r:r['path']), sorted(closure)

def deterministic_zip(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_STORED) as z:
        for name, data in sorted(files.items()):
            info=zipfile.ZipInfo(safe_path(name), (2026,10,15,0,0,0))
            info.compress_type=zipfile.ZIP_STORED; info.create_system=3
            info.external_attr=0o100644 << 16
            z.writestr(info,data)
    return buffer.getvalue()

def assemble(paths, runtime, output, source_revision):
    lock=json.loads((ROOT/'inputs.lock.json').read_bytes())
    inputs={key:checked_input(paths[key],pin) for key,pin in lock['inputs'].items() if key!='recovered103'}
    recovered=paths['recovered103']
    if recovered.exists():
        inputs['recovered103']=checked_input(recovered,lock['inputs']['recovered103'])
    else:
        part_dir=ROOT/'recovered-103-apps.parts'
        names=sorted(p.name for p in part_dir.iterdir())
        assert names==[f'{i:03}.part' for i in range(23)]
        inputs['recovered103']=b''.join((part_dir/n).read_bytes() for n in names)
        pin=lock['inputs']['recovered103']
        assert len(inputs['recovered103'])==pin['bytes'] and sha(inputs['recovered103'])==pin['sha256']
    spec=importlib.util.spec_from_file_location('spiffs_image',runtime/'scripts/spiffs_image.py')
    decoder=importlib.util.module_from_spec(spec);spec.loader.exec_module(decoder)
    fw=inputs['firmware121'];store=decoder.read_image(fw[0x2f0000:0x800000],0x510000)
    cohort=json.loads(store['cohort.json'])
    native=fw[0x10000:0x10000+cohort['firmware_size']]
    assert sha(native)==cohort['firmware_sha256']
    files,rows,closure=select_files(store,inputs,lock)
    packed=deterministic_zip(files)
    assert read_zip(packed)==files
    if 'expected_output' in lock:
        assert sha(packed)==lock['expected_output']['sha256']
        assert len(packed)==lock['expected_output']['bytes']
    output.mkdir(parents=True,exist_ok=True)
    (output/NAME).write_bytes(packed)
    manifest=dict(schema='riscrte.complete-sd-manifest',schema_version=1,product='xteink-x4-pro',
                  firmware_version='0.1.121',package_file=NAME,package_sha256=sha(packed),
                  package_size_bytes=len(packed),file_count=len(files),files=rows)
    (output/MANIFEST).write_text(json.dumps(manifest,indent=2)+'\n')
    provenance=dict(schema='riscrte.complete-sd-provenance',schema_version=1,
                    packaging_source_revision=source_revision,firmware_source_revision=lock['firmware_source'],
                    runtime_source_revision=lock['runtime_source'],inputs=lock['inputs'],
                    byte_changes='No application, driver or font binary was rebuilt or modified.',
                    manifest_source='Exact app manifest bytes from frozen .121 boot store; five .87 manifests gain already-deployed foreground lifecycle metadata.',
                    hardware_tested=False)
    (output/'X4-0.1.121-Complete-SD-Provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    validation=dict(schema='riscrte.complete-sd-validation',schema_version=1,
                    package_sha256=sha(packed),boot_sha256=sha(store['boot.json']),
                    firmware_sha256=sha(fw),native_sha256=sha(native),
                    complete_boot_sd_image_closure=True,sd_apps=18,sd_drivers=31,font_files=10,
                    app_manifests_match_firmware_exactly=True,all_content_addressed_images_match=True,
                    all_sd_driver_images_match_internal_fallbacks=True,all_files_sha256_verified=True,
                    zip_roundtrip=True,settings_or_user_data_files=0,hardware_tested=False,
                    boot_image_paths=closure)
    (output/'X4-0.1.121-Complete-SD-Validation.json').write_text(json.dumps(validation,indent=2)+'\n')
    for filename in ('COMPLETE-SD-INSTRUCTIONS.txt','COMPLETE-SD-CHANGES.txt','X4-0.1.121-Technical-Details.txt','RELEASE-NOTES.txt'):
        (output/filename).write_bytes((ROOT/filename).read_bytes())
    checks=''.join(sha(p.read_bytes())+'  '+p.name+'\n' for p in sorted(output.iterdir()) if p.is_file() and p.name!='SHA256SUMS-complete-sd.txt')
    (output/'SHA256SUMS-complete-sd.txt').write_text(checks)
    return manifest,validation

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('base87','overlay120','firmware121','runtime','output'):
        p.add_argument('--'+key,required=True,type=Path)
    p.add_argument('--source-revision',required=True)
    a=p.parse_args()
    assert re.fullmatch('[0-9a-f]{40}',a.source_revision)
    paths={key:getattr(a,key) for key in ('base87','overlay120','firmware121')}
    paths['recovered103']=ROOT/'recovered-103-apps.zip'
    manifest,validation=assemble(paths,a.runtime,a.output,a.source_revision)
    print(json.dumps({k:manifest[k] for k in ('package_file','package_sha256','package_size_bytes','file_count')},indent=2))

if __name__=='__main__':main()
