#!/usr/bin/env python3
"""Plan an approved style rotation. Does not generate copy or render media."""
import argparse
import hashlib
import json
from pathlib import Path


def allocate(library, clip_ids, previous=None, collection=None, clip_shapes=None):
    if library.get('schema') != 'hook-style-library/v1':
        raise ValueError('Unsupported style library')
    if not clip_ids or len(set(clip_ids)) != len(clip_ids):
        raise ValueError('Provide distinct clip IDs')
    if previous and previous.get('library_id') != library['library_id']:
        raise ValueError('Previous plan belongs to another library')
    all_styles = library['styles']
    if len({s['id'] for s in all_styles}) != len(all_styles):
        raise ValueError('Duplicate style IDs')
    collection = collection or library.get('default_collection')
    if previous and previous.get('collection') != collection:
        raise ValueError('Previous plan belongs to another style collection')
    styles = [s for s in all_styles if s.get('status') == 'approved' and
              (not collection or collection == 'all' or s.get('collection', 'classic') == collection)]
    if not styles:
        raise ValueError('No approved styles; obtain favorite IDs before rotation')
    for s in styles:
        if not s.get('approval_evidence'):
            raise ValueError('Approved style lacks approval evidence')
        if not Path(s['font_path']).expanduser().is_file():
            raise ValueError('Approved font unavailable: '+s['id'])
        if s['case'] not in ('preserve', 'upper'):
            raise ValueError('Unsupported case')
        if s.get('box_mode', 'fitted_lines') not in ('fitted_lines', 'unified'):
            raise ValueError('Unsupported box mode')
        for line in s.get('line_styles', []):
            if not Path(line.get('font_path', s['font_path'])).expanduser().is_file():
                raise ValueError('Approved line font unavailable: '+s['id'])
        if s.get('line_styles') and len(s['line_styles']) not in (1, 2, 3):
            raise ValueError('Style supports only one to three display-line treatments')
        if s.get('line_styles') and len(s['line_styles']) >= 2 and 1 in s.get('semantic_beats', [1, 2]):
            raise ValueError('Two-treatment style cannot accept a one-beat hook')
        if s.get('box_mode') == 'unified' and any(
            line.get('background', s.get('background')) != s.get('background')
            for line in s.get('line_styles', [])):
            raise ValueError('Unified card requires one background color')
    ids = [s['id'] for s in styles]
    last = previous['assignments'][-1]['style_id'] if previous and previous.get('assignments') else None
    start = (ids.index(last)+1) % len(ids) if last in ids else 0
    assignments = []
    usage = {id_: 0 for id_ in ids}
    cursor = start
    for clip in clip_ids:
        descriptor = (clip_shapes or {}).get(clip)
        shape = descriptor.get('shape') if isinstance(descriptor, dict) else descriptor
        beats = descriptor.get('beats') if isinstance(descriptor, dict) else None
        if beats is not None and beats not in (1, 2):
            raise ValueError(f'Invalid semantic beat count for {clip}')
        eligible = [s for s in styles if
                    (not shape or shape in s.get('copy_shapes', ['any']) or
                     'any' in s.get('copy_shapes', ['any'])) and
                    (beats in s.get('semantic_beats', [1, 2]) if beats else
                     1 in s.get('semantic_beats', [1, 2]) and len(s.get('line_styles', [])) <= 1)]
        if not eligible:
            raise ValueError(f'No compatible approved style for {clip}: {shape or "unspecified shape"}')
        s = min(eligible, key=lambda item: (usage[item['id']], (ids.index(item['id'])-cursor) % len(ids)))
        usage[s['id']] += 1
        cursor = (ids.index(s['id'])+1) % len(ids)
        # Snapshot the recipe, so edits to the library do not change a resumed batch.
        assignments.append({'clip_id': clip, 'copy_shape': shape, 'semantic_beats': beats,
                            'style_id': s['id'],
                            'style': dict(s), 'status': 'planned'})
    return {'schema': 'hook-style-plan/v1', 'library_id': library['library_id'],
            'collection': collection,
            'library_sha256': hashlib.sha256(json.dumps(library,sort_keys=True).encode()).hexdigest(),
            'approved_style_count': len(styles),
            'distinct_styles_used': len({a['style_id'] for a in assignments}),
            'repeats_required': len({a['style_id'] for a in assignments}) < len(assignments),
            'assignments': assignments}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--library',required=True);p.add_argument('--clips',required=True,help='JSON array of stable clip IDs')
    p.add_argument('--previous-plan');p.add_argument('--output',required=True)
    p.add_argument('--collection',help='Approved style collection, or all; defaults to library setting')
    p.add_argument('--shapes',help='Optional JSON map: clip ID to shape or {shape, beats}')
    a=p.parse_args(); clips=json.loads(Path(a.clips).read_text()); library=json.loads(Path(a.library).read_text());out=Path(a.output)
    if out.exists():
        plan=json.loads(out.read_text())
        shapes=json.loads(Path(a.shapes).read_text()) if a.shapes else None
        expected_collection=a.collection or library.get('default_collection')
        actual_shapes={r['clip_id']:{'shape':r.get('copy_shape'),'beats':r.get('semantic_beats')}
                       for r in plan['assignments']}
        expected_shapes={clip:((value if isinstance(value,dict) else {'shape':value}) if value is not None else {})
                         for clip,value in ((clip,(shapes or {}).get(clip)) for clip in clips)}
        if (plan.get('library_id')!=library.get('library_id') or
            plan.get('collection')!=expected_collection or
            [r['clip_id'] for r in plan['assignments']]!=clips or
            any(actual_shapes[clip]['shape']!=expected_shapes[clip].get('shape') or
                actual_shapes[clip]['beats']!=expected_shapes[clip].get('beats') for clip in clips)):
            raise ValueError('Existing plan belongs to another batch; choose a fresh output')
        print(json.dumps({'status':'resumed','output':str(out)}));return
    prior=json.loads(Path(a.previous_plan).read_text()) if a.previous_plan else None
    shapes=json.loads(Path(a.shapes).read_text()) if a.shapes else None
    plan=allocate(library,clips,prior,a.collection,shapes)
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x') as f:json.dump(plan,f,indent=2)
    print(json.dumps({'status':'planned','output':str(out),'distinct_styles':plan['distinct_styles_used'],'repeats_required':plan['repeats_required']}))

if __name__=='__main__':main()
