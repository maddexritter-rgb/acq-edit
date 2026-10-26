import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('recovery', Path(__file__).parents[1]/'scripts/recover_premiere_empty_selection.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RecoveryTest(unittest.TestCase):
    def fixture(self, directory):
        before = {'projectPath': '/test.prproj', 'sequenceId': 's', 'revision': 'before', 'tracks': []}
        after = {**before, 'revision': 'after', 'tracks': [{'audio': 'precise'}]}
        raw = {k: v for k, v in after.items() if k != 'revision'}
        prior = {'project_path': '/test.prproj', 'active_sequence_id': None,
                 'sequences': [{'sequence_id': 's', 'snapshot': {k: v for k, v in before.items() if k != 'revision'}}]}
        final = {**prior, 'active_sequence_id': 's', 'sequences': [{'sequence_id': 's', 'snapshot': raw}]}
        files = {'before.json': before, 'after.json': after, 'project-before.json': prior,
                 'links-after.json': {'items': ['linked']},
                 'restore-operation.json': {'operation': {'operation_id': 'restore', 'tool': 'set_active_sequence',
                    'arguments': {'sequence_id': None}, 'target': {'sequence_id': 's', 'expected_revision': 'after'}}}}
        for name in ('edges-operation.json', 'save-operation.json'):
            files[name] = {'result': {'reconciled': True, 'operation': {'status': 'committed_unverified', 'result': {'success': True}}}}
        for name, data in files.items():
            (directory/name).write_text(json.dumps(data))
        responses = {'lab_get_job': None, 'lab_get_operation': None, 'lab_snapshot': after,
                     'inspect_assembly_links': {'data': files['links-after.json']}, 'inspect_project_sequences': {'data': final}}
        class Client:
            def inspect(self, name, arguments):
                return copy.deepcopy(responses[name])
        return Client(), responses

    def test_saved_exact_state_recovers_without_any_mutation_api(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp); client, responses = self.fixture(out); calls = []
            result = module.recover(client, out, lambda *a, **k: calls.append(k))
            self.assertEqual(result['nativeMutations'], 0)
            self.assertEqual(calls[0]['after_revision'], 'after')
            self.assertTrue((out/'restore-operation.json').exists())

    def test_changed_snapshot_links_or_unrelated_sequence_are_refused(self):
        for target in ('snapshot', 'links', 'sequence'):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temp:
                out=Path(temp);client,responses=self.fixture(out)
                if target=='snapshot':responses['lab_snapshot']['revision']='user-edit'
                elif target=='links':responses['inspect_assembly_links']['data']['items']=[]
                else:responses['inspect_project_sequences']['data']['sequences'].append({'sequence_id':'other','snapshot':{}})
                with self.assertRaises(ValueError):module.recover(client,out,lambda *a,**k:self.fail('Must not write handoff'))

    def test_recorded_unknown_native_attempt_is_not_cleared(self):
        with tempfile.TemporaryDirectory() as temp:
            out=Path(temp);client,responses=self.fixture(out)
            responses['lab_get_job']={'jobId':'restore','state':'running'}
            with self.assertRaises(ValueError):module.recover(client,out,lambda *a,**k:self.fail('Must not write handoff'))


if __name__=='__main__':unittest.main()
