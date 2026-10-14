from pathlib import Path
from types import SimpleNamespace
import json,subprocess,sys,shutil,hashlib
R=Path(__file__).resolve().parents[2];S=R/'System-t052';O=R/'t052-build/x4';O.mkdir(exist_ok=True)
sys.path.insert(0,str(S/'scripts'));from portable_file_sharing_build import configure
cc=json.loads((R/'t051-product-build/watch-wifi-command.json').read_text())[0]
shutil.copytree(R/'t051-evidence/x4-target/native-time-sdk',O/'native-time-sdk',dirs_exist_ok=True)
include=O/'native-time-sdk/include'
# Keep the selected Runtime/time/alarm ABI headers; update portable implementation helpers.
for p in (S/'lib/PortableApps/include').iterdir():
 if p.is_file() and p.name.startswith('Portable'):shutil.copyfile(p,include/p.name)
receipt=json.loads((R/'X4-input-product/minimal/docs/evidence/mounted-files-097-final/file_browser-build-record.json').read_text())
flags=receipt['defines']+['-DPORTABLE_FILE_BROWSER_SHARED_INPUT','-DPORTABLE_TEXT_INPUT_CLIENT','-DPORTABLE_TEXT_INPUT_POLICY']
profile=SimpleNamespace(peer_files=True,webdav_sharing=True,sharing_export_instance=0,sharing_tcp_instance=0,sharing_entropy_instance=0,sharing_setup_instance=0)
_,more,_=configure(profile,S,O,include,cc)
(O/'catalog.c').write_text('#include "PortableApps.h"\nconst t5_app_manifest_t portable_catalog[1]={{.compatible=false}};const unsigned portable_catalog_count=0;\n')
(O/'file_browser.map').write_text('{ global: app_main; app_module_init; app_module_fini; local: *; };\n')
sources=[S/'Apps/file_browser.c',S/'lib/PortableApps/src/adapter.c',O/'catalog.c']+[S/'lib/PortableApps/src'/n for n in ['PortableNativeTimeSource.c','PortableRealtimeClient.c','PortableTimeZone.c','PortableTimeZoneCatalog.c','PortableTimeZonePreference.c']]+more
elf=O/'file_browser.elf';cmd=[cc,'-std=c11','-Os','-fPIC','-mtext-section-literals','-mlongcalls','-fvisibility=hidden','-ffreestanding','-fno-builtin','-nostdlib','-nostartfiles','-shared','-Wl,--no-relax','-Wl,--hash-style=sysv','-Wl,--version-script='+str(O/'file_browser.map'),'-Wall','-Wextra','-Werror',*flags,'-I'+str(include),'-I'+str(S/'lib/NativeApps/include'),*map(str,sources),'-lgcc','-o',str(elf)]
(O/'command.json').write_text(json.dumps(cmd,indent=2)+'\n')
with (O/'build.log').open('w') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
subprocess.run([str(R.parent/'task-2/target-providers/validate-elf'),str(elf)],check=True)
(O/'build.json').write_text(json.dumps(dict(sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),bytes=elf.stat().st_size,system_source=subprocess.check_output(['git','-C',S,'rev-parse','HEAD'],text=True).strip(),version='1.5.38'),indent=2)+'\n');print(elf.stat().st_size)
