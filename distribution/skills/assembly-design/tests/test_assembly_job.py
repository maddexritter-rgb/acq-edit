"""Synthetic invariant tests. A fixture PASS is not an editorial or listening verdict."""
import copy
from fractions import Fraction
import json
from pathlib import Path
import subprocess
import runpy
import sys
import types
import unittest
from unittest.mock import patch
import tempfile
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'edit/scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import assembly_job as jobmod
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'live-clip/scripts'))
import measured_multicam_xml as multicam
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'edit/scripts'))
import review_xml
import test_assembly_plan as fixtures
compiler = fixtures.m


class DigestCacheTests(unittest.TestCase):
    def test_unsigned_64_bit_filesystem_identity_uses_persistent_cache(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = root / 'sha256.sqlite3'
            key = (str(root / 'media.bin'), 2**64 - 2, 2**64 - 1, 4096,
                   2**63 + 1, 2**63 + 2)
            with patch.object(jobmod, '_HASH_DB', db):
                self.assertEqual(jobmod._persistent_digest(Path(key[0]), key, 'sample', 'digest'),
                                 'digest')
                self.assertEqual(jobmod._persistent_digest(Path(key[0]), key, 'sample'),
                                 'digest')
                self.assertIsNone(jobmod._persistent_digest(Path(key[0]), key, 'changed'))

    def test_large_media_digest_reuses_validated_persistent_entry(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            media = root / 'media.bin'
            media.write_bytes(b'a' * 4096)
            with patch.object(jobmod, '_PERSIST_MIN_BYTES', 1), \
                    patch.object(jobmod, '_HASH_DB', root / 'sha256.sqlite3'):
                jobmod._DIGEST_CACHE.clear()
                expected = jobmod.digest(media)
                jobmod._DIGEST_CACHE.clear()
                sample = jobmod._sample_digest(media, media.stat().st_size)
                with patch.object(jobmod, '_sample_digest', return_value=sample), \
                        patch.object(Path, 'open', side_effect=AssertionError('full reread')):
                    self.assertEqual(jobmod.digest(media), expected)
                jobmod._DIGEST_CACHE.clear()
                media.write_bytes(b'b' * 4096)
                self.assertNotEqual(jobmod.digest(media), expected)
                jobmod._DIGEST_CACHE.clear()

    def test_digest_cache_failure_falls_back_to_full_hash(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            media = root / 'media.bin'
            media.write_bytes(b'evidence')
            with patch.object(jobmod, '_PERSIST_MIN_BYTES', 1), \
                    patch.object(jobmod, '_HASH_DB', root / 'not-a-dir' / 'sha256.sqlite3'), \
                    patch.object(jobmod, '_persistent_digest', return_value=None):
                jobmod._DIGEST_CACHE.clear()
                self.assertEqual(jobmod.digest(media), jobmod.hashlib.sha256(b'evidence').hexdigest())
                jobmod._DIGEST_CACHE.clear()


class JobTests(unittest.TestCase):
    def setUp(self):
        f = fixtures.AssemblyTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        self.f = f
        self.root = f.root
        self.plan = f.plan
        self.pp = f.save('assembly_plan.json', self.plan)
        self.jp = self.root / 'job.json'
        words_pin = jobmod.pin(self.plan['source_words'])
        self.coverage = f.save('coverage.json', {'transcript': words_pin,
            'read_ranges': [[0,7]], 'interactions': [{'words': [0,7], 'kind': 'monologue',
            'speakers': ['A'], 'disposition': 'candidate', 'reason': 'Synthetic test interaction'}]})
        media = jobmod.pin(f.audio)
        mapping = f.save('mapping.json', {'schema': 'edit.source-mapping/v1',
            'source_id': 's1', 'discovery_transcript': words_pin, 'candidate_words': words_pin,
            'media': media, 'reference_audio': media, 'clock_basis': 'identical'})
        self.c = {'source_id': 's1', 'design_group': 'pilot', 'kind': 'monologue',
                  'plan': jobmod.pin(self.pp), 'source_words': words_pin,
                  'source_mapping': jobmod.pin(mapping), 'question_policy': 'not_applicable',
                  'question_reason': 'Synthetic standalone example, no question.'}
        self.snapshot = jobmod.skill_snapshot()
        # Freeze the tool surface for fixture speed, never the production CLI path.
        self.mock = patch.object(jobmod, 'skill_snapshot', return_value=self.snapshot)
        self.mock.start(); self.addCleanup(self.mock.stop)
        self.job = {'schema': 'edit.assembly-job/v1', 'job_id': 'fixture', 'builder_id': 'builder',
                    'skills': self.snapshot, 'sources': [{'id': 's1', 'media': media,
                    'transcript': words_pin, 'participants': ['A'], 'relationship': 'single camera',
                    'coverage': jobmod.pin(self.coverage), 'coverage_gaps': []}],
                    'batch': {'kind': 'calibration'}, 'candidates': {'test': self.c}}
        self.comparison()
        self.save_job()

    def save_job(self):
        self.jp.write_text(json.dumps(self.job))

    def comparison(self):
        quote = lambda ranges: ' '.join(self.f.words[i]['word'] for a,b in ranges for i in range(a,b+1))
        ranges = [s['words'] for s in self.plan['segments']]
        note = 'Synthetic fixture evidence, not a real editorial judgment or listening claim.'
        comp = {'schema': 'assembly-design.design-comparison/v1',
                'reviewed_plan': jobmod.pin(self.pp),
                'interaction': {'word_range':[0,7], 'text':quote([[0,7]])},
                'unedited_baseline': {'word_ranges':[[0,7]], 'text':quote([[0,7]])},
                'selected_assembly': {'word_ranges':ranges, 'text':quote(ranges)},
                'content_unit': {k: note for k in ('viewer','promise','reward','cold_viewer',
                                'goodwill','value_compression','audience_growth')},
                'decisions': [{'scope': s, 'word_ranges': [ranges[0]], 'why': note}
                              for s in ('opening','body','ending')],
                'single_span': len(ranges)==1, 'clean_source_justification': note,
                'alternative_review': {'meaningful_alternative':False, 'why':note}}
        for k in ('hook','retention_path','payoff'):
            comp[k] = {'word_ranges':[ranges[0]], 'quote':quote([ranges[0]]), 'why':note}
        self.f.save('design_comparison.json', comp)

    def build_evidence(self):
        self.c['compiled'] = jobmod.pin(self.f.save('compiled.json', compiler.compile_assembly(self.plan)))
        resolved = self.f.resolved()
        self.c['resolved'] = jobmod.pin(self.f.save('resolved.json', resolved))
        self.c['reconciled'] = jobmod.pin(self.f.save('reconciled.json', compiler.reconcile(self.plan, resolved)))
        self.c['reviews'] = {}
        self.save_job()
        for perspective in ('cold_viewer', 'source_fidelity'):
            packet_path = self.f.save(perspective+'-packet.json', jobmod.review_packet(self.jp,'test',perspective))
            packet_pin = jobmod.pin(packet_path)
            agent = 'fixture-'+perspective
            inv = self.f.save(perspective+'-invocation.json', {'agent_id':agent,
                'tool_call_id':'synthetic-call-'+perspective, 'packet':packet_pin, 'fresh_context':True})
            checks = jobmod.COLD if perspective=='cold_viewer' else jobmod.FIDELITY
            response = {'schema':'edit.editorial-review/v1','clip_id':'test','perspective':perspective,
                'agent_id':agent,'packet':packet_pin,'invocation':jobmod.pin(inv),'verdict':'PASS',
                'checks': {k:{'verdict':'PASS','word_ranges':[[5,7]],'quote':'Test demand first.',
                               'reason':'Synthetic fixture only.'} for k in checks}, 'fixes':[]}
            self.c['reviews'][perspective] = jobmod.pin(self.f.save(perspective+'-review.json',response))
        self.save_job()

    def edit_review(self, fn, perspective='cold_viewer'):
        path = Path(self.c['reviews'][perspective]['path'])
        data = jobmod.load(path); fn(data); path.write_text(json.dumps(data))
        self.c['reviews'][perspective] = jobmod.pin(path); self.save_job()

    def test_valid_native_packet(self):
        self.build_evidence()
        result = jobmod.native_packet(self.jp,'test')
        self.assertEqual(result['statuses']['human'],'PENDING')
        p = self.f.save('native.json',result)
        self.assertEqual(jobmod.validate_native_packet(p), result)

    def test_missing_source(self):
        self.job['sources'][0]['media']['path'] = str(self.root/'missing.mp4'); self.save_job()
        with self.assertRaisesRegex(ValueError,'missing absolute'):
            jobmod.validate_job(self.jp)

    def test_candidate_check_reuses_other_camera_identity_but_checks_selected_media(self):
        second = copy.deepcopy(self.job['sources'][0])
        second['id'] = 'unused-camera'
        second['media'] = {'path': str(self.root / 'not-present.mp4'),
                           'sha256': 'not-a-valid-digest'}
        self.job['sources'].append(second)
        self.save_job()
        with self.assertRaisesRegex(ValueError, 'missing absolute'):
            jobmod.validate_job(self.jp)
        jobmod.validate_job(self.jp, media_scope='s1')
        self.job['sources'][0]['media']['sha256'] = 'wrong'
        self.save_job()
        with self.assertRaisesRegex(ValueError, 'stale evidence'):
            jobmod.validate_job(self.jp, media_scope='s1')

    def test_v4_picture_camera_does_not_require_duplicate_transcription(self):
        self.make_v4_full(['s1', 'camera-b'])
        picture = self.f.save('camera-b.bin', {'synthetic_picture_only': True})
        self.job['sources'].append({
            'id': 'camera-b', 'role': 'picture_only', 'media': jobmod.pin(picture),
            'primary_dialogue_source_id': 's1',
            'relationship': 'Secondary picture angle for the same conversation.',
            'audio_not_transcribed_reason': 'Primary feed carries complete dialogue.'})
        self.save_job()
        jobmod.validate_job(self.jp)
        self.job['candidates']['test']['source_id'] = 'camera-b'
        self.save_job()
        with self.assertRaisesRegex(ValueError, 'candidate dialogue source'):
            jobmod.validate_job(self.jp)

    def test_coverage_gap(self):
        data = jobmod.load(self.coverage); data['read_ranges']=[[0,6]]
        self.coverage.write_text(json.dumps(data))
        self.job['sources'][0]['coverage']=jobmod.pin(self.coverage); self.save_job()
        with self.assertRaisesRegex(ValueError,'incomplete transcript'):
            jobmod.validate_job(self.jp)

    def test_interaction_gap(self):
        data=jobmod.load(self.coverage); data['interactions'][0]['words']=[0,6]
        self.coverage.write_text(json.dumps(data))
        self.job['sources'][0]['coverage']=jobmod.pin(self.coverage); self.save_job()
        with self.assertRaisesRegex(ValueError,'inventory has gaps'):
            jobmod.validate_job(self.jp)

    def test_seventh_candidate(self):
        self.job['candidates']={str(i):copy.deepcopy(self.c) for i in range(7)}; self.save_job()
        with self.assertRaisesRegex(ValueError,'limit'):
            jobmod.validate_job(self.jp)

    def test_six_requires_two_groups(self):
        self.job['candidates']={str(i):copy.deepcopy(self.c) for i in range(6)}; self.save_job()
        with self.assertRaisesRegex(ValueError,'five'):
            jobmod.validate_job(self.jp)
        self.job['candidates']['5']['design_group']='second'; self.save_job()
        jobmod.validate_job(self.jp)

    def test_unauthorized_clip(self):
        self.plan['clip_id']='seventh'; self.pp.write_text(json.dumps(self.plan))
        with self.assertRaisesRegex(ValueError,'not authorized'):
            jobmod.authorize_plan(self.jp,self.pp)

    def test_required_question_removed(self):
        self.c.update(question_policy='retain',question_words=[[4,4]]); self.save_job()
        with self.assertRaisesRegex(ValueError,'required question'):
            jobmod.authorize_plan(self.jp,self.pp)

    def test_diagnosis_cannot_downgrade(self):
        self.c['kind']='l1_diagnosis'; self.save_job()
        with self.assertRaisesRegex(ValueError,'downgraded'):
            jobmod.authorize_plan(self.jp,self.pp)

    def test_changed_skill_surface(self):
        self.job['skills']=self.snapshot[:-1]; self.save_job()
        with self.assertRaisesRegex(ValueError,'skill surface changed'):
            jobmod.validate_job(self.jp)

    def test_wrong_compiled_dialogue(self):
        self.build_evidence()
        path=Path(self.c['compiled']['path']); data=jobmod.load(path); data['assembled_text']='Different.'
        path.write_text(json.dumps(data)); self.c['compiled']=jobmod.pin(path); self.save_job()
        with self.assertRaisesRegex(ValueError,'does not belong'):
            jobmod.native_packet(self.jp,'test')

    def test_fabricated_review_range(self):
        self.build_evidence()
        self.edit_review(lambda r:r['checks']['hook'].update(word_ranges=[[999,999]]))
        with self.assertRaisesRegex(ValueError,'out-of-source'):
            jobmod.native_packet(self.jp,'test')

    def test_quote_mismatch(self):
        self.build_evidence()
        self.edit_review(lambda r:r['checks']['reward'].update(quote='Invented reward.'))
        with self.assertRaisesRegex(ValueError,'not exact'):
            jobmod.native_packet(self.jp,'test')

    def test_cold_review_cannot_cite_omitted_words(self):
        self.build_evidence()
        self.edit_review(lambda r:r['checks']['hook'].update(word_ranges=[[4,4]],quote='um'))
        with self.assertRaisesRegex(ValueError,'outside reviewed'):
            jobmod.native_packet(self.jp,'test')

    def test_builder_cannot_review(self):
        self.build_evidence(); self.edit_review(lambda r:r.update(agent_id='builder'))
        with self.assertRaisesRegex(ValueError,'independent'):
            jobmod.native_packet(self.jp,'test')

    def test_required_fixes_block(self):
        self.build_evidence()
        self.edit_review(lambda r:r.update(fixes=[{'required':True,'edit':'Restore context','evidence':'line 1'}]))
        with self.assertRaisesRegex(ValueError,'unresolved'):
            jobmod.native_packet(self.jp,'test')

    def test_two_failed_cycles_hold_candidate_without_invalidating_job(self):
        failed=self.f.save('rejected.json',{'verdict':'REVISE'})
        self.c['failed_revisions']=[jobmod.pin(failed),jobmod.pin(failed)]; self.save_job()
        jobmod.validate_job(self.jp)

    def test_third_failed_cycle_is_job_violation(self):
        failed=self.f.save('rejected.json',{'verdict':'REVISE'})
        self.c['failed_revisions']=[jobmod.pin(failed),jobmod.pin(failed),jobmod.pin(failed)]
        self.save_job()
        with self.assertRaisesRegex(ValueError,'exceeded two unsuccessful'):
            jobmod.validate_job(self.jp)

    def test_continuation_needs_real_recorded_approval(self):
        previous=self.f.save('prior-job.json',self.job)
        self.job['batch']={'kind':'continuation','previous_job':jobmod.pin(previous),
            'human_approval':jobmod.pin(self.f.save('approval.json',{'decision':'APPROVE_NEXT_BATCH'}))}
        self.save_job()
        with self.assertRaisesRegex(ValueError,'approval missing'):
            jobmod.validate_job(self.jp)

    def make_v4_full(self, source_ids=None):
        self.job['schema'] = 'edit.assembly-job/v4'
        authorized = source_ids if source_ids is not None else ['s1']
        auth = self.f.save('full-authorization.json', {
            'schema': 'edit.full-batch-authorization/v1',
            'decision': 'APPROVE_FULL_BATCH',
            'authorized_source_ids': authorized,
            'user_message': 'Mine all supplied footage without a calibration batch.',
            'message_id': None})
        self.job['batch'] = {'kind': 'full', 'authorization': jobmod.pin(auth)}
        self.save_job()

    def make_v4_design(self):
        self.make_v4_full()
        note = 'Synthetic editorial self-check with complete source interaction.'
        quote = lambda a, b: ' '.join(self.f.words[i]['word'] for i in range(a, b + 1))
        ranges = [s['words'] for s in self.plan['segments']]
        worksheet = {
            'schema': 'assembly-design.editorial-worksheet/v1',
            'source_words': {'path': self.plan['source_words'],
                             'sha256': self.plan['source_sha256']},
            'interaction_words': [0, 7], 'interaction_text': quote(0, 7),
            'source_read': note, 'question_and_revealed_problem': note,
            'branch_ledger': [{'words': [0, 7], 'disposition': 'selected', 'why': note}],
            'ranked_promises': [{'rank': 1, 'promise': note, 'why': note}],
            'selected_promise': note,
            'question_policy': {'policy': 'not_applicable', 'why': note},
            'reasoning_ladder': [{'words': ranges[0], 'why': note}],
            'payoff': {'words': ranges[-1], 'quote': quote(*ranges[-1]), 'why': note},
            'omissions': [{'words': [4, 4], 'why': note}],
            'reorder_checks': [{'words': ranges[0], 'why': note}],
            'proposed_assembly': {'word_ranges': ranges,
                                  'text': quote(5, 7) + ' ' + quote(0, 3)},
            'cold_read': note,
            'meaningful_alternative': {'exists': False, 'why': note}}
        self.c['editorial_worksheet'] = jobmod.pin(
            self.f.save('editorial_worksheet.json', worksheet))
        self.save_job()

    def provisional_cut(self):
        return self.f.save('provisional-cut.json', {
            'schema': 'edit.provisional-cut/v2', 'clip_id': 'test',
            'media': self.job['sources'][0]['media'],
            'source_words': self.c['source_words'], 'fps': '24',
            'source_frames': [[120, 180], [0, 84]],
            'word_ranges': [[5, 7], [0, 3]],
            'arc': {'hook': [[5, 5]], 'reasoning': [[6, 7]], 'payoff': [[0, 3]]},
            'issues': [{'code': 'ACOUSTIC_EDGE', 'why': 'Synthetic FUSED seam awaiting listening.'},
                       {'code': 'FINAL_EDITORIAL', 'why': 'Final review has not run.'}],
            'review_note': 'Synthetic source-backed edit for editor review.'})

    def test_v4_provisional_packet_builds_without_final_review(self):
        self.make_v4_design()
        cut = self.provisional_cut()
        packet = jobmod.provisional_native_packet(self.jp, 'test', cut)
        self.assertEqual(packet['statuses']['editorial'], 'PENDING')
        self.assertEqual(packet['source_frames'], [[120, 180], [0, 84]])
        packet_path = self.f.save('provisional-packet.json', packet)
        self.assertEqual(jobmod.validate_provisional_packet(packet_path), packet)
        with self.assertRaises((KeyError, ValueError)):
            jobmod.validate_native_packet(packet_path)

    def test_v4_provisional_packet_rejects_uncovered_words_and_stale_revision(self):
        self.make_v4_design()
        cut = self.provisional_cut()
        data = jobmod.load(cut)
        data['source_frames'] = [[120, 145], [0, 84]]
        cut.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'not covered'):
            jobmod.provisional_native_packet(self.jp, 'test', cut)
        data['source_frames'] = [[120, 180], [0, 84]]
        cut.write_text(json.dumps(data))
        packet_path = self.f.save('provisional-packet.json',
                                  jobmod.provisional_native_packet(self.jp, 'test', cut))
        data['review_note'] = 'Changed note after packet creation.'
        cut.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'stale evidence'):
            jobmod.validate_provisional_packet(packet_path)

    def test_v4_provisional_packet_requires_explicit_word_edge_risk(self):
        self.make_v4_design()
        cut = self.provisional_cut()
        data = jobmod.load(cut)
        data['source_frames'][0][0] = 125
        data['issues'] = [issue for issue in data['issues']
                          if issue['code'] != 'ACOUSTIC_EDGE']
        cut.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'ACOUSTIC_EDGE'):
            jobmod.provisional_native_packet(self.jp, 'test', cut)
        data['issues'].append({'code': 'ACOUSTIC_EDGE',
                               'why': 'The proposed start falls inside the first word box.'})
        cut.write_text(json.dumps(data))
        packet = jobmod.provisional_native_packet(self.jp, 'test', cut)
        self.assertEqual(packet['edge_risks'][0]['word'], 'Test')

    def test_v4_provisional_xml_keeps_editable_pairs_and_review_marker(self):
        self.make_v4_design()
        packet_path = self.f.save('provisional-packet.json',
            jobmod.provisional_native_packet(self.jp, 'test', self.provisional_cut()))
        out = self.root / 'provisional.xml'
        with patch.object(review_xml, 'probe', return_value=(1920, 1080, Fraction(24), 12.0)):
            receipt = review_xml.build([packet_path], 'EDITOR_REVIEW', out)
        root = ET.parse(out)
        self.assertEqual(len(root.findall('.//video/track/clipitem')), 2)
        self.assertEqual(len(root.findall('.//audio/track/clipitem')), 2)
        self.assertEqual(len(root.findall('.//marker')), 1)
        self.assertIn('ACOUSTIC_EDGE', root.findtext('.//marker/comment'))
        self.assertEqual([i['source_frames'] for i in receipt['items']],
                         [[120, 180], [0, 84]])

    def test_v4_full_batch_allows_more_than_calibration_limit(self):
        self.job['candidates'] = {str(i): copy.deepcopy(self.c) for i in range(8)}
        for i, candidate in self.job['candidates'].items():
            candidate['design_group'] = 'one' if int(i) < 5 else 'two'
        self.make_v4_full()
        jobmod.validate_job(self.jp)

    def test_v4_full_batch_requires_authorization(self):
        self.job['schema'] = 'edit.assembly-job/v4'
        self.job['batch'] = {'kind': 'full'}
        self.save_job()
        with self.assertRaisesRegex((ValueError, TypeError), 'authorization|evidence'):
            jobmod.validate_job(self.jp)

    def test_v4_full_batch_rejects_unauthorized_source_scope(self):
        self.make_v4_full(['different-source'])
        with self.assertRaisesRegex(ValueError, 'source scope mismatch'):
            jobmod.validate_job(self.jp)

    def test_v4_full_batch_rejects_oversized_design_group(self):
        self.job['candidates'] = {str(i): copy.deepcopy(self.c) for i in range(6)}
        self.make_v4_full()
        with self.assertRaisesRegex(ValueError, 'five'):
            jobmod.validate_job(self.jp)

    def test_v4_uses_one_post_cut_combined_review(self):
        self.build_evidence()
        note = 'Synthetic source-specific editorial reasoning for the combined-review fixture.'
        ranges = [s['words'] for s in self.plan['segments']]
        quote = lambda selected: ' '.join(
            self.f.words[i]['word'] for a, b in selected for i in range(a, b + 1))
        worksheet = {
            'schema': 'assembly-design.editorial-worksheet/v1',
            'source_words': {'path': str(self.plan['source_words']),
                             'sha256': self.plan['source_sha256']},
            'interaction_words': self.plan['interaction_words'],
            'interaction_text': quote([self.plan['interaction_words']]),
            'source_read': note, 'question_and_revealed_problem': note,
            'branch_ledger': [{'words': self.plan['interaction_words'],
                               'disposition': 'selected', 'why': note}],
            'ranked_promises': [{'rank': 1, 'promise': note, 'why': note}],
            'selected_promise': note,
            'question_policy': {'policy': 'not_applicable', 'why': note},
            'reasoning_ladder': [{'words': ranges[0], 'why': note}],
            'payoff': {'words': ranges[-1], 'quote': quote([ranges[-1]]), 'why': note},
            'omissions': [{'words': [4, 4], 'why': note}],
            'reorder_checks': [{'words': ranges[0], 'why': note}],
            'proposed_assembly': {'word_ranges': ranges, 'text': quote(ranges)},
            'cold_read': note,
            'meaningful_alternative': {'exists': False, 'why': note}}
        worksheet_path = self.f.save('editorial_worksheet.json', worksheet)
        self.c['editorial_worksheet'] = jobmod.pin(worksheet_path)
        self.make_v4_full()
        packet_path = self.f.save(
            'final-editorial-packet.json',
            jobmod.review_packet(self.jp, 'test', 'final_editorial'))
        packet_pin = jobmod.pin(packet_path)
        agent = 'fixture-final-editorial'
        invocation = self.f.save('final-editorial-invocation.json', {
            'agent_id': agent, 'tool_call_id': 'synthetic-final-review',
            'packet': packet_pin, 'fresh_context': True})
        checks = jobmod.COLD | jobmod.FIDELITY
        response = {
            'schema': 'edit.editorial-review/v1', 'clip_id': 'test',
            'perspective': 'final_editorial', 'agent_id': agent,
            'packet': packet_pin, 'invocation': jobmod.pin(invocation), 'verdict': 'PASS',
            'checks': {k: {'verdict': 'PASS', 'word_ranges': [[5, 7]],
                           'quote': 'Test demand first.', 'reason': 'Synthetic fixture only.'}
                       for k in checks},
            'fixes': []}
        self.c['reviews'] = {'final_editorial': jobmod.pin(
            self.f.save('final-editorial-review.json', response))}
        self.save_job()
        validated = jobmod.validate_review(
            self.jp, 'test', 'final_editorial', self.c['reviews']['final_editorial'])
        self.assertEqual(validated['perspective'], 'final_editorial')

    def test_v3_calibration_still_requires_exactly_three(self):
        self.job['schema'] = 'edit.assembly-job/v3'
        self.save_job()
        with self.assertRaisesRegex(ValueError, 'exactly three'):
            jobmod.validate_job(self.jp)

    def test_native_packet_invalidated_by_job_change(self):
        self.build_evidence(); p=self.f.save('native.json',jobmod.native_packet(self.jp,'test'))
        self.job['builder_id']='another'; self.save_job()
        with self.assertRaisesRegex(ValueError,'stale evidence'):
            jobmod.validate_native_packet(p)

    def test_cli_requires_job(self):
        command=[sys.executable,str(Path(compiler.__file__)),'compile','--plan',str(self.pp),
                 '--out',str(self.root/'not-created.json')]
        result=subprocess.run(command,capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('--job',result.stderr)

    def test_alias_cannot_bypass_candidate_requirements(self):
        self.build_evidence()
        self.job['candidates']['alias'] = copy.deepcopy(self.c)
        self.job['candidates']['alias']['question_policy']='retain'
        self.job['candidates']['alias']['question_words']=[[4,4]]
        self.save_job()
        with self.assertRaisesRegex(ValueError,'plan clip_id'):
            jobmod.verified_compile(self.jp,'alias')

    def test_review_execution_reuse_blocks(self):
        self.build_evidence()
        review_path=Path(self.c['reviews']['source_fidelity']['path'])
        review=jobmod.load(review_path)
        invocation_path=Path(review['invocation']['path'])
        invocation=jobmod.load(invocation_path)
        invocation['tool_call_id']='synthetic-call-cold_viewer'
        invocation_path.write_text(json.dumps(invocation))
        review['invocation']=jobmod.pin(invocation_path)
        review_path.write_text(json.dumps(review))
        self.c['reviews']['source_fidelity']=jobmod.pin(review_path); self.save_job()
        with self.assertRaisesRegex(ValueError,'reused one execution'):
            jobmod.native_packet(self.jp,'test')

    def test_native_adapter_rejects_changed_frame_rate(self):
        self.build_evidence()
        packet_path=self.f.save('native.json',jobmod.native_packet(self.jp,'test'))
        adapter=jobmod.SKILLS/'live-clip/scripts/live_review_xml.py'
        fake=types.ModuleType('live_common')
        fake.video_props=lambda p: {'fps':25.0,'width':1920,'height':1080}
        fake.ffprobe_duration=lambda p: 12.0
        out=self.root/'review.xml'
        argv=[str(adapter),'--media',str(self.f.audio),'--name','01_CUTS','--out',str(out),
              '--assembly-packets',json.dumps([str(packet_path)])]
        with patch.dict(sys.modules,{'live_common':fake}), patch.object(sys,'argv',argv):
            with self.assertRaises(SystemExit) as exc:
                runpy.run_path(str(adapter),run_name='__main__')
        self.assertEqual(exc.exception.code,2)
        self.assertFalse(out.exists())

    def test_native_adapter_preserves_resolved_frames(self):
        import xml.etree.ElementTree as ET
        self.build_evidence()
        packet_path=self.f.save('native.json',jobmod.native_packet(self.jp,'test'))
        adapter=jobmod.SKILLS/'live-clip/scripts/live_review_xml.py'
        fake=types.ModuleType('live_common')
        fake.video_props=lambda p: {'fps':24.0,'width':1920,'height':1080}
        fake.ffprobe_duration=lambda p: 12.0
        out=self.root/'review.xml'
        argv=[str(adapter),'--media',str(self.f.audio),'--name','01_CUTS','--out',str(out),
              '--assembly-packets',json.dumps([str(packet_path)])]
        with patch.dict(sys.modules,{'live_common':fake}), patch.object(sys,'argv',argv):
            runpy.run_path(str(adapter),run_name='__main__')
        items=ET.parse(out).findall('.//video/track/clipitem')
        self.assertEqual([(int(i.findtext('in')),int(i.findtext('out'))) for i in items],
                         [(120,180),(0,84)])

    def test_job_aware_compile_cli(self):
        out=self.root/'cli-compiled.json'
        result=subprocess.run([sys.executable,str(Path(compiler.__file__)),'compile',
            '--job',str(self.jp),'--plan',str(self.pp),'--out',str(out)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(jobmod.load(out),compiler.compile_assembly(self.plan))

    def test_final_gate_cli_does_not_grant_human_approval(self):
        self.build_evidence()
        script=jobmod.SKILLS/'assembly-design/scripts/final_editorial_gate.py'
        out=self.root/'final-gate.json'
        result=subprocess.run([sys.executable,str(script),'--job',str(self.jp),'--out',str(out)],
                              capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        receipt=jobmod.load(out)
        self.assertEqual(receipt['status'],'EVIDENCE_VALID')
        self.assertEqual(receipt['clips'][0]['statuses']['human'],'PENDING')


if __name__=='__main__':
    unittest.main()


class MeasuredMulticamAdapterTests(unittest.TestCase):
    """Guard regressions; real Premiere import, picture and listening remain separate."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.master = self.root / 'master.mov'
        self.guest = self.root / 'guest.mov'
        self.master.write_bytes(b'master-test-media')
        self.guest.write_bytes(b'guest-test-media')
        self.sync = self.root / 'sync.json'
        self.sync.write_text(json.dumps({'schema':'edit.source-sync-index/v1',
            'master':str(self.master),'fps':'24',
            'acceptance':{'maximum_fit_residual_s':1/24,'minimum_peak_ratio':1.05},
            'children':[{'child':str(self.guest),
            'duration_s':10.0,'verdict':'PASS',
            'fit_max_residual_s':0.0,
            'anchors':[{'child_anchor_s':1,'master_anchor_s':11,'confidence_peak_ratio':2},
                       {'child_anchor_s':5,'master_anchor_s':15,'confidence_peak_ratio':2},
                       {'child_anchor_s':9,'master_anchor_s':19,'confidence_peak_ratio':2}],
            'mapping':{'master_time_s':'intercept_s + child_time_s * (1 + drift_s_per_s)',
                       'intercept_s':10.0,'drift_s_per_s':0.0}}]}))
        self.packet_path = self.root / 'native.json'
        self.mapping_path = self.root / 'mapping.json'
        self.mapping_path.write_text(json.dumps({'media':jobmod.pin(self.master),
            'clock_basis':'measured','sync_evidence':jobmod.pin(self.sync)}))
        self.packet = {'schema':'edit.native-build-packet/v1','clip_id':'L1_TEST',
            'fps':'24','source_spans':[[10.0,14.0]],
            'source_mapping':jobmod.pin(self.mapping_path)}
        self.packet_path.write_text(json.dumps(self.packet))
        self.evidence = self.root / 'picture-reviewed.txt'
        self.evidence.write_text('Synthetic visual fixture only.')
        def panel(source, side):
            return {'source':source,'side':side,'framing':{'scale':100,
                'position':[.25 if side=='left' else .75 if side=='right' else .5,.5],
                'crop':{'left':25 if side!='full' else 0,
                        'right':25 if side!='full' else 0,'top':0,'bottom':0}}}
        self.plan = {'schema':'edit.native-measured-multicam-plan/v1',
            'native_packet':jobmod.pin(self.packet_path),'sync_index':jobmod.pin(self.sync),
            'guest_media':jobmod.pin(self.guest),'sequence_name':'L1_TEST_REVIEW',
            'audio':[{'timeline_frames':[0,96],'source':'guest','speaker':'guest',
                      'why':'Synthetic guest speech fixture'}],
            'picture':[{'id':'Q','timeline_frames':[0,36],'layout':'single',
                        'panels':[panel('guest','full')], 'why':'Question picture fixture',
                        'evidence':jobmod.pin(self.evidence)},
                       {'id':'EXCHANGE','timeline_frames':[36,96],'layout':'split',
                        'panels':[panel('guest','left'),panel('master','right')],
                        'why':'Two-person picture fixture','evidence':jobmod.pin(self.evidence)}]}
        self.plan_path = self.root / 'picture.json'
        self.patchers = [patch.object(multicam,'validate_native_packet',return_value=self.packet),
            patch.object(multicam,'video_props',return_value={'fps':24.0,'width':1920,'height':1080}),
            patch.object(multicam,'ffprobe_duration',side_effect=lambda p:20.0 if Path(p).name=='master.mov' else 10.0)]
        for p in self.patchers:
            p.start(); self.addCleanup(p.stop)

    def run_adapter(self):
        self.plan_path.write_text(json.dumps(self.plan))
        out = self.root / 'review.xml'
        result = multicam.build(self.plan_path,out)
        return result,ET.parse(out)

    def test_nonzero_offset_and_independent_picture_timing(self):
        receipt, tree = self.run_adapter()
        self.assertEqual(receipt['audio_items'],1)
        self.assertEqual(receipt['picture_items'],3)
        audio = tree.findall('.//audio/track/clipitem')
        self.assertEqual(len(audio),1)
        self.assertEqual((audio[0].findtext('in'),audio[0].findtext('out')),('0','96'))
        video = tree.findall('.//video/track/clipitem')
        self.assertEqual(sorted({v.findtext('start') for v in video}),['0','36'])
        self.assertEqual(len({v.findtext('name') for v in video}),3)

    def test_mapping_direction_rejected(self):
        sync = json.loads(self.sync.read_text())
        sync['master'] = str(self.guest)
        self.sync.write_text(json.dumps(sync))
        self.plan['sync_index'] = jobmod.pin(self.sync)
        mapping = json.loads(self.mapping_path.read_text())
        mapping['sync_evidence'] = jobmod.pin(self.sync)
        self.mapping_path.write_text(json.dumps(mapping))
        self.packet['source_mapping'] = jobmod.pin(self.mapping_path)
        self.packet_path.write_text(json.dumps(self.packet))
        self.plan['native_packet'] = jobmod.pin(self.packet_path)
        self.plan_path.write_text(json.dumps(self.plan))
        with self.assertRaisesRegex(ValueError,'direction/master'):
            multicam.build(self.plan_path,self.root/'review.xml')

    def test_frame_rounding_and_no_duplicate_audio(self):
        self.packet['source_spans'] = [[10.02,14.02]]
        self.packet_path.write_text(json.dumps(self.packet))
        self.plan['native_packet'] = jobmod.pin(self.packet_path)
        receipt, tree = self.run_adapter()
        self.assertEqual(receipt['timeline_frames'],96)
        self.assertEqual(tree.find('.//audio/track/clipitem/in').text,'0')
        self.assertEqual(len(tree.findall('.//audio/track')),1)
        self.assertEqual(len(tree.findall('.//audio/track/clipitem')),1)

    def test_overlapping_audio_routes_rejected(self):
        self.plan['audio'] = [
            {'timeline_frames':[0,60],'source':'guest','speaker':'guest','why':'fixture'},
            {'timeline_frames':[50,96],'source':'master','speaker':'host','why':'fixture'}]
        self.plan_path.write_text(json.dumps(self.plan))
        with self.assertRaisesRegex(ValueError,'audio intervals must tile'):
            multicam.build(self.plan_path,self.root/'review.xml')
