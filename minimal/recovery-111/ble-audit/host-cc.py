#!/Library/Frameworks/Python.framework/Versions/3.11/bin/python3
"""Translate Linux linker-only flags for existing host fixtures on macOS."""
import os,sys
args=[]
for a in sys.argv[1:]:
    if os.environ.get('AUDIT_UBSAN_ONLY') and a=='-fsanitize=address,undefined': a='-fsanitize=undefined'
    if a in ('-lgcc','-no-pie','-g'): continue
    if a=='-Wl,--gc-sections': args.append('-Wl,-dead_strip');continue
    if a.startswith('-Wl,--version-script='): args.append('-Wl,-exported_symbol,_t5_driver_get');continue
    args.append(a)
os.execv('/usr/bin/cc',['cc',*args,'-Wno-unused-but-set-variable','-Wno-empty-body','-Wno-unused-function'])
