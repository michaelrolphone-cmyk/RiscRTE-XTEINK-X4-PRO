import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import compose_lists_shared_input as a

class RecipeTest(unittest.TestCase):
 def prior(self):
  m=a.encoded({'version':'0.1.1','requires':[]})
  return ({'default.elf':b'old-owner','default.json':a.encoded({'version':'0.4.14','requires':[]}),'lists.json':m,'file_browser.elf':b'Files-opt-in','ui-scene/driver.elf':b'scene-host','ui-scene/manifest.json':a.encoded({'version':'0.4.4','requires':[{'capability':'display.output','api':1}]}),'ui-text/driver.elf':b'text-host','ui-text/manifest.json':a.encoded({'version':'0.1.5','requires':[{'capability':'ui.scene','api':1}]}),'boot.json':a.encoded({'app_capabilities':[{'manifest':'lists.json','grants':[],'image_source':{'path':'Apps/lists/lists.elf','volume_instance':9}},{'manifest':'file_browser.json','grants':[a.GRANT]}],'drivers':[{'manifest':'ui-text/manifest.json','image_source':{'internal_fallback':True,'path':'Drivers/text-input-host/image-'+a.HOST_PRIOR['x4'][1]+'.elf','volume_instance':9}},{'manifest':'ui-scene/manifest.json','image_source':{'internal_fallback':True,'path':'Drivers/scene-host/image-'+a.SCENE_PRIOR['x4'][1]+'.elf','volume_instance':9}}]}),'cohort.json':a.encoded({'version':'0.1.102','source_revision':a.BASE})}, {'Apps/lists/lists.elf':b'old-selected','Apps/lists/manifest.json':m,'Drivers/scene-host/image-'+a.SCENE_PRIOR['x4'][1]+'.elf':b'scene-host','Drivers/ui-text/image-immutable.elf':b'text-host','Drivers/text-input-host/image-'+a.HOST_PRIOR['x4'][1]+'.elf':b'text-host'})
 def component(self,old):
  m=json.loads(old['lists.json']);m['version']=a.VERSION;m['requires'].append({'capability':'ui.text-input','api':1})
  return {'default.elf':b'new-owner','default.json':a.encoded(dict(json.loads(old['default.json']),version=a.OWNER_VERSION)),'lists.json':a.encoded(m),'lists.elf':b'new-rf','ui-scene/driver.elf':b'new-scene','ui-scene/manifest.json':a.encoded(dict(json.loads(old['ui-scene/manifest.json']),version=a.SCENE_VERSION)),'ui-text/driver.elf':b'new-text','ui-text/manifest.json':a.encoded(dict(json.loads(old['ui-text/manifest.json']),version=a.TEXT_VERSION))}
 def test_preserve_union_and_immutable_hosts(self):
  old,sd=self.prior();frozen=copy.deepcopy((old,sd));new,new_sd,additions=a.payload(old,sd,self.component(old),'next')
  self.assertEqual((old,sd),frozen);self.assertEqual({n for n in new if new[n]!=old[n]},a.CHANGED);self.assertEqual({n for n in sd if new_sd[n]!=sd[n]},a.SD_CHANGED)
  self.assertEqual(len(additions),4);self.assertEqual(new_sd['Apps/lists/lists.elf'],b'old-selected')
  self.assertEqual(new_sd['Drivers/ui-text/image-immutable.elf'],sd['Drivers/ui-text/image-immutable.elf'])
  before=json.loads(old['boot.json'])['drivers'];after=json.loads(new['boot.json'])['drivers'];after[0]['image_source']['path']=before[0]['image_source']['path'];after[1]['image_source']['path']=before[1]['image_source']['path'];self.assertEqual(after,before)
 def test_mismatch_manifest_rejected(self):
  old,sd=self.prior();sd['Apps/lists/manifest.json']=b'{}'
  with self.assertRaises(ValueError):a.payload(old,sd,self.component(old),'next')
 def test_additional_member_rejected(self):
  old,sd=self.prior();component=self.component(old);component['native.bin']=b'bad'
  with self.assertRaises(ValueError):a.payload(old,sd,component,'next')
 def test_extra_authority_rejected(self):
  old,sd=self.prior();component=self.component(old);m=json.loads(component['lists.json']);m['requires'].append({'capability':'net.http','api':1});component['lists.json']=a.encoded(m)
  with self.assertRaises(ValueError):a.payload(old,sd,component,'next')
 def test_text_authority_rejected(self):
  old,sd=self.prior();component=self.component(old);m=json.loads(component['ui-text/manifest.json']);m['requires'].append({'capability':'usb.hid','api':1});component['ui-text/manifest.json']=a.encoded(m)
  with self.assertRaises(ValueError):a.payload(old,sd,component,'next')
 def test_text_fallback_change_rejected(self):
  old,sd=self.prior();b=json.loads(old['boot.json']);b['drivers'][0]['image_source']['internal_fallback']=False;old['boot.json']=a.encoded(b)
  with self.assertRaises(ValueError):a.payload(old,sd,self.component(old),'next')
 def test_owner_authority_rejected(self):
  old,sd=self.prior();component=self.component(old);m=json.loads(component['default.json']);m['requires'].append({'capability':'usb.hid','api':1});component['default.json']=a.encoded(m)
  with self.assertRaises(ValueError):a.payload(old,sd,component,'next')
 def test_scene_authority_rejected(self):
  old,sd=self.prior();component=self.component(old);m=json.loads(component['ui-scene/manifest.json']);m['requires'].append({'capability':'usb.hid','api':1});component['ui-scene/manifest.json']=a.encoded(m)
  with self.assertRaises(ValueError):a.payload(old,sd,component,'next')
 def test_scene_fallback_change_rejected(self):
  old,sd=self.prior();b=json.loads(old['boot.json']);b['drivers'][1]['image_source']['internal_fallback']=False;old['boot.json']=a.encoded(b)
  with self.assertRaises(ValueError):a.payload(old,sd,self.component(old),'next')
 def test_wrong_immutable_selection_rejected(self):
  old,sd=self.prior();boot=json.loads(old['boot.json']);boot['app_capabilities'][0]['image_source']['path']='Apps/lists/wrong.elf';old['boot.json']=a.encoded(boot)
  with self.assertRaises(ValueError):a.payload(old,sd,self.component(old),'next')
if __name__=='__main__':unittest.main()
