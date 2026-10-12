import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import compose_contexts_shared_input as a

class RecipeTest(unittest.TestCase):
 def prior(self):
  m=a.encoded({'version':'0.4.2','requires':[]})
  return ({'contexts.json':m,'file_browser.elf':b'Files-opt-in','ui-text/driver.elf':b'text-host','boot.json':a.encoded({'app_capabilities':[{'manifest':'contexts.json','grants':[],'image_source':{'path':'Apps/contexts/image-'+a.PRIOR['x4']+'/contexts.elf','volume_instance':9}},{'manifest':'file_browser.json','grants':[a.GRANT]}],'drivers':[{'image_source':{'path':'Drivers/ui-text/image-immutable.elf'}}]}),'cohort.json':a.encoded({'version':'0.1.102','source_revision':a.BASE})}, {'Apps/contexts/image-'+a.PRIOR['x4']+'/contexts.elf':b'old-selected','Apps/contexts/image-'+a.PRIOR['x4']+'/manifest.json':m,'Apps/contexts/contexts.elf':b'old-rf','Apps/contexts/manifest.json':m,'Drivers/ui-text/image-immutable.elf':b'text-host'})
 def component(self,old):
  m=json.loads(old['contexts.json']);m['version']=a.VERSION;m['requires'].append({'capability':'ui.text-input','api':1})
  return {'contexts.json':a.encoded(m),'contexts.elf':b'new-rf'}
 def test_preserve_union_and_immutable_hosts(self):
  old,sd=self.prior();frozen=copy.deepcopy((old,sd));new,new_sd,additions=a.payload(old,sd,self.component(old),'next')
  self.assertEqual((old,sd),frozen);self.assertEqual({n for n in new if new[n]!=old[n]},a.CHANGED);self.assertEqual({n for n in sd if new_sd[n]!=sd[n]},a.SD_CHANGED)
  self.assertEqual(len(additions),2);self.assertEqual(new_sd['Apps/contexts/image-'+a.PRIOR['x4']+'/contexts.elf'],b'old-selected')
  self.assertEqual(new_sd['Drivers/ui-text/image-immutable.elf'],sd['Drivers/ui-text/image-immutable.elf'])
  self.assertEqual(json.loads(new['boot.json'])['drivers'],json.loads(old['boot.json'])['drivers'])
 def test_mismatch_manifest_rejected(self):
  old,sd=self.prior();sd['Apps/contexts/image-'+a.PRIOR['x4']+'/manifest.json']=b'{}'
  with self.assertRaises(ValueError):a.payload(old,sd,self.component(old),'next')
 def test_additional_member_rejected(self):
  old,sd=self.prior();component=self.component(old);component['native.bin']=b'bad'
  with self.assertRaises(ValueError):a.payload(old,sd,component,'next')
 def test_extra_authority_rejected(self):
  old,sd=self.prior();component=self.component(old);m=json.loads(component['contexts.json']);m['requires'].append({'capability':'net.http','api':1});component['contexts.json']=a.encoded(m)
  with self.assertRaises(ValueError):a.payload(old,sd,component,'next')
 def test_wrong_immutable_selection_rejected(self):
  old,sd=self.prior();boot=json.loads(old['boot.json']);boot['app_capabilities'][0]['image_source']['path']='Apps/contexts/contexts.elf';old['boot.json']=a.encoded(boot)
  with self.assertRaises(ValueError):a.payload(old,sd,self.component(old),'next')
if __name__=='__main__':unittest.main()

