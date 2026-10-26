"""Regression gates for crowded body cards and accidental native wrapping."""
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'distribution/skills/caption-clips/scripts'))
from caption_lint import validate_card_layout
from filmcraft_caption_contract import prepare_cards
from resolve_cards import group

class CaptionDensityTests(unittest.TestCase):
    def test_reported_six_word_card_rejected(self):
        for text in ['like what are the true things','and so I got to see','a b c d e f']:
            with self.assertRaisesRegex(ValueError,'words per line'):validate_card_layout(text)
    def test_characters_and_linebreaks_are_independent(self):
        for text in ['extraordinary opportunities','true\nthings','true\rthings']:
            with self.assertRaises(ValueError):validate_card_layout(text)
    def test_actual_width_rejects_under_character_limit(self):
        text='generating the most shows'
        validate_card_layout(text)
        with self.assertRaisesRegex(ValueError,'exceeds'):
            validate_card_layout(text,measure=lambda *args:850,face='ExactFace',size_px=80,width_px=780)
    def test_short_phrase_and_multiline_profile(self):
        validate_card_layout('the true things')
        validate_card_layout('a longer phrase here\nwith a second line',{'max_lines':2})
    def test_filmcraft_rejects_before_native_construction(self):
        cards=[{'text':'like what are the true things','quote':False,'start_frame':0,'speech_end':1}]
        with self.assertRaisesRegex(ValueError,'words per line'):prepare_cards(cards,{},30,60)
    def test_grouping_preserves_words_despite_overlong_editorial_group(self):
        text='like what are the true things'
        words=[{'text':w,'start':i*.2,'end':(i+1)*.2,'physical_speaker':'host','source_indices':[i]} for i,w in enumerate(text.split())]
        phrases=group(words,[],lambda s:round(s*30),.75,6,[5])
        self.assertEqual([i for g in phrases for i in g],list(range(6)))
        for g in phrases:validate_card_layout(' '.join(words[i]['text'] for i in g))

if __name__=='__main__':unittest.main()
