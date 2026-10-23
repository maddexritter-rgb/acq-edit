#!/usr/bin/env python3
"""Resolve a caption-director stream into a native Graphic manifest.

This is deliberately a style-only transform: it neither retranscribes nor
regroups cards, and it preserves text, frame timing, color and speaker fields.
It makes the director's per-word weight/italic and per-cue size decisions
explicit before ``premiere_native_cards.py`` transports them into Premiere.
"""
import argparse
import copy
import json
from pathlib import Path

WEIGHT_ALIASES={'mute':'base','soft':'base','bold':'strong','black':'payoff'}
SIZE_TIERS={100:'base',110:'emph',115:'strong',120:'peak'}

def _spec(stream,index):
    return (stream.get('words') or {}).get(str(index),{})

def _indices(card):
    indices=card.get('normalized_indices')
    if isinstance(indices,list) and len(indices)==len(card.get('words',[])):
        return indices
    nested=[w.get('normalized_index') for w in card.get('words',[])]
    if nested and all(type(i) is int for i in nested): return nested
    raise ValueError('Each native card needs one normalized style index per word')

def _weight(spec):
    weight=WEIGHT_ALIASES.get(spec.get('w'),spec.get('w','base'))
    if not isinstance(weight,str) or not weight: raise ValueError('Invalid director weight')
    return weight

def _size_percent(spec):
    value=spec.get('s',100)
    if isinstance(value,(int,float)) and not isinstance(value,bool): return int(value)
    return {'base':100,'emph':110,'strong':115,'peak':120}.get(value,100)

def _cue_size(specs):
    values=[_size_percent(s) for s in specs]
    if len(values)==1:return values[0]
    return values[0] if len(set(values))==1 and values[0]!=100 else 100

def _axis(status,reason,targets):
    return {'status':status,'reason':reason,**({'targets':targets} if targets else {})}

def _check_voice(cards,stream):
    """Fail closed when the director marked another voice the grouping never applied.

    caption_director carries represented voice ONLY as per-word `c` (it empties
    voice_spans). Colour is per card and is a grouping boundary, so it must be applied
    by resolve_cards --director-style BEFORE grouping; this style-only pass cannot
    regroup. Resolving anyway silently rendered every represented voice in the host
    colour.
    """
    missed=[]
    for card in cards:
        for i,word in zip(_indices(card),card['words']):
            c=_spec(stream,i).get('c')
            if c not in (None,'','alex','host') and card.get('speaker')=='host':
                missed.append(f"{card['id']}:{word.get('text')}")
    if missed:
        raise ValueError('Director marked represented voice on '+', '.join(missed[:8])
                         +(' ...' if len(missed)>8 else '')+' but those cards are host-coloured; '
                         're-run resolve_cards.py with --director-style so the voice is grouped and coloured')

def resolve(manifest,stream,base_font_size_px=None,allow_legacy_stream=False,allow_deterministic=False):
    provenance=stream.get('style_provenance')
    if not provenance and not allow_legacy_stream:
        raise ValueError('Director stream lacks style_provenance; regenerate it or explicitly permit a reviewed legacy stream')
    if provenance and provenance.get('mode')=='deterministic' and not allow_deterministic:
        raise ValueError('Director fell back to deterministic flat styling; resolve a real director stream before native build')
    # The base size is the canvas-scaled profile size resolve_cards recorded. Passing a
    # different one (e.g. a 2160-canvas 160 onto a 1080 manifest) doubles every card.
    nominal=manifest.get('nominal_font_size_px')
    if base_font_size_px is None:base_font_size_px=nominal
    elif nominal is not None and abs(float(base_font_size_px)-float(nominal))>1e-6:
        raise ValueError(f'--base-font-size-px {base_font_size_px:g} differs from the manifest nominal '
                         f'{nominal:g} (scaled for canvas {manifest.get("canvas_px")}); omit the flag')
    if not isinstance(base_font_size_px,(int,float)) or isinstance(base_font_size_px,bool) or base_font_size_px<=0:
        raise ValueError('A positive approved base font size is required')
    result=copy.deepcopy(manifest)
    cards=result.get('cards',[])
    if not cards: raise ValueError('Manifest has no semantic cards')
    by_semantic={c['id']:c for c in cards}
    _check_voice(cards,stream)
    for card in cards:
        specs=[_spec(stream,i) for i in _indices(card)]
        for word,spec in zip(card['words'],specs):
            word['weight']=_weight(spec)
            # `q` is quoting, NOT slant: the director's own contract says a named
            # term ("key man risk") gets q WITHOUT italic, and role-played speech
            # already arrives as q+i. ORing them slanted every quoted term and the
            # style review then logged it as an approved italic target.
            word['italic']=bool(spec.get('i'))
        pct=_cue_size(specs)
        card['size_tier']=SIZE_TIERS.get(pct,'custom')
        card['font_size_px']=round(float(base_font_size_px)*pct/100,3)
        card['base_font_size_px']=base_font_size_px
    segments=result.get('render_segments')
    if segments:
        for segment in segments:
            semantic=by_semantic.get(segment.get('semantic_card_id'))
            if semantic is None: raise ValueError('Render segment has no semantic-card style source')
            for key in ('words','size_tier','font_size_px','base_font_size_px'):
                segment[key]=copy.deepcopy(semantic[key])
    else:
        segments=cards;result['render_segments']=copy.deepcopy(cards)
    weight_targets=[];italic_targets=[];size_targets=[]
    for card in result['render_segments']:
        for i,word in enumerate(card['words']):
            if word['weight']!='base':weight_targets.append({'segment_id':card['id'],'word_index':i,'text':word['text'],'value':word['weight']})
            if word['italic']:italic_targets.append({'segment_id':card['id'],'word_index':i,'text':word['text'],'value':True})
        if card['size_tier']!='base':size_targets.append({'segment_id':card['id'],'tier':card['size_tier'],'font_size_px':card['font_size_px']})
    source='caption director stream' if provenance else 'reviewed legacy director stream'
    result['style_review']={
        'mode':'editorial','reviewed':True,'segment_ids':[c['id'] for c in result['render_segments']],
        'weight':_axis('applied' if weight_targets else 'not_applicable',source+' resolved '+('weight targets' if weight_targets else 'no weight targets'),weight_targets),
        'size':_axis('applied' if size_targets else 'not_applicable',source+' resolved '+('cue size targets' if size_targets else 'no cue size targets'),size_targets),
        'italic':_axis('applied' if italic_targets else 'not_applicable',source+' resolved '+('italic targets' if italic_targets else 'no italic targets'),italic_targets)}
    result['style_resolution']={'source':provenance or {'mode':'legacy_reviewed'},'base_font_size_px':base_font_size_px}
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--manifest',type=Path,required=True)
    ap.add_argument('--director-style',type=Path,required=True)
    ap.add_argument('--base-font-size-px',type=float,
                    help='defaults to the manifest nominal size (already scaled to its canvas)')
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--allow-legacy-stream',action='store_true')
    ap.add_argument('--allow-deterministic-style',action='store_true')
    a=ap.parse_args()
    if a.out.exists():raise FileExistsError(a.out)
    out=resolve(json.loads(a.manifest.read_text()),json.loads(a.director_style.read_text()),a.base_font_size_px,a.allow_legacy_stream,a.allow_deterministic_style)
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({'out':str(a.out),'cards':len(out['render_segments']),'style_review':out['style_review']['mode']}))

if __name__=='__main__':main()
