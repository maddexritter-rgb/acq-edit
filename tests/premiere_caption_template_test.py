import importlib.util
from pathlib import Path
import unittest
import xml.etree.ElementTree as E
spec=importlib.util.spec_from_file_location('template',Path(__file__).resolve().parents[1]/'scripts/prepare_premiere_caption_template.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ClosureTests(unittest.TestCase):
    def test_only_reachable_graph_is_transported(self):
        root=E.fromstring('<R><VideoClipTrackItem ObjectID="1"><Ref ObjectRef="2"/></VideoClipTrackItem><Media ObjectID="2"><Title>Graphic</Title><Infinite>true</Infinite><FilePath>123</FilePath></Media><Media ObjectID="3"><FilePath>/private/footage.mov</FilePath></Media></R>')
        self.assertEqual({n.get('ObjectID') for n in m.closure(root,['1'])},{'1','2'})
    def test_external_media_refused(self):
        root=E.fromstring('<R><Media ObjectID="1"><Title>Graphic</Title><Infinite>true</Infinite><FilePath>/footage.mov</FilePath></Media></R>')
        with self.assertRaisesRegex(ValueError,'External donor media'):m.closure(root,['1'])
    def test_dangling_dependency_refused(self):
        root=E.fromstring('<R><VideoClipTrackItem ObjectID="1"><Ref ObjectRef="absent"/></VideoClipTrackItem></R>')
        with self.assertRaisesRegex(ValueError,'Dangling donor'):m.closure(root,['1'])
    def test_sequence_dependency_refused(self):
        root=E.fromstring('<R><Sequence ObjectID="1"/></R>')
        with self.assertRaisesRegex(ValueError,'unrelated timeline'):m.closure(root,['1'])
    def test_ambiguous_identity_refused(self):
        root=E.fromstring('<R><Media ObjectID="1"/><Media ObjectID="1"/></R>')
        with self.assertRaisesRegex(ValueError,'Ambiguous'):m.closure(root,['1'])
if __name__=='__main__':unittest.main()
