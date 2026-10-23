import importlib.util
import io
import json
import os
import stat
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '_shared'))
import gemini_audio  # noqa: E402

spec = importlib.util.spec_from_file_location('delivery_map', ROOT / 'long-form-ingest/scripts/delivery_map.py')
dm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dm)


def words(n, step=0.5, pause_every=None):
    out, t = [], 0.0
    for i in range(n):
        if pause_every and i and i % pause_every == 0:
            t += 2.0
        out.append({'word': f'w{i}', 'start': t, 'end': t + 0.3, 'speaker': 'A'})
        t += step
    return out


class GeminiCallTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cache = Path(self.temp.name) / 'cache'
        patcher = mock.patch.object(gemini_audio, 'credential', return_value='secret-key')
        patcher.start()
        self.addCleanup(patcher.stop)

    def http_error(self, code):
        return urllib.error.HTTPError('u', code, 'busy', {}, io.BytesIO(b'{"error":"busy secret-key"}'))

    def ok_response(self, text='{"tags": []}'):
        body = {'candidates': [{'finishReason': 'STOP', 'content': {'parts': [{'text': text}]}}],
                'usageMetadata': {'promptTokenCount': 1000, 'candidatesTokenCount': 100, 'thoughtsTokenCount': 400}}
        return mock.MagicMock(__enter__=lambda s: io.BytesIO(json.dumps(body).encode()), __exit__=lambda *a: False)

    def test_busy_model_retries_once_then_continues_unavailable(self):
        waits = []
        with mock.patch('urllib.request.urlopen', side_effect=[self.http_error(503), self.http_error(503)]) as op:
            r = gemini_audio.call(b'audio', 'p', cache_dir=self.cache, budget=gemini_audio.Budget(), wait=waits.append)
        self.assertEqual(r['status'], 'UNAVAILABLE')
        self.assertEqual(op.call_count, 2)
        self.assertEqual(waits, [gemini_audio.RETRY_WAIT_S])
        self.assertNotIn('secret-key', r['detail'])

    def test_billing_errors_are_not_retried(self):
        with mock.patch('urllib.request.urlopen', side_effect=[self.http_error(402)]) as op:
            r = gemini_audio.call(b'audio', 'p', cache_dir=self.cache, budget=gemini_audio.Budget(), wait=lambda s: None)
        self.assertEqual((r['status'], op.call_count), ('UNAVAILABLE', 1))

    def test_success_is_cached_and_never_paid_twice(self):
        budget = gemini_audio.Budget()
        with mock.patch('urllib.request.urlopen', return_value=self.ok_response()) as op:
            first = gemini_audio.call(b'audio', 'p', cache_dir=self.cache, budget=budget)
            second = gemini_audio.call(b'audio', 'p', cache_dir=self.cache, budget=budget)
        self.assertEqual((first['status'], second['status'], op.call_count), ('OK', 'CACHED', 1))
        pin, pout = gemini_audio.PRICES[gemini_audio.DEFAULT_MODEL]
        self.assertAlmostEqual(first['usd'], (1000 * pin + 500 * pout) / 1e6)
        self.assertEqual(second['usd'], 0.0)

    def test_chain_moves_on_only_when_a_model_is_busy(self):
        busy = {'status': 'UNAVAILABLE', 'http_status': 503, 'detail': 'busy'}
        ok = {'status': 'OK', 'result': {'tags': []}, 'usd': 0.01}
        seen = []

        def fake(audio, prompt, model, **kw):
            seen.append(model)
            return busy if model == 'm1' else ok
        with mock.patch.object(gemini_audio, 'call', side_effect=fake):
            r = gemini_audio.call_chain(b'a', 'p', models=('m1', 'm2', 'm3'), cache_dir=self.cache, budget=gemini_audio.Budget())
        self.assertEqual((r['status'], r['model'], seen), ('OK', 'm2', ['m1', 'm2']))

    def test_chain_does_not_shop_for_a_second_opinion_or_bypass_budget(self):
        with mock.patch.object(gemini_audio, 'call', return_value={'status': 'OK', 'result': {}, 'usd': 0}) as c:
            gemini_audio.call_chain(b'a', 'p', models=('m1', 'm2'), cache_dir=self.cache, budget=gemini_audio.Budget())
        self.assertEqual(c.call_count, 1)
        with mock.patch.object(gemini_audio, 'call', return_value={'status': 'UNAVAILABLE', 'detail': 'budget cap reached'}) as c:
            r = gemini_audio.call_chain(b'a', 'p', models=('m1', 'm2'), cache_dir=self.cache, budget=gemini_audio.Budget())
        self.assertEqual((r['status'], c.call_count), ('UNAVAILABLE', 1))

    def test_budget_cap_stops_new_calls(self):
        budget = gemini_audio.Budget(max_usd=10, max_calls=1)
        with mock.patch('urllib.request.urlopen', return_value=self.ok_response()):
            gemini_audio.call(b'a1', 'p', cache_dir=self.cache, budget=budget)
            r = gemini_audio.call(b'a2', 'p', cache_dir=self.cache, budget=budget)
        self.assertEqual(r['status'], 'UNAVAILABLE')
        self.assertIn('budget', r['detail'])


