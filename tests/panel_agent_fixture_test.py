import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
module=importlib.util.spec_from_file_location('panel_agent_fixture',Path(__file__).resolve().parents[1]/'scripts/panel_agent_fixture.py')
fixture=importlib.util.module_from_spec(module);module.loader.exec_module(fixture)


class PanelAgentFixtureTests(unittest.TestCase):
    def prepared(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup);root=Path(folder.name)
        seed={'sources':[{'id':'a','sha256':'a-hash'}],'width':640,'height':360,'fps':{'numerator':25,'denominator':1},'cuts':[{'id':'seed','frames':25,'recordFrame':0,'sourceId':'a','sourceInFrame':0,'audioInSample':0,'audioSamples':48000}], 'captions':[{'text':'NATIVE AGENT LOOP','endFrame':50,'style':{}}]}
        (root/'seed.json').write_text(json.dumps(seed));(root/'second.json').write_text(json.dumps({'id':'b','sha256':'b-hash'}))
        return fixture.prepare(root/'seed.json',root/'second.json')

    def test_fixture_has_two_independent_panel_occurrences_and_pinned_camera_clocks(self):
        plan=self.prepared();self.assertEqual([c['sourceInFrame'] for c in plan['cuts']],[25,0,50]);self.assertEqual([c['recordFrame'] for c in plan['cuts']],[0,25,50]);self.assertEqual(sum(c['frames'] for c in plan['cuts']),75)
        first=plan['framing']['shots']['cut-0'];last=plan['framing']['shots']['cut-2']
        self.assertEqual(first['panels'][1]['sourceRange']['inFrame'],50);self.assertEqual(last['panels'][1]['sourceRange']['inFrame'],0)
        self.assertEqual(fixture.read(first['cameraReceiptPath'])['cutsSha256'],fixture.fingerprint(plan['cuts']))
        self.assertEqual(fixture.sha(first['cameraReceiptPath']),first['cameraReceiptSha256'])

    def test_live_checker_requires_exact_request_and_rejects_unrequested_edits(self):
        old=self.prepared();new=copy.deepcopy(old);new['framing'].update(receiptPath='new-framing',receiptSha256='new-hash')
        first=new['framing']['shots']['cut-0'];first.update(cameraReceiptPath='new-camera',cameraReceiptSha256='new-camera-hash');a,b=first['panels'];a['rect']['y']=320;b['rect']['y']=0;a['crop'].update(x=80.25,xByFrame=[80.25+.75*i for i in range(25)]);b['crop']['x']=60
        fixture.expected_revision(old,new)
        for kind in ['curve','caption','later-panel','source-clock','receipt']:
            changed=copy.deepcopy(new)
            if kind=='curve':changed['framing']['shots']['cut-0']['panels'][0]['crop']['xByFrame'][12]+=1
            elif kind=='caption':changed['captions'][0]['text']='changed'
            elif kind=='later-panel':changed['framing']['shots']['cut-2']['panels'][1]['crop']['x']=60
            elif kind=='source-clock':changed['cuts'][0]['sourceInFrame']+=1
            else:changed['framing']['shots']['cut-0']['cameraReceiptSha256']=old['framing']['shots']['cut-0']['cameraReceiptSha256']
            with self.subTest(kind=kind),self.assertRaises(RuntimeError):fixture.expected_revision(old,changed)


if __name__=='__main__':unittest.main()
