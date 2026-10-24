"""Ensure the live recut checker rejects plausible but incorrect revisions."""
import copy
import importlib.util
import unittest
from pathlib import Path
module=importlib.util.spec_from_file_location('recut_agent_fixture',Path(__file__).resolve().parents[1]/'scripts/recut_agent_fixture.py')
fixture=importlib.util.module_from_spec(module);module.loader.exec_module(fixture)


class RecutAgentFixtureTests(unittest.TestCase):
    def plans(self):
        old={'editorial':{'sha256':'old','selectionPath':'old.json','reviewed':True},'cuts':[{'id':'cut-0','recordFrame':0,'sourceInFrame':0},{'id':'cut-1','recordFrame':25,'sourceInFrame':50}],
             'captions':[{'text':'NATIVE AGENT LOOP','startFrame':0,'endFrame':50,'style':{'font':'Arial'}}],
             'framing':{'receiptPath':'old-framing','receiptSha256':'old-framing-hash','shots':{'cut-0':{'x':80},'cut-1':{'x':80}}},
             'audio':{'music':[{'sourceId':'music','sourceInSample':0,'samples':96000,'startFrame':0,'gainDb':-12,'receiptPath':'old-music','receiptSha256':'old-music-hash'}]},
             'graphics':[{'path':'graphic.mov','sha256':'asset-hash','startFrame':25,'frames':25}]}
        new=copy.deepcopy(old);new['editorial'].update(sha256='new',selectionPath='new.json');new['cuts']=[{**old['cuts'][1],'recordFrame':0}]
        new['captions'][0].update(text='RETAINED SECOND PASSAGE',endFrame=25)
        new['framing'].update(receiptPath='new-framing',receiptSha256='new-framing-hash',shots={'cut-1':{'x':80}})
        new['audio']['music'][0].update(sourceInSample=48000,samples=48000,receiptPath='new-music',receiptSha256='new-music-hash')
        new['graphics'][0]['startFrame']=0
        return old,new

    def test_accepts_only_requested_passage_and_retimed_dependents(self):
        old,new=self.plans();fixture.expected_revision(old,new)
        for kind in ['source','music','graphic','caption','framing','asset','gain']:
            changed=copy.deepcopy(new)
            if kind=='source':changed['cuts'][0]['sourceInFrame']=0
            elif kind=='music':changed['audio']['music'][0]['sourceInSample']=0
            elif kind=='graphic':changed['graphics'][0]['startFrame']=25
            elif kind=='caption':changed['captions'][0]['endFrame']=50
            elif kind=='framing':changed['framing']['shots']['cut-1']['x']=90
            elif kind=='asset':changed['graphics'][0]['sha256']='different-asset'
            else:changed['audio']['music'][0]['gainDb']=-6
            with self.subTest(kind=kind),self.assertRaises(RuntimeError):fixture.expected_revision(old,changed)

    def test_refuses_stale_owner_receipts(self):
        old,new=self.plans()
        for kind in ['editorial','framing','music']:
            changed=copy.deepcopy(new)
            if kind=='music':changed['audio']['music'][0]['receiptSha256']=old['audio']['music'][0]['receiptSha256']
            else:
                field='sha256' if kind=='editorial' else 'receiptSha256';changed[kind][field]=old[kind][field]
            with self.subTest(kind=kind),self.assertRaises(RuntimeError):fixture.expected_revision(old,changed)


if __name__=='__main__':unittest.main()
