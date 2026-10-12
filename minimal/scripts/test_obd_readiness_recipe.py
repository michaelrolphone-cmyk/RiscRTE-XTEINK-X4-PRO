#!/usr/bin/env python3
"""Allow only the two audited component deltas; reject authority expansion."""
import copy,errno,json,tempfile
from pathlib import Path
from unittest.mock import patch
from compose_obd_readiness import payload,CHANGED,SD_CHANGED,encoded,sha,write_shared

def fixture():
 app={'id':'obd-dashboard','version':'0.2.1','requires':[{'capability':'ui.scene','api':1},{'capability':'bluetooth.serial','api':1},{'capability':'storage.volume','api':1}]}
 driver={'id':'ble-serial','version':'0.1.0','requires':[{'capability':'bluetooth.hci','api':1},{'capability':'platform.clock','api':1}]}
 previous=b'old serial';path='Drivers/ble-serial/image-'+sha(previous)+'.elf'
 boot={'drivers':[{'manifest':'ble-serial/manifest.json','image_source':{'path':path,'volume_instance':9,'internal_fallback':True}}],'app_capabilities':[{'manifest':'obd_dashboard.json','grants':[{'capability':'bluetooth.serial','api':1,'instance_id':0}],'image_source':{'path':'Apps/obd-dashboard/obd_dashboard.elf','volume_instance':9}}]}
 old={'obd_dashboard.json':encoded(app),'ble-serial/manifest.json':encoded(driver),'ble-serial/driver.elf':previous,'boot.json':encoded(boot),'cohort.json':encoded({'version':'0.1.102','source_revision':'old'}),'unrelated.txt':b'preserve me'}
 sd={'Apps/obd-dashboard/manifest.json':encoded(app),'Apps/obd-dashboard/obd_dashboard.elf':b'old app',path:previous,'Books/keep.txt':b'private data fixture'}
 new={'obd_dashboard.json':encoded(dict(app,version='0.2.2')),'obd_dashboard.elf':b'new app','ble-serial/manifest.json':encoded(dict(driver,version='0.1.1')),'ble-serial/driver.elf':b'new serial'}
 return old,sd,new

def rejected(fn):
 try:fn()
 except (AssertionError,ValueError,RuntimeError,KeyError,SystemExit):return
 raise AssertionError('Invalid component update accepted')

def run():
 old,sd,data=fixture();saved=copy.deepcopy((old,sd,data));new,new_sd,added=payload(old,sd,data,'new-revision')
 assert (old,sd,data)==saved and len(added)==1
 assert {k for k in old if new[k]!=old[k]}==CHANGED
 assert {k for k in sd if new_sd[k]!=sd[k]}==SD_CHANGED
 assert new['unrelated.txt']==old['unrelated.txt'] and new_sd['Books/keep.txt']==sd['Books/keep.txt']
 assert next(v for k,v in new_sd.items() if k.startswith('Drivers/ble-serial/image-') and v==b'old serial')==b'old serial'
 for key in ('obd_dashboard.json','ble-serial/manifest.json'):
  bad=copy.deepcopy(data);m=json.loads(bad[key]);m['requires'].append({'capability':'unexpected.authority','api':1});bad[key]=encoded(m);rejected(lambda:payload(old,sd,bad,'new'))
 bad=copy.deepcopy(data);bad['surprise.elf']=b'bad';rejected(lambda:payload(old,sd,bad,'new'))
 bad=copy.deepcopy(sd);bad['Apps/obd-dashboard/manifest.json']=b'{}';rejected(lambda:payload(old,bad,data,'new'))
 bad=copy.deepcopy(sd);bad[next(iter(added))]=b'collision';rejected(lambda:payload(old,bad,data,'new'))
 bad=copy.deepcopy(old);m=json.loads(bad['boot.json']);m['drivers'][0]['image_source']['internal_fallback']=False;bad['boot.json']=encoded(m);rejected(lambda:payload(bad,sd,data,'new'))
 with tempfile.TemporaryDirectory() as temp:
  root=Path(temp);source=root/'source';source.mkdir();(source/'keep').write_bytes(b'original')
  with patch('compose_obd_readiness.os.link',side_effect=OSError(errno.EXDEV,'Cross-device fixture')):
   write_shared(root/'output',{'keep':b'original','added':b'new'},source)
  assert (root/'output/keep').read_bytes()==(source/'keep').read_bytes()==b'original'
  assert (root/'output/added').read_bytes()==b'new'
 print('OBD overlay: exact delta, unrelated bytes, prior provider preserved, six rejection cases PASS')
if __name__=='__main__':run()
