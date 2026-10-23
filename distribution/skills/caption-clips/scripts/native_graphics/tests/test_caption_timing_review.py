import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from native_graphics.caption_timing_review import review

class TimingReviewTests(unittest.TestCase):
    rate={'numerator':24,'denominator':1}
    def card(self,indices,start=24):return dict(id='phrase',normalized_indices=indices,start_frame=start)
    def test_early_onset(self):
        self.assertEqual(review([self.card([0])],[dict(word='felt',start=2.,end=2.2)],self.rate)[0]['kind'],'early_first_word')
    def test_intact_subject_verb(self):
        w=[dict(word='I',start=1.,end=1.1),dict(word='felt',start=1.1,end=1.3),dict(word='like',start=1.3,end=1.4)]
        self.assertEqual(review([self.card([0,1,2])],w,self.rate),[])
    def test_pause_hidden_by_group(self):
        w=[dict(word='you',start=1.,end=1.2),dict(word='refocus',start=2.5,end=3.)]
        self.assertEqual(review([self.card([0,1])],w,self.rate)[0]['kind'],'future_phrase_across_pause')
    def test_orphan_not_silently_merged(self):
        self.assertEqual(review([self.card([0])],[dict(word='I',start=1.,end=1.1)],self.rate)[0]['kind'],'function_word_orphan_review')

    def test_hesitation_punctuation_preserved(self):
        for text in ['I..','I…','“and”']:
            w=[dict(word=text,start=1.,end=1.7)]
            c=self.card([0]);c['text']=text
            result=review([c],w,self.rate)
            self.assertEqual(result[0]['kind'],'function_word_orphan_review')
            self.assertEqual(result[0]['displayed_text'],text)
            self.assertEqual(w[0]['word'],text)
