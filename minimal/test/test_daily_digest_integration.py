#!/usr/bin/env python3
"""Check additive X4 registration, dated SD identity, and cohort preservation."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('daily',ROOT/'minimal/scripts/integrate_daily_digest.py')
daily=importlib.util.module_from_spec(spec);spec.loader.exec_module(daily)

class Integration(unittest.TestCase):
    def setUp(self):
        self.manifest={'id':'daily-digest','file_name':'daily_digest.elf',
            'requires':[{'capability':c,'api':1} for c in daily.INSTANCES]}
        self.boot={'app_capabilities':[{'manifest':'ebook_reader.json',
            'image_source':{'volume_instance':9,'path':'Apps/ebook-reader/ebook_reader.elf'}},
            *[{'manifest':f'app{i}.json','grants':[]} for i in range(24)]],
            'drivers':[{'manifest':f'driver{i}/manifest.json'} for i in range(27)],
            'resident_shell':{'foreground':['ebook_reader.elf'],'legacy':['gameboy.elf']}}
    def test_additive_and_idempotent(self):
        frozen=copy.deepcopy(self.boot);out=daily.policy(self.boot,self.manifest)
        self.assertEqual(self.boot,frozen)
        self.assertEqual(out['app_capabilities'][:-1],frozen['app_capabilities'])
        self.assertEqual(out['drivers'][:-1],frozen['drivers'])
        self.assertEqual(len(out['app_capabilities']),26);self.assertEqual(len(out['drivers']),28)
        self.assertEqual(daily.policy(out,self.manifest),out)
        row=out['app_capabilities'][-1]
        self.assertEqual(row['image_source']['path'],'Apps/daily-digest/daily_digest.elf')
        self.assertEqual({g['capability']:g['instance_id'] for g in row['grants']},daily.INSTANCES)
        self.assertEqual(out['resident_shell']['legacy'],frozen['resident_shell']['legacy'])
    def test_reject_legacy(self):
        del self.boot['app_capabilities'][0]['image_source']
        with self.assertRaises(ValueError):daily.policy(self.boot,self.manifest)
    def test_reject_conflicting_row(self):
        self.boot['app_capabilities'].append({'manifest':'daily_digest.json','grants':[]})
        with self.assertRaises(ValueError):daily.policy(self.boot,self.manifest)
    def test_reject_capacity_overflow(self):
        self.boot['drivers'].append({'manifest':'extra/manifest.json'})
        with self.assertRaises(ValueError):daily.policy(self.boot,self.manifest)
    def test_catalog_addition(self):
        catalog=json.loads((ROOT/'minimal/sd-app-catalog.json').read_text())['apps']
        names=[r['file_name'] for r in catalog]
        self.assertEqual(len(names),len(set(names)))
        self.assertIn('ebook_reader.elf',names)
        self.assertEqual([r for r in catalog if r['file_name']=='daily_digest.elf'],[
            {'display_name':'Daily Paper','file_name':'daily_digest.elf','icon':'solid:f15b'}])

if __name__=='__main__':unittest.main()
