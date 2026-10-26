import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('caption_recovery', Path(__file__).resolve().parents[1]/'scripts/recover_premiere_caption_import.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

class RecoveryTests(unittest.TestCase):
    def fixture(self, root):
        runtime = root/'runtime'; out = root/'evidence'; out.mkdir()
        (runtime/'operations').mkdir(parents=True); (runtime/'jobs').mkdir()
        record = dict(operationId='one', status='unknown', startedAt='2026-01-01T00:00:00Z', result=dict(success=False, error='Error: IMPORTED_COMPONENT_CHAIN_MISMATCH'))
        (runtime/'operations/one.json').write_text(json.dumps(record))
        (runtime/'jobs/one.json').write_text(json.dumps(dict(jobId='one', state='settled', result=record)))
        (runtime/'writer.lock').touch()
        project = dict(project_path='/test.prproj', revision='original')
        proof = dict(schema='acq-edit/premiere-caption-import-recovery-v1', operationId='one', originalOperation=record, project=project, resolution='verified')
        path = out/'receipt.json'; path.write_text(json.dumps(proof))
        class Client:
            def inspect(self, *args): return dict(data=project)
        return runtime, path, Client(), project

    def test_terminal_verified_import_releases_only_owned_lock(self):
        with tempfile.TemporaryDirectory() as d:
            r,p,c,_=self.fixture(Path(d))
            result=m.release_verified_lock(c,p,r)
            self.assertEqual(result['nativeMutations'],0)
            self.assertFalse((r/'writer.lock').exists())
            self.assertTrue((r/'one.retired-writer.lock').exists())
            self.assertEqual(json.loads((p.parent/'original-journal.json').read_text())['status'],'unknown')

    def test_changed_native_state_retains_lock_and_original_journal(self):
        with tempfile.TemporaryDirectory() as d:
            r,p,c,project=self.fixture(Path(d)); project['revision']='intervening-user-edit'
            with self.assertRaisesRegex(ValueError,'Project or operation changed'):m.release_verified_lock(c,p,r)
            self.assertTrue((r/'writer.lock').exists())
            self.assertEqual(json.loads((r/'operations/one.json').read_text())['status'],'unknown')

    def test_running_job_retains_lock(self):
        with tempfile.TemporaryDirectory() as d:
            r,p,c,_=self.fixture(Path(d)); (r/'jobs/other.json').write_text(json.dumps(dict(jobId='other',state='running')))
            with self.assertRaisesRegex(ValueError,'still active'):m.release_verified_lock(c,p,r)
            self.assertTrue((r/'writer.lock').exists())

    def test_newer_native_operation_retains_lock(self):
        with tempfile.TemporaryDirectory() as d:
            r,p,c,_=self.fixture(Path(d)); (r/'operations/other.json').write_text(json.dumps(dict(operationId='other',startedAt='2026-01-02T00:00:00Z')))
            with self.assertRaisesRegex(ValueError,'Newer native'):m.release_verified_lock(c,p,r)
            self.assertTrue((r/'writer.lock').exists())

    def test_unknown_component_chain_rejected_without_mutating_request(self):
        request=dict(tracks=[dict(items=[dict(source_kind='graphic',component_match_names=['unknown'])])])
        with self.assertRaises(ValueError):m.expanded_structure(request)
        self.assertEqual(request['tracks'][0]['items'][0]['component_match_names'],['unknown'])

if __name__ == '__main__': unittest.main()
