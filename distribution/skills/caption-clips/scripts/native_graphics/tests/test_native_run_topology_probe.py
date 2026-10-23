import base64
import os
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from native_graphics.native_run_topology_probe import rebuild_runs
from native_graphics.decode_graphic_text import decode_runs


class RunTopologyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture=os.environ.get('NATIVE_TEXT_STYLE_FIXTURE')
        if not fixture:raise unittest.SkipTest('Set NATIVE_TEXT_STYLE_FIXTURE to a licensed native text preset')
        p=Path(fixture)
        if not p.exists():raise unittest.SkipTest('User fixture absent')
        cls.payload=base64.b64decode(ET.parse(p).find('.//StartKeyframeValue').text)
    def test_one_to_six_and_back(self):
        fragments=['one ','two ','three ','four ','five ','six']
        expanded=rebuild_runs(self.payload,[(0,t) for t in fragments])
        self.assertEqual([r['text'] for r in decode_runs(expanded)],fragments)
        reduced=rebuild_runs(expanded,[(5,'single')])
        self.assertEqual([r['text'] for r in decode_runs(reduced)],['single'])
    def test_rejects_bad_donor_or_text(self):
        for request in [[(999,'text')],[(True,'text')],[(0,'')],[(0,'a\x00b')],[]]:
            with self.subTest(request=request),self.assertRaises(ValueError):rebuild_runs(self.payload,request)
    def test_input_immutable_unicode(self):
        original=bytes(self.payload)
        result=rebuild_runs(self.payload,[(0,'“café” '),(0,'😀')])
        self.assertEqual(''.join(r['text'] for r in decode_runs(result)),'“café” 😀')
        self.assertEqual(self.payload,original)
