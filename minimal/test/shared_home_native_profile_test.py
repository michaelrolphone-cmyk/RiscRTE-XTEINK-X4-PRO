#!/usr/bin/env python3
"""Configure actual product profile and prove only the capacity delta from .123."""
import hashlib,os,re,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
runtime=Path(os.environ['RISCRTE_RUNTIME_ROOT']).resolve()
with tempfile.TemporaryDirectory() as t:
 work=Path(t)
 (work/'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.22)\nproject(home_contract NONE)\nset(RISC_RUNTIME_ROOT "'+str(runtime)+'")\ninclude("'+str(ROOT/'profiles/native-shared-home.cmake')+'")\nfile(WRITE "${CMAKE_BINARY_DIR}/definitions.txt" "${RISC_NATIVE_DEFINITIONS}")\n')
 subprocess.run(['cmake','-S',str(work),'-B',str(work/'build')],check=True)
 actual=(work/'build/definitions.txt').read_text().split(';')
 before=(ROOT/'profiles/native-provision-123.cmake').read_text()
 block=re.search(r'set\(RISC_NATIVE_DEFINITIONS\n(.*?)\)\nset\(RISC_NATIVE_COMPILE_OPTIONS',before,re.S).group(1)
 import shlex
 expected=shlex.split(block)
 expected=[x.replace('RISC_APP_REQUIREMENT_ROWS=24','RISC_APP_REQUIREMENT_ROWS=32') for x in expected]
 assert sorted(actual)==sorted(expected),(actual,expected)
 assert actual.count('RISC_APP_POLICY_ROWS=32')==actual.count('RISC_APP_REQUIREMENT_ROWS=32')==1
 selection=(work/'build/x4-native-idf61/selection.txt').read_text()
 payload,digest=selection.rsplit('composition_sha256=',1)
 assert hashlib.sha256(payload.encode()).hexdigest()==digest.strip()
 assert 'sha256:profiles/native-shared-home.cmake=' in payload
 assert 'RISC_NATIVE_SERIAL_FILES=1' in actual and 'RISC_PLATFORM_CAPACITY=40' in actual
print('Actual X4 shared Home profile: full .123 features and only requirement24->32 delta PASS')
