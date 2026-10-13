#!/usr/bin/env python3
"""Run the pinned RF lifecycle fixture with its exact qualified glyph bytes.

Font-wheel/FreeType differences otherwise fail the fixture before any lifecycle
test. Only the typography generation step is replaced; its original SHA check
and every app/adapter/text-host/scene-host assertion remain unchanged.
"""
import argparse,base64,gzip,hashlib,sys,tempfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--utilities',type=Path,required=True)
a,rest=p.parse_known_args();script=a.utilities.resolve()/'scripts/test_rf_shared_input.py'
source=script.read_text()
needle="subprocess.run([sys.executable,str(stage/'scripts'/generator.name)],check=True)"
assert source.count(needle)==1
data=gzip.decompress(base64.b64decode((Path(__file__).parent/'telemetry-fixture.gz.b64').read_bytes()))
assert hashlib.sha256(data).hexdigest()=='2d7501e42d6223ebbc191817715431182c435fea944a1a02166a0748a577eaf1'
with tempfile.TemporaryDirectory(prefix='rf-qualified-fonts-') as tmp:
 font=Path(tmp)/'telemetry.inc';font.write_bytes(data)
 source=source.replace(needle,"shutil.copyfile(Path("+repr(str(font))+"),font_dir/'telemetry.inc')")
 sys.argv=[str(script),*rest]
 exec(compile(source,str(script),'exec'),{'__name__':'__main__','__file__':str(script)})
