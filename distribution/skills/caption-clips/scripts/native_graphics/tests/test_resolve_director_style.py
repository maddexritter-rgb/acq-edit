import copy
import unittest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from native_graphics.resolve_director_style import resolve


class ResolveDirectorStyleTests(unittest.TestCase):
    def manifest(self):
        card={'id':'card-1','start_frame':1,'end_frame':12,'speaker':'host',
              'text':'this matters','normalized_indices':[0,1],
              'words':[{'text':'this','color':'FFFFFF'},{'text':'matters','color':'FFFFFF'}]}
        segment=copy.deepcopy(card);segment.update(id='card-1/segment-1',semantic_card_id='card-1',
                                                   animation_elapsed_frames=0)
        return {'cards':[card],'render_segments':[segment]}

    def stream(self,mode='api'):
        return {'style_provenance':{'engine':'caption_director','mode':mode},'words':{
            '0':{'w':'base'},'1':{'w':'emphasis','i':True,'s':'strong'}}}

    def test_preserves_timing_text_speaker_and_color_while_resolving_style(self):
        before=self.manifest();out=resolve(before,self.stream(),160)
        card=out['cards'][0];segment=out['render_segments'][0]
        self.assertEqual(before['cards'][0]['text'],card['text'])
        self.assertEqual(before['cards'][0]['start_frame'],card['start_frame'])
        self.assertEqual(before['cards'][0]['speaker'],card['speaker'])
        self.assertEqual(card['words'][1]['color'],'FFFFFF')
        self.assertEqual(card['words'][1]['weight'],'emphasis')
        self.assertTrue(card['words'][1]['italic'])
        self.assertEqual(card['size_tier'],'base')  # mixed multi-word sizes never create a broken word bump
        self.assertEqual(segment['words'],card['words'])
        self.assertEqual(out['style_review']['weight']['status'],'applied')
        self.assertEqual(out['style_review']['italic']['status'],'applied')

    def test_single_word_size_becomes_card_size(self):
        manifest=self.manifest();card=manifest['cards'][0];card.update(text='matters',normalized_indices=[1],words=[card['words'][1]])
        segment=manifest['render_segments'][0];segment.update(text='matters',normalized_indices=[1],words=[segment['words'][1]])
        out=resolve(manifest,self.stream(),160)
        self.assertEqual(out['cards'][0]['size_tier'],'strong')
        self.assertEqual(out['cards'][0]['font_size_px'],184.0)
        self.assertEqual(out['style_review']['size']['status'],'applied')

    def test_flat_deterministic_stream_fails_closed(self):
        with self.assertRaisesRegex(ValueError,'deterministic flat'):
            resolve(self.manifest(),self.stream('deterministic'),160)

    def test_missing_provenance_requires_explicit_legacy_review(self):
        stream=self.stream();stream.pop('style_provenance')
        with self.assertRaisesRegex(ValueError,'lacks style_provenance'):
            resolve(self.manifest(),stream,160)
        self.assertEqual(resolve(self.manifest(),stream,160,allow_legacy_stream=True)['style_resolution']['source']['mode'],'legacy_reviewed')


if __name__=='__main__':
    unittest.main()
