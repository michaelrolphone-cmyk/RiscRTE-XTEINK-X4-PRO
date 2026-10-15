#!/usr/bin/env python3
"""Admit all 49 card ELFs with deployed Runtime policy and actual BIN exports."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,re,struct,subprocess,tempfile,zipfile
ROOT=Path(__file__).resolve().parent

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result

def imports(data):
    assert data[:7]==b'\x7fELF\x01\x01\x01'
    shoff=struct.unpack_from('<I',data,32)[0]
    entsize,count=struct.unpack_from('<HH',data,46)
    assert entsize==40 and shoff+entsize*count<=len(data)
    sections=[struct.unpack_from('<IIIIIIIIII',data,shoff+i*40) for i in range(count)]
    names=set()
    for s in sections:
        if s[1] not in (2,11):continue
        assert s[9]==16 and s[5]%16==0 and s[6]<count
        strings=sections[s[6]];table=data[strings[4]:strings[4]+strings[5]]
        assert s[4]+s[5]<=len(data)
        for off in range(s[4],s[4]+s[5],16):
            name,_,_,_,_,index=struct.unpack_from('<IIIBBH',data,off)
            if index==0 and name:
                assert name<len(table)
                names.add(table[name:table.index(b'\0',name)].decode('ascii'))
    return sorted(names)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runtime',type=Path,required=True)
    p.add_argument('--firmware',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();rt=a.runtime.resolve();out=a.output.resolve()
    lock=json.loads((ROOT/'inputs.lock.json').read_text());raw=a.firmware.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==lock['inputs']['firmware121']['sha256']
    decoder=module('spiffs_image',rt/'scripts/spiffs_image.py')
    store=decoder.read_image(raw[0x2f0000:0x800000],0x510000);meta=json.loads(store['cohort.json'])
    proof=json.loads((ROOT.parent/'recovery-107/fixtures/native-resolver-105.json').read_text())
    resolver=module('native_binary_exports',ROOT.parent/'scripts/native_binary_exports.py')
    lookup,native_proof=resolver.exports(raw[0x10000:0x10000+meta['firmware_size']],
                                       {t['table']:[row['name'] for row in t['rows']] for t in proof['tables']})
    manifest=json.loads((out/'X4-0.1.121-Complete-SD-Manifest.json').read_text())
    rows=[]
    with tempfile.TemporaryDirectory() as tmp:
        d=Path(tmp);fixture=ROOT.parent/'recovery-107/fixtures'
        header=(fixture/'cohort_elf_admission.h').read_text()
        header,n=re.subn(r'static const char\* exports\[\]=\{[^}]*\};',
                        'static const char* exports[]={'+','.join(json.dumps(name) for name in sorted(lookup))+'};',header)
        assert n==1
        (d/'cohort_elf_admission.h').write_text(header)
        (d/'strict.cpp').write_bytes((fixture/'strict.cpp').read_bytes())
        incs=[rt/n for n in ('src','sdk/app','sdk/driver','sdk/hardware','lib/ArduinoJson/src','test/drivers/stubs','lib/elf_loader/include','test/native_bank_stubs')]+[d,rt]
        common=['-I'+str(i) for i in incs]
        subprocess.run(['cc','-std=c11',*common,'-c',str(rt/'lib/elf_loader/src/esp_elf_validate.c'),'-o',str(d/'validate.o')],check=True)
        subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror','-Wno-missing-field-initializers','-Wno-misleading-indentation',*common,str(d/'strict.cpp'),str(d/'validate.o'),'-o',str(d/'strict')],check=True)
        with zipfile.ZipFile(out/manifest['package_file']) as z:
            assert set(z.namelist())=={row['path'] for row in manifest['files']}
            for row in manifest['files']:
                data=z.read(row['path']);assert hashlib.sha256(data).hexdigest()==row['sha256'] and len(data)==row['size_bytes']
                if row['kind'] not in ('application','driver'):continue
                symbols=imports(data);assert set(symbols)<=set(lookup),(row['path'],set(symbols)-set(lookup))
                path=d/'candidate.elf';path.write_bytes(data)
                subprocess.run([str(d/'strict'),'app' if row['kind']=='application' else 'driver',str(path),*symbols],check=True,stdout=subprocess.DEVNULL)
                rows.append(dict(path=row['path'],sha256=row['sha256'],role=row['kind'],imports=symbols,
                                 strict_admission=True,wrong_role_rejected=True,unsafe_operation_rejected=True,
                                 each_missing_import_rejected=True))
    assert len(rows)==49
    validation_path=out/'X4-0.1.121-Complete-SD-Validation.json';validation=json.loads(validation_path.read_text())
    validation.update(production_runtime_elf_admission=True,native_exports_read_from_exact_firmware=True,
                      runtime_source_revision=lock['runtime_source'],elf_admission=rows)
    validation_path.write_text(json.dumps(validation,indent=2)+'\n')
    sums=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in sorted(out.iterdir()) if p.is_file() and p.name!='SHA256SUMS-complete-sd.txt')
    (out/'SHA256SUMS-complete-sd.txt').write_text(sums)
    print('PASS: all 49 SD ELFs admitted with exact native exports; wrong-role, unsafe-operation and per-import negative cases pass.')

if __name__=='__main__':main()
