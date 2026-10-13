import json,subprocess,shutil,sys,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[1]
proof=root/'x4-ble-audit/proof/targets/target-x4'
out=root/'x4-ble-audit/rebuilt';out.mkdir(exist_ok=True)
sdk=out/'sdk';shutil.copytree(proof/'sdk',sdk,dirs_exist_ok=True)
system=root/'RiscRTE-System-ble-selected';utilities=root/'RiscRTE-Utilities'
for p in (system/'lib/PortableApps/include').glob('*.h'):shutil.copyfile(p,sdk/'include'/p.name)
sys.path.insert(0,str(root/'X4-111-wifi/minimal/recovery-108'))
from compact_current_elf import compact
cc='/Users/micahelbyrns/.platformio/packages/toolchain-xtensa-esp32s3/bin/xtensa-esp32s3-elf-gcc'
for name in ('ble_buttons','ble_touchpad'):
 r=json.loads((proof/name/'x4-native-app.json').read_text());dest=out/name;dest.mkdir(exist_ok=True)
 for f in ('catalog.c','exports.map'):shutil.copyfile(proof/name/f,dest/f)
 maps={'/workspace/shared/ble-buttons-report-recovery-20261010/target-x4':str(out),'/workspace/shared/ble-buttons-report-recovery-20261010/utilities':str(utilities),'/workspace/shared/ui-qualified-raster-source-20261010/system':str(system)}
 cmd=r['compile_command'];cmd[0]=cc
 for a,b in maps.items():cmd=[s.replace(a,b) for s in cmd]
 subprocess.run(cmd,check=True)
 elf=dest/(name+'.elf');pre=hashlib.sha256(elf.read_bytes()).hexdigest();compact(elf,cc,debug_path=dest/(name+'.debug.elf'))
 r.update(compile_command=cmd,system_source_revision=subprocess.check_output(['git','-C',str(system),'rev-parse','HEAD'],text=True).strip(),elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),elf_bytes=elf.stat().st_size,precompact_sha256=pre)
 (dest/'reconstruction.json').write_text(json.dumps(r,indent=2)+'\n');print(name,r['elf_sha256'],r['elf_bytes'],flush=True)