class TiebreakTest(unittest.TestCase):
    WORDS = [{'word': w, 'start': i * 0.4, 'end': i * 0.4 + 0.3} for i, w in enumerate(
        'pull forward all your cash flow to our customers awesome okay'.split())]

    def vote(self, tag, whisper):
        return dm.tiebreak(self.WORDS, 'a.wav', tag, transcriber=lambda *a: whisper)

    def test_whisper_agreeing_with_assemblyai_overrules_gemini(self):
        v = self.vote({'word_first': 7, 'word_last': 7, 'type': 'misheard', 'heard': 'acquire'},
                      'cash flow to our customers. Awesome.')
        self.assertEqual(v['winner'], 'assemblyai')

    def test_whisper_agreeing_with_gemini_overrules_assemblyai(self):
        v = self.vote({'word_first': 7, 'word_last': 7, 'type': 'misheard', 'heard': 'acquire'},
                      'cash flow to acquire customers awesome')
        self.assertEqual(v['winner'], 'gemini')

    def test_no_verdict_when_whisper_heard_neither(self):
        v = self.vote({'word_first': 9, 'word_last': 10, 'type': 'misheard', 'heard': 'see ya'},
                      'thank you sir all right sir')
        self.assertEqual(v['winner'], 'unresolved')

    def test_fillers_and_failures_never_decide(self):
        words = [{'word': w, 'start': i, 'end': i + .5} for i, w in enumerate(['so', 'um', 'yes'])]
        v = dm.tiebreak(words, 'a', {'word_first': 1, 'word_last': 1, 'type': 'phantom_word'}, transcriber=lambda *a: 'so yes')
        self.assertEqual(v['winner'], 'unresolved')

        def broken(*a):
            raise RuntimeError('mlx missing')
        v = self.vote({'word_first': 7, 'word_last': 7, 'type': 'misheard', 'heard': 'x'}, None)
        self.assertEqual(v['winner'], 'unresolved')
        v = dm.tiebreak(self.WORDS, 'a', {'word_first': 7, 'word_last': 7, 'type': 'misheard', 'heard': 'x'}, transcriber=broken)
        self.assertIn('failed', v['reason'])

    def test_numbers_and_spellings_compare_as_spoken(self):
        self.assertEqual(dm.norm('2, 3 months'), dm.norm('two three months'))
        self.assertEqual(dm.norm("cuz it's outta"), dm.norm('because it\'s out of'))


class DeliveryMapTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.words = self.root / 'words.json'
        self.words.write_text(json.dumps({'words': words(300, pause_every=50)}))

    def test_chunks_cover_every_word_once_and_prefer_pauses(self):
        ws = words(300, pause_every=50)
        spans = dm.chunks(ws, 60)
        covered = [i for a, b in spans for i in range(a, b + 1)]
        self.assertEqual(covered, list(range(300)))
        self.assertTrue(all((b + 1) % 50 == 0 or b == 299 for _, b in spans))

    def test_tags_are_keyed_to_words_and_invalid_ones_dropped(self):
        def caller(audio, prompt, **kw):
            self.assertIn('0:w0', prompt)
            return {'status': 'OK', 'usd': 0.01, 'result': {'tags': [
                {'word_first': 3, 'word_last': 4, 'type': 'stumble_restart', 'confidence': 'high', 'note': 'restart'},
                {'word_first': 9999, 'word_last': 9999, 'type': 'phantom_word', 'confidence': 'high'},
                {'word_first': 5, 'word_last': 5, 'type': 'made_up_type', 'confidence': 'high'}]}}
        doc = dm.build(self.words, self.root / 'a.wav', self.root / 'map.json', self.root / 'c',
                       chunk_s=10_000, caller=caller, encoder=lambda *a: b'mp3')
        self.assertEqual([(t['word_first'], t['type']) for t in doc['tags']], [(3, 'stumble_restart')])
        self.assertEqual(doc['chunks'][0]['invalid_tags_dropped'], 2)
        self.assertEqual(doc['coverage']['status'], 'COMPLETE')

    def test_unavailable_gemini_still_writes_a_usable_map(self):
        doc = dm.build(self.words, self.root / 'a.wav', self.root / 'map.json', self.root / 'c', chunk_s=60,
                       caller=lambda *a, **k: {'status': 'UNAVAILABLE', 'detail': 'HTTP 503'},
                       encoder=lambda *a: b'mp3')
        self.assertEqual(doc['coverage']['status'], 'UNAVAILABLE')
        self.assertEqual(doc['tags'], [])
        self.assertTrue((self.root / 'map.json').exists())
        with self.assertRaises(FileExistsError):
            dm.build(self.words, self.root / 'a.wav', self.root / 'map.json', self.root / 'c', chunk_s=60,
                     caller=lambda *a, **k: {'status': 'UNAVAILABLE'}, encoder=lambda *a: b'mp3')


if __name__ == '__main__':
    unittest.main()
