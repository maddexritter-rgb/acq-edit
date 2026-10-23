import json
import tempfile
import unittest
from pathlib import Path

from campaign import inventory, record, load, new_json, digest


class CampaignTests(unittest.TestCase):
    def setup_root(self,root):
        new_json(root/'state.json',{'report_every_completed_cases':10})
        new_json(root/'campaign.json',{'campaign_id':'test','project_ref':'test-ref'})
        (root/'evidence.txt').write_text('Evidence with a concrete disposition')
        return {'case_id':'one','status':'no_new_finding','summary':'Existing lesson already covers this choice',
                'disposition_reason':'Duplicate support, no new rule','next_action':'Next case',
                'artifacts':[{'uri':str(root/'evidence.txt')}]}

    def test_repeated_checkpoint_does_not_double_count_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);entry=self.setup_root(root)
            record(root,entry);state=record(root,entry)
            self.assertEqual(state['completed_studies'],1)
            self.assertEqual(state['checkpoint_count'],2)

    def test_published_without_readback_cannot_count_as_ingested(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);entry=self.setup_root(root);entry['status']='retrieved'
            with self.assertRaises(ValueError): record(root,entry)
            self.assertFalse((root/'events.jsonl').exists())

    def test_changed_checkpoint_evidence_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);entry=self.setup_root(root);entry['artifacts'][0]['sha256']='0'*64
            with self.assertRaises(ValueError): record(root,entry)

    def test_inventory_does_not_turn_project_name_into_final(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'FINAL #001.prproj').write_bytes(b'project')
            (root/'copy.prproj').write_bytes(b'project')
            result=inventory({'project_root':str(root),'evidence_root':str(root),'campaign_id':'test'})
            self.assertEqual(result['project_file_count'],2)
            self.assertEqual(result['unique_project_hashes'],1)
            self.assertIsNone(result['distinct_final_count'])
            self.assertTrue(all(p['inspection_status']=='UNINSPECTED' for p in result['projects']))


if __name__ == '__main__': unittest.main()
