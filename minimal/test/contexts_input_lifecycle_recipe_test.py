import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import compose_contexts_input_lifecycle as a
import build_contexts_input_lifecycle as b
class RecipeTest(unittest.TestCase):
 def prior(self):
  manifest=a.encoded({'version':'0.4.3','requires':[{'capability':'ui.text-input','api':1},{'capability':'radio.iq','api':1}]})
  directory='Apps/contexts/image-'+a.PRIOR['x4']
  return {'contexts.json':manifest,'default.elf':b'preserved-home','ui-text/driver.elf':b'preserved-text','ui-scene/driver.elf':b'preserved-scene',
   'boot.json':a.encoded({'app_capabilities':[{'manifest':'contexts.json','grants':[a.GRANT],'image_source':{'path':directory+'/contexts.elf','volume_instance':9}},{'manifest':'lists.json','grants':[a.GRANT]}],'drivers':[{'manifest':'ui-text/manifest.json','image_source':{'path':'frozen-host'}}]}),
   'cohort.json':a.encoded({'version':'0.1.102','source_revision':a.BASE})}, {directory+'/contexts.elf':b'old',directory+'/manifest.json':manifest,'Apps/contexts/contexts.elf':b'older-flat','Apps/contexts/manifest.json':b'older-flat-manifest','Apps/lists/lists.elf':b'older-lists','frozen-host':b'preserved-host'}
 def component(self,old):return {'contexts.elf':b'new','contexts.json':a.encoded(dict(json.loads(old['contexts.json']),version=b.VERSION))}
 def test_exact_delta_and_preserved_bytes(self):
  old,sd=self.prior();before=copy.deepcopy((old,sd));new,new_sd,added=a.payload(old,sd,self.component(old),'new')
  self.assertEqual((old,sd),before);self.assertEqual({n for n in new if old[n]!=new[n]},a.CHANGED);self.assertEqual(len(added),2)
  for n in sd:self.assertEqual(sd[n],new_sd[n],n)
  for n in set(old)-a.CHANGED:self.assertEqual(old[n],new[n],n)
 def test_only_selection_changes_in_boot(self):
  old,sd=self.prior();new,new_sd,added=a.payload(old,sd,self.component(old),'new');actual=json.loads(new['boot.json']);expected=json.loads(old['boot.json']);expected['app_capabilities'][0]['image_source']['path']='Apps/contexts/image-'+a.sha(b'new')+'/contexts.elf';self.assertEqual(actual,expected)
 def test_manifest_only_version_changes(self):
  old,sd=self.prior();new,_,_=a.payload(old,sd,self.component(old),'new');self.assertEqual(json.loads(new['contexts.json']),dict(json.loads(old['contexts.json']),version='0.4.4'))
 def test_excess_authority_rejected(self):
  old,sd=self.prior();c=self.component(old);m=json.loads(c['contexts.json']);m['requires'].append({'capability':'net.http','api':1});c['contexts.json']=a.encoded(m)
  with self.assertRaises(ValueError):a.payload(old,sd,c,'new')
 def test_flat_image_not_selected(self):
  old,sd=self.prior();boot=json.loads(old['boot.json']);boot['app_capabilities'][0]['image_source']['path']='Apps/contexts/contexts.elf';old['boot.json']=a.encoded(boot)
  with self.assertRaises(ValueError):a.payload(old,sd,self.component(old),'new')
 def test_immutable_collision_rejected(self):
  old,sd=self.prior();sd['Apps/contexts/image-'+a.sha(b'new')+'/contexts.elf']=b'collision'
  with self.assertRaises(ValueError):a.payload(old,sd,self.component(old),'new')
 def test_wrong_baseline_rejected(self):
  old,sd=self.prior();old['cohort.json']=a.encoded({'version':'0.1.102','source_revision':'other'})
  with self.assertRaises(ValueError):a.payload(old,sd,self.component(old),'new')
 def test_duplicate_inherited_grant_rejected(self):
  old,sd=self.prior();m=json.loads(old['boot.json']);m['app_capabilities'][0]['grants'].append(a.GRANT);old['boot.json']=a.encoded(m)
  with self.assertRaises(ValueError):a.payload(old,sd,self.component(old),'new')
 def test_inherited_flags_retained(self):
  prior=json.loads((b.DOCS/'baseline.json').read_text());self.assertEqual(prior['defines'],['-DCONTEXTS_ALARM_API=2','-DCONTEXTS_SETTING_MASK=0x274u','-DPORTABLE_NATIVE_TIME_TOOLBAR','-DPORTABLE_CONTEXTS_SOURCE_MASK=CONTEXTS_RADIO']);self.assertEqual(b.ADDITIONS,['-DPORTABLE_CONTEXTS_SHARED_TEXT_INPUT'])
 def test_unselected_sources_block_build(self):
  before=b.SELECTION['finalized'];b.SELECTION['finalized']=False
  try:
   with self.assertRaisesRegex(ValueError,'Final published'):b.build(None)
  finally:b.SELECTION['finalized']=before
if __name__=='__main__':unittest.main()
