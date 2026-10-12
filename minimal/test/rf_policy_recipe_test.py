import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import compose_rf_policy as a
import build_rf_policy as b
class RecipeTest(unittest.TestCase):
 def prior(self):
  manifest=a.encoded({'version':'0.3.4','requires':[{'capability':'ui.text-input','api':1},{'capability':'radio.iq','api':1}]})
  directory='Apps/waterfall'
  return {'waterfall.json':manifest,'default.elf':b'preserved-home','ui-text/driver.elf':b'preserved-text','ui-scene/driver.elf':b'preserved-scene',
   'boot.json':a.encoded({'app_capabilities':[{'manifest':'waterfall.json','grants':[a.GRANT],'image_source':{'path':directory+'/waterfall.elf','volume_instance':9}},{'manifest':'lists.json','grants':[a.GRANT]}],'drivers':[{'manifest':'ui-text/manifest.json','image_source':{'path':'frozen-host'}}]}),
   'cohort.json':a.encoded({'version':'0.1.102','source_revision':a.BASE})}, {directory+'/waterfall.elf':b'old',directory+'/manifest.json':manifest,'Apps/lists/lists.elf':b'older-lists','frozen-host':b'preserved-host'}
 def component(self,old):return {'waterfall.elf':b'new','waterfall.json':a.encoded(dict(json.loads(old['waterfall.json']),version=b.VERSION))}
 def test_exact_delta_and_preserved_bytes(self):
  old,sd=self.prior();before=copy.deepcopy((old,sd));new,new_sd,added=a.payload(old,sd,self.component(old),'new')
  self.assertEqual((old,sd),before);self.assertEqual({n for n in new if old[n]!=new[n]},a.CHANGED);self.assertEqual(len(added),2)
  for n in sd:self.assertEqual(sd[n],new_sd[n],n)
  for n in set(old)-a.CHANGED:self.assertEqual(old[n],new[n],n)
 def test_only_selection_changes_in_boot(self):
  old,sd=self.prior();new,new_sd,added=a.payload(old,sd,self.component(old),'new');actual=json.loads(new['boot.json']);expected=json.loads(old['boot.json']);expected['app_capabilities'][0]['image_source']['path']='Apps/waterfall/image-'+a.sha(b'new')+'/waterfall.elf';self.assertEqual(actual,expected)
 def test_manifest_only_version_changes(self):
  old,sd=self.prior();new,_,_=a.payload(old,sd,self.component(old),'new');self.assertEqual(json.loads(new['waterfall.json']),dict(json.loads(old['waterfall.json']),version='0.3.5'))
 def test_excess_authority_rejected(self):
  old,sd=self.prior();c=self.component(old);m=json.loads(c['waterfall.json']);m['requires'].append({'capability':'net.http','api':1});c['waterfall.json']=a.encoded(m)
  with self.assertRaises(ValueError):a.payload(old,sd,c,'new')
 def test_other_image_not_selected(self):
  old,sd=self.prior();boot=json.loads(old['boot.json']);boot['app_capabilities'][0]['image_source']['path']='Apps/waterfall/wrong.elf';old['boot.json']=a.encoded(boot)
  with self.assertRaises(ValueError):a.payload(old,sd,self.component(old),'new')
 def test_immutable_collision_rejected(self):
  old,sd=self.prior();sd['Apps/waterfall/image-'+a.sha(b'new')+'/waterfall.elf']=b'collision'
  with self.assertRaises(ValueError):a.payload(old,sd,self.component(old),'new')
 def test_wrong_baseline_rejected(self):
  old,sd=self.prior();old['cohort.json']=a.encoded({'version':'0.1.102','source_revision':'other'})
  with self.assertRaises(ValueError):a.payload(old,sd,self.component(old),'new')
 def test_duplicate_inherited_grant_rejected(self):
  old,sd=self.prior();m=json.loads(old['boot.json']);m['app_capabilities'][0]['grants'].append(a.GRANT);old['boot.json']=a.encoded(m)
  with self.assertRaises(ValueError):a.payload(old,sd,self.component(old),'new')
 def test_policy_flag_preserves_inherited_order(self):
  old=['-DPORTABLE_NOVA_UI'];new=b.add_unique(old,b.COMMON);self.assertEqual(new[0],old[0]);self.assertIn('-DPORTABLE_TEXT_INPUT_POLICY',new)
 def test_only_new_feature_flag(self):self.assertEqual(b.COMMON,['-DPORTABLE_TEXT_INPUT_POLICY'])
if __name__=='__main__':unittest.main()
