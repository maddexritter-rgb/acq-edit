import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from premiere_native_cards import donor_run_offset


class NativeStyleDonorTests(unittest.TestCase):
    def test_selects_mixed_italic_runs_without_flattening(self):
        donor={'runs':{'base':{'upright':2,'italic':5}},'italic':False}
        self.assertEqual(donor_run_offset(donor,{'weight':'base','italic':False}),2)
        self.assertEqual(donor_run_offset(donor,{'weight':'base','italic':True}),5)

    def test_legacy_donor_fails_for_unsupported_italic(self):
        donor={'runs':{'base':2},'italic':False}
        with self.assertRaisesRegex(ValueError,'Unsupported italic'):
            donor_run_offset(donor,{'weight':'base','italic':True})


if __name__=='__main__':
    unittest.main()
