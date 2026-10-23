import copy
import hashlib
import io
import os
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import editorial_context as ec
from scoped_policy import camera_exclusion_matches, load_brand_profile, select_stage, validate_scope, validate_scoped_policies


class ScopedPolicyTests(unittest.TestCase):
    def row(self, stage='assembly'):
        body = 'Preserve the applicable condition; source limitations belong in the existing handoff.'
        return dict(policy_id='brand-policy', version=1, brand='brand_x', production_type='l1_short',
                    stage=stage, source_id='source1', original_source_id='original1', source_title='Draft guidance',
                    source_body=body, source_sha256=hashlib.sha256(body.encode()).hexdigest(),
                    settings={'music_default': 'off'}, priority_note='No new quality gate',
                    evidence_class='USER_DIRECTED_SCOPED_POLICY_FROM_DRAFT', verification_note='Not final-media proof')

    def test_exact_scope_and_answer_only_independence(self):
        scope = validate_scope('brand_x', 'l1_short', 'assembly')
        self.assertEqual(len(validate_scoped_policies({'policies':[self.row()]}, scope)), 1)
        # No content-unit format in this binding: monologue answer-only remains covered.
        self.assertNotIn('format', scope)

    def test_no_cross_brand_production_or_stage_leak(self):
        for field,value in [('brand','brand_y'),('production_type','podcast_short'),('stage','reframe')]:
            row=self.row();row[field]=value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_scoped_policies({'policies':[row]},validate_scope('brand_x','l1_short','assembly'))

    def test_hash_duplicate_and_partial_scope(self):
        row=self.row();row['source_body'] += 'unrecorded change'
        with self.assertRaises(ValueError):
            validate_scoped_policies({'policies':[row]},validate_scope('brand_x','l1_short'))
        with self.assertRaises(ValueError):
            validate_scoped_policies({'policies':[self.row(),self.row()]},validate_scope('brand_x','l1_short'))
        for args in [('brand_x',None,None),('../brand_x','l1_short',None),(None,None,'assembly')]:
            with self.assertRaises(ValueError):validate_scope(*args)

    def test_empty_match_is_not_quality_failure(self):
        self.assertEqual(validate_scoped_policies({'policies':[],'status':'no_match'},validate_scope('brand_x','l1_short')),[])

    def test_same_run_stage_selection(self):
        ctx={'scoped_policy':{'policies':[self.row(),self.row('audio')]}}
        result=select_stage(ctx,brand='brand_x',production_type='l1_short',stage='audio')
        self.assertEqual(result['settings']['music_default'],'off')

    def test_profile_discovery_identity(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'brand_x'/'_brand'/'editorial_profile.json';p.parent.mkdir(parents=True)
            p.write_text(json.dumps({'schema':'edit.brand-editorial-profile/v1','brand':'brand_x'}))
            self.assertEqual(load_brand_profile('brand_x',root=root)['brand'],'brand_x')
            self.assertIsNone(load_brand_profile('brand_y',root=root))
            p.write_text(json.dumps({'schema':'edit.brand-editorial-profile/v1','brand':'brand_y'}))
            with self.assertRaises(ValueError):load_brand_profile('brand_x',root=root)

    def test_exclusions_follow_source_clock_and_exact_session(self):
        entries=[{'session_id':'session-x','camera_id':'cam-b','media':'/source/camera-b.mov',
                  'source_ticks':['100','200'],'reason':'Reviewer excluded unstable section'}]
        args={'session_id':'session-x','camera_id':'cam-b','media':'/source/camera-b.mov','source_ticks':['150','250']}
        self.assertEqual(len(camera_exclusion_matches(entries,**args)),1)
        self.assertEqual(camera_exclusion_matches(entries,**{**args,'source_ticks':['200','300']}),[])
        self.assertEqual(camera_exclusion_matches(entries,**{**args,'session_id':'session-y'}),[])
        self.assertEqual(camera_exclusion_matches(entries,**{**args,'camera_id':'cam-c'}),[])
        entries[0]['source_ticks']=None
        self.assertEqual(len(camera_exclusion_matches(entries,**{**args,'source_ticks':['500','600']})),1)

    def test_scoped_integrity_failure_does_not_block_valid_format_context(self):
        body='Current valid format guidance'
        digest=hashlib.sha256(body.encode()).hexdigest()
        for failure in ('missing','wrong_scope','bad_hash'):
            query={'problem':'question context','format':'q_and_a','limit':5,'includeDevelopment':False,
                   'currentProjectPrefix':None,'heldOutSourcePrefixes':[],'includeRequiredReading':False,
                   'readingOverlays':[],'brand':'brand_x','productionType':'l1_short','stage':'assembly'}
            row=self.row()
            if failure=='wrong_scope':query['brand']='brand_y'
            if failure=='bad_hash':row['source_body']+='changed'
            payload={'schema':'editorial-brain.context/v1','project_ref':'projectref','query':query,
                     'playbooks':[{'format':f,'body':body,'body_sha256':digest,'version':1} for f in ('universal','q_and_a')],
                     'cards':[],'scoped_policy':{'policies':[row]}}
            if failure=='missing':payload.pop('scoped_policy')
            with self.subTest(failure=failure), patch.dict(os.environ,{
                'EDITORIAL_BRAIN_FUNCTION_URL':'https://projectref.supabase.co/functions/v1/editorial-search',
                'EDITORIAL_BRAIN_PROJECT_REF':'projectref','EDITORIAL_BRAIN_READ_KEY':'test-key'}), \
                    patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(payload).encode())):
                result=ec.fetch_context(problem='question context',fmt='q_and_a',brand='brand_x',production_type='l1_short',stage='assembly')
                self.assertEqual(len(result['playbooks']),2)
                self.assertEqual(result['scoped_policy']['status'],'unavailable')
                self.assertEqual(result['scoped_policy']['policies'],[])


if __name__=='__main__':unittest.main()
