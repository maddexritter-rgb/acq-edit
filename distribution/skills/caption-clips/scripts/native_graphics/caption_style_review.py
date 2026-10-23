"""Require explicit native editorial styling; never generate arbitrary variation."""
import argparse
import json
from pathlib import Path


def validate(manifest):
    cards = manifest.get('render_segments', manifest.get('cards', []))
    review = manifest.get('style_review', {})
    if review.get('mode') == 'uniform_requested':
        if not isinstance(review.get('user_request'), str) or not review['user_request'].strip():
            raise ValueError('Uniform styling requires the explicit user request')
        return {'status': 'EXPLICIT_UNIFORM_STYLE', 'user_request': review['user_request']}
    if review.get('mode') != 'editorial' or review.get('reviewed') is not True:
        raise ValueError('Missing editorial style review: resolve weight, intentional size and italic decisions before native build')
    if not cards or len({c['id'] for c in cards}) != len(cards):
        raise ValueError('Style review requires nonempty uniquely identified render segments')
    by_id = {c['id']: c for c in cards}
    if set(review.get('segment_ids', [])) != set(by_id):
        raise ValueError('Style review does not cover the current render segments')
    for axis in ('weight', 'size', 'italic'):
        decision = review.get(axis, {})
        if not isinstance(decision.get('reason'), str) or not decision['reason'].strip():
            raise ValueError('Style review requires a clip-specific reason for '+axis)
        if decision.get('status') == 'not_applicable':
            if decision.get('targets'):
                raise ValueError('Not-applicable style axis cannot have targets')
            continue
        targets = decision.get('targets')
        if decision.get('status') != 'applied' or not isinstance(targets, list) or not targets:
            raise ValueError('Missing reviewed style targets for '+axis)
        for target in targets:
            if target.get('segment_id') not in by_id:
                raise ValueError('Stale style target segment')
            card = by_id[target['segment_id']]
            if axis == 'size':
                if not isinstance(target.get('tier'), str) or target['tier'] in ('', 'base'):
                    raise ValueError('Intentional size requires a non-base editorial tier, not width fitting')
                if card.get('size_tier') != target['tier'] or card.get('font_size_px') != target.get('font_size_px'):
                    raise ValueError('Planned size styling lost from manifest')
            else:
                i = target.get('word_index')
                if type(i) is not int or not 0 <= i < len(card.get('words', [])):
                    raise ValueError('Invalid style target word index')
                word = card['words'][i]
                if word.get('text') != target.get('text') or word.get(axis) != target.get('value'):
                    raise ValueError('Planned '+axis+' styling lost from manifest')
                if axis == 'weight' and target.get('value') in (None, '', 'base'):
                    raise ValueError('Weight emphasis target cannot be base')
                if axis == 'italic' and target.get('value') is not True:
                    raise ValueError('Italic target must actually be italic')
    return {'status': 'STYLE_PLAN_PRESENT_AND_TARGETS_MATCH_NOT_VISUAL_APPROVAL',
            'segments': len(cards), 'review': review}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(validate(json.loads(args.manifest.read_text())), indent=2))


if __name__ == '__main__':
    main()
