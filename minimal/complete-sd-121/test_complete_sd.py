#!/usr/bin/env python3
"""Negative packaging cases and no-user-data merge regression checks."""
from pathlib import Path
import argparse,copy,importlib.util,io,json,tempfile,unittest,zipfile
import build_complete_sd as package

class Tests(unittest.TestCase):
    def test_complete_closure(self):
        files,rows,closure=package.select_files(STORE,INPUTS,LOCK)
        self.assertEqual(len(files),77);self.assertEqual(len(closure),49)
        self.assertEqual(set(closure),{r['path'] for r in rows if r['kind'] in ('application','driver')})
    def test_reproducible(self):
        files,_,_=package.select_files(STORE,INPUTS,LOCK)
        one=package.deterministic_zip(files);two=package.deterministic_zip(dict(reversed(list(files.items()))))
        self.assertEqual(one,two);self.assertEqual(package.sha(one),LOCK['expected_output']['sha256'])
    def test_exact_manifests(self):
        files,_,_=package.select_files(STORE,INPUTS,LOCK)
        for entry in json.loads(STORE['boot.json'])['app_capabilities']:
            if 'image_source' in entry:
                p=str(Path(entry['image_source']['path']).parent/'manifest.json')
                self.assertEqual(files[p],STORE[entry['manifest']])
    def test_no_user_data_and_merge(self):
        files,_,_=package.select_files(STORE,INPUTS,LOCK)
        old={'Books/personal.epub':b'book','ROMs/game.gb':b'rom','Settings/current.json':b'custom','AppData/save.bin':b'save','Apps/extra/extra.elf':b'extra'}
        merged=dict(old);merged.update(files)
        for k,v in old.items():self.assertEqual(merged[k],v)
        self.assertTrue(all(p.startswith(('Apps/','Drivers/','fonts/')) for p in files))
    def test_path_escape(self):
        for p in ('../x','/x','Apps/../x','Apps//x','Apps\\x',''):
            with self.assertRaises(ValueError):package.safe_path(p)
    def test_duplicate_zip(self):
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w') as z:z.writestr('Apps/x',b'x');z.writestr('Apps/x',b'y')
        with self.assertRaises(ValueError):package.read_zip(b.getvalue())
    def test_corrupt_input(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'bad';p.write_bytes(b'bad')
            with self.assertRaises(ValueError):package.checked_input(p,LOCK['inputs']['base87'])
    def test_missing_recovered_app(self):
        inputs=dict(INPUTS);z=package.read_zip(inputs['recovered103']);z.pop(next(iter(z)))
        inputs['recovered103']=package.deterministic_zip(z)
        with self.assertRaises((KeyError,AssertionError)):package.select_files(STORE,inputs,LOCK)
    def test_corrupt_driver(self):
        st=dict(STORE);st['i2c/driver.elf']=b'bad'
        with self.assertRaises(AssertionError):package.select_files(st,INPUTS,LOCK)
    def test_wrong_firmware(self):
        st=dict(STORE);c=json.loads(st['cohort.json']);c['version']='0.1.87';st['cohort.json']=json.dumps(c).encode()
        with self.assertRaises(AssertionError):package.select_files(st,INPUTS,LOCK)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for k in ('base87','overlay120','firmware121','runtime'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();LOCK=json.loads((package.ROOT/'inputs.lock.json').read_bytes())
    INPUTS={k:package.checked_input(getattr(a,k),LOCK['inputs'][k]) for k in ('base87','overlay120','firmware121')}
    INPUTS['recovered103']=b''.join(p.read_bytes() for p in sorted((package.ROOT/'recovered-103-apps.parts').glob('*.part')))
    assert package.sha(INPUTS['recovered103'])==LOCK['inputs']['recovered103']['sha256']
    spec=importlib.util.spec_from_file_location('spiffs_image',a.runtime/'scripts/spiffs_image.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    STORE=m.read_image(INPUTS['firmware121'][0x2f0000:0x800000],0x510000)
    unittest.main(argv=['test_complete_sd.py'])
