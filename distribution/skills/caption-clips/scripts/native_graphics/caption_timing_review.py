"""Review signals for resolved cards. Never infer acoustic truth from ASR.

Run after evidence-backed timing correction and before cut partitioning. Caller
thresholds are review tolerances, not a learned speech model. No automatic retime.
"""
import argparse,json
from fractions import Fraction
from pathlib import Path

FUNCTION_WORDS={'i','a','an','the','and','or','but','if','to','of','in','is','it'}

def review(cards, words, frame_rate, *, lead_frames=2, pause_seconds=.65):
    fps=Fraction(frame_rate['numerator'],frame_rate['denominator'])
    findings=[]
    for card in cards:
        indices=card['normalized_indices']
        selected=[words[i] for i in indices]
        onset=float(selected[0]['start']);display=float(Fraction(card['start_frame'],1)/fps)
        if onset-display>float(Fraction(lead_frames,1)/fps):
            findings.append(dict(card_id=card['id'],kind='early_first_word',seconds=onset-display))
        for left,right in zip(selected,selected[1:]):
            gap=float(right['start'])-float(left['end'])
            if gap>=pause_seconds:
                findings.append(dict(card_id=card['id'],kind='future_phrase_across_pause',word=right['word'],seconds=gap))
        if len(selected)==1 and selected[0]['word'].strip('.,?!…“”\"').lower() in FUNCTION_WORDS:
            findings.append(dict(card_id=card['id'],kind='function_word_orphan_review',word=selected[0]['word'],
                                 displayed_text=card.get('text',selected[0]['word']),
                                 action='Review source rhythm, punctuation and cuts; never automatically merge or emphasize'))
    return findings

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--words',type=Path,required=True)
    a=p.parse_args();m=json.loads(a.manifest.read_text());w=json.loads(a.words.read_text())
    if isinstance(w,dict):w=w.get('words',[])
    rows=review(m['cards'],w,m['frame_rate'])
    print(json.dumps(dict(status='REVIEW_REQUIRED' if rows else 'RESOLVED_TIMING_CHECK_PASS_NOT_ACOUSTIC_CERTIFICATION',findings=rows),indent=2))
    raise SystemExit(bool(rows))

if __name__=='__main__':main()
