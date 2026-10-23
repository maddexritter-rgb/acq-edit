"""Synthetic contracts only; these tests do not certify editorial or audio quality."""
from array import array
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

SKILLS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILLS / '_shared'))
sys.path.insert(0, str(SKILLS / 'assembly-design/scripts'))
sys.path.insert(0, str(SKILLS / 'edit/scripts'))
import candidate_performance as performance
import assembly_job as job
from word_selection import validate_indexed_spec


class CandidatePerformanceTests(unittest.TestCase):
    def test_full_interaction_flags_pause_filler_and_stretched_word(self):
        words = [
            {'word': 'Well,', 'start': 0.0, 'end': 0.25},
            {'word': 'um', 'start': 0.25, 'end': 0.50},
            {'word': 'it', 'start': 0.50, 'end': 1.40},
            {'word': 'works.', 'start': 2.10, 'end': 2.40},
        ]
        samples = array('h', [1000] * (3 * 16000))
        evidence = performance.analyze(words, 0, 3, Fraction(24000, 1001),
                                       [[0.0, 1.4], [1.8, 2.4]], samples)
        ids = {event['id'] for event in evidence['events']}
        self.assertEqual(evidence['status'], 'MEASURED')
        self.assertTrue({'filler_1', 'word_2', 'gap_2_3'} <= ids)
        gap = next(event for event in evidence['events'] if event['id'] == 'gap_2_3')
        self.assertGreater(gap['speech_overlap_s'], 0)
        self.assertEqual(len(evidence['words']), 4)

    def test_clean_take_has_no_performance_flags(self):
        words = [{'word': 'Test', 'start': 0, 'end': .22},
                 {'word': 'demand', 'start': .25, 'end': .48},
                 {'word': 'first.', 'start': .50, 'end': .75}]
        result = performance.analyze(words, 0, 2, Fraction(24), [[0, .75]], array('h', [1000]*16000))
        self.assertEqual(result['events'], [])

    def test_reuses_validated_large_media_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            media = root / 'stable.mp4'; media.write_bytes(b'fixture')
            identity = root / 'media_identity.json'
            identity.write_text(json.dumps({
                'schema': 'long-form-ingest.media-identity/v1',
                'identity_status': 'SOURCE_AND_COPY_SHA256_MATCH',
                'project_copy': str(media), 'size_bytes': media.stat().st_size,
                'project_copy_sha256': hashlib.sha256(b'fixture').hexdigest()}))
            result = performance.pinned_media(media, identity)
            self.assertEqual(result['sha256'], hashlib.sha256(b'fixture').hexdigest())
            media.write_bytes(b'changed-size')
            with self.assertRaisesRegex(ValueError, 'does not match'):
                performance.pinned_media(media, identity)

    def test_butted_asr_boxes_cannot_hide_measured_pause(self):
        words = [{'word': 'We', 'start': 0.0, 'end': .5},
                 {'word': 'sell', 'start': .5, 'end': 1.0}]
        result = performance.analyze(words, 0, 1, Fraction(24),
                                     [[0.0, .2], [.8, 1.0]],
                                     array('h', [1000] * 16000))
        conflicts = [event for event in result['events'] if event['kind'] == 'vad_word_conflict']
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]['word_indices'], [0, 1])
        self.assertAlmostEqual(conflicts[0]['duration_s'], .6)
        self.assertEqual(conflicts[0]['start_frame_floor'], 4)

    def test_v2_requires_decision_for_hidden_pause_inside_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            words = [{'word': 'We', 'start': 0.0, 'end': .5},
                     {'word': 'sell', 'start': .5, 'end': 1.0}]
            source = root / 'words.json'; source.write_text(json.dumps({'words': words}))
            audio = root / 'audio.bin'; audio.write_bytes(b'synthetic-not-real-audio')
            evidence = performance.analyze(words, 0, 1, Fraction(24),
                                           [[0.0, .2], [.8, 1.0]],
                                           array('h', [1000] * 16000))
            evidence.update(schema=performance.SCHEMA, source_words=job.pin(source),
                            reference_audio=job.pin(audio))
            path = root / 'performance.json'; path.write_text(json.dumps(evidence))
            plan = {'interaction_words': [0, 1], 'segments': [{'words': [0, 1]}],
                    'performance_evidence': job.pin(path), 'performance_decisions': []}
            candidate = {'source_words': job.pin(source)}
            mapping = {'reference_audio': job.pin(audio)}
            verification = {'audio_path': str(audio), 'audio_sha256': job.digest(audio)}
            with self.assertRaisesRegex(ValueError, 'not considered'):
                job.validate_candidate_performance(plan, candidate, mapping, verification)
            plan['performance_decisions'] = [{
                'event_id': evidence['events'][0]['id'], 'action': 'keep',
                'why': 'Source listening confirms this pause is intentional.'}]
            job.validate_candidate_performance(plan, candidate, mapping, verification)

    def test_v2_requires_pinned_evidence_and_every_selected_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            words = [{'word': 'Wait', 'start': 0, 'end': .2},
                     {'word': 'here.', 'start': .8, 'end': 1.1}]
            source = root / 'words.json'; source.write_text(json.dumps({'words': words}))
            audio = root / 'audio.bin'; audio.write_bytes(b'synthetic-not-real-audio')
            evidence = performance.analyze(words, 0, 1, Fraction(24), [[0, .2], [.8, 1.1]],
                                           array('h', [1000]*32000))
            evidence.update(schema=performance.SCHEMA, source_words=job.pin(source),
                            reference_audio=job.pin(audio))
            path = root / 'performance.json'; path.write_text(json.dumps(evidence))
            plan = {'interaction_words': [0, 1], 'segments': [{'words': [0, 1]}],
                    'performance_evidence': job.pin(path), 'performance_decisions': [
                        {'event_id': 'gap_0_1', 'action': 'keep',
                         'why': 'Intentional source cadence stays in this take.'}]}
            candidate = {'source_words': job.pin(source)}
            mapping = {'reference_audio': job.pin(audio)}
            verification = {'audio_path': str(audio), 'audio_sha256': job.digest(audio)}
            job.validate_candidate_performance(plan, candidate, mapping, verification)
            plan['performance_decisions'] = []
            with self.assertRaisesRegex(ValueError, 'not considered'):
                job.validate_candidate_performance(plan, candidate, mapping, verification)
            plan['performance_decisions'] = [{'event_id': 'gap_0_1', 'action': 'remove',
                                              'why': 'Incorrectly removes an internal pause.'}]
            with self.assertRaisesRegex(ValueError, 'unsupported'):
                job.validate_candidate_performance(plan, candidate, mapping, verification)
            plan['performance_decisions'][0]['action'] = 'keep'
            source.write_text(json.dumps({'words': words + [{'word': 'Changed', 'start': 2, 'end': 2.2}]}))
            with self.assertRaisesRegex(ValueError, 'stale evidence'):
                job.validate_candidate_performance(plan, candidate, mapping, verification)

    def test_old_map_revision_requires_regeneration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            words = [{'word': 'Hello', 'start': 0, 'end': .2}]
            source = root / 'words.json'; source.write_text(json.dumps({'words': words}))
            audio = root / 'audio.bin'; audio.write_bytes(b'fixture')
            evidence = performance.analyze(words, 0, 0, Fraction(24), [[0, .2]],
                                           array('h', [1000] * 16000))
            evidence.update(schema='cut.candidate-performance/v1',
                            source_words=job.pin(source), reference_audio=job.pin(audio))
            path = root / 'old-map.json'; path.write_text(json.dumps(evidence))
            plan = {'interaction_words': [0, 0], 'segments': [{'words': [0, 0]}],
                    'performance_evidence': job.pin(path), 'performance_decisions': []}
            with self.assertRaisesRegex(ValueError, 'regenerate'):
                job.validate_candidate_performance(plan, {'source_words': job.pin(source)},
                                                   {'reference_audio': job.pin(audio)},
                                                   {'audio_path': str(audio),
                                                    'audio_sha256': job.digest(audio)})

    def test_cut_rejects_changed_performance_pin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            transcript = {'words': [{'word': 'Hello', 'start': 0, 'end': .2}]}
            raw = json.dumps(transcript).encode()
            evidence = root / 'map.json'; evidence.write_text(json.dumps({
                'schema': performance.SCHEMA, 'status': 'MEASURED',
                'source_words': {'sha256': job.hashlib.sha256(raw).hexdigest()}}))
            spec = {'source_sha256': job.hashlib.sha256(raw).hexdigest(),
                    'segments': [{'source_words': [0, 0]}],
                    'performance_evidence': job.pin(evidence), 'performance_decisions': []}
            audio = root / 'audio.bin'; audio.write_bytes(b'fixture')
            record = json.loads(evidence.read_text()); record['reference_audio'] = job.pin(audio)
            evidence.write_text(json.dumps(record)); spec['performance_evidence'] = job.pin(evidence)
            validate_indexed_spec(spec, transcript, raw, True)
            evidence.write_text('{}')
            with self.assertRaisesRegex(ValueError, 'changed'):
                validate_indexed_spec(spec, transcript, raw, True)


if __name__ == '__main__':
    unittest.main()
