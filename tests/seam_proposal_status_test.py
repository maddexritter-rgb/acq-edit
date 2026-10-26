import importlib.util
from pathlib import Path
import sys
import unittest
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT/'distribution/skills/assembly-design/scripts'
sys.path.insert(0,str(SCRIPTS))
import seam_windows

class SeamProposalStatusTests(unittest.TestCase):
    def test_measurement_and_override_do_not_claim_editor_inspection(self):
        words=[{'word':x,'start':float(i),'end':i+.4} for i,x in enumerate(['one','omit','two'])]
        for incoming,outgoing in [(None,None),({2:(1.8,1.9,2.0)},{0:(.4,.5,.6)})]:
            decisions,_=seam_windows.plan(words,[[0,0],[2,2]],{},np.zeros(4000),48000,'24000/1001','fixture',incoming,outgoing)
            self.assertEqual(decisions['outer_edge_evidence']['status'],'PROPOSED')
            self.assertTrue(all(j['status']=='PROPOSED' for j in decisions['joins']))
            self.assertNotIn('MFA',decisions['joins'][0]['reason'])

if __name__=='__main__':unittest.main()
