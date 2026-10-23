import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from filmcraft_shadow import shadow_layer_props,scoped_shadow_profile

class ScopedShadowTests(unittest.TestCase):
    def policy(self):
        return {'brand':'brand_x','production_type':'l1_short','stage':'captions','settings':{'caption_shadow':{'backends':{'filmcraft':{'status':'native_inspected','profile':{'id':'light-v1','wide_opacity':65,'tight_opacity':80}}}}}}

    def test_scope_and_inspection_before_override(self):
        p=self.policy()
        profile=scoped_shadow_profile(p,brand='brand_x',production_type='l1_short')
        self.assertEqual(shadow_layer_props('wide',75,profile)['shadow_opacity'],65)
        self.assertEqual(shadow_layer_props('tight',75,profile)['shadow_opacity'],80)
        self.assertIsNone(scoped_shadow_profile(p,brand='brand_y',production_type='l1_short'))
        self.assertIsNone(scoped_shadow_profile(p,brand='brand_x',production_type='podcast_short'))
        p['settings']['caption_shadow']['backends']['filmcraft']['status']='pending'
        self.assertIsNone(scoped_shadow_profile(p,brand='brand_x',production_type='l1_short'))

    def test_only_opacity_changes_and_legacy_unchanged(self):
        profile=scoped_shadow_profile(self.policy(),brand='brand_x',production_type='l1_short')
        for role in ('wide','tight','text'):
            original=shadow_layer_props(role,75);changed=shadow_layer_props(role,75,profile)
            self.assertEqual({k:v for k,v in original.items() if k!='shadow_opacity'},
                             {k:v for k,v in changed.items() if k!='shadow_opacity'})
            if role!='text':self.assertEqual(original['shadow_opacity'],100)

    def test_invalid_values_do_not_become_shadow_settings(self):
        for value in (-1,101,float('nan'),True):
            with self.assertRaises(ValueError):shadow_layer_props('wide',75,{'id':'bad','wide_opacity':value,'tight_opacity':80})

if __name__=='__main__':unittest.main()
