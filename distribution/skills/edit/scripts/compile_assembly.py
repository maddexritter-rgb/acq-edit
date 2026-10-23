#!/usr/bin/env python3
"""Compile model-selected source words into the exact spoken assembly for frame resolution."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re


FILLERS = {'um', 'uh', 'ah', 'erm', 'hmm'}
# A clip's editorial-brain reading must be fresh: one live preflight per clip,
# fetched shortly before that clip is designed. Context compaction can silently
# replace the playbook with a summary; a per-clip receipt does not depend on the
# model noticing that it happened.
BRAIN_MAX_AGE_HOURS = 6
OPENING_CONNECTIVES = {'so', 'well', 'and', 'but'}


_DIGEST_CACHE = {}


def digest(path: Path) -> str:
    # CTA assets recur across a batch. Hash actual bytes once per unchanged file;
    # inode and both nanosecond clocks invalidate replacements and edits.
    path = Path(path).resolve()
    before = path.stat()
    identity = (str(path), before.st_dev, before.st_ino, before.st_size,
                before.st_mtime_ns, before.st_ctime_ns)
    if identity not in _DIGEST_CACHE:
        hasher = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                hasher.update(block)
        after = path.stat()
        after_identity = (str(path), after.st_dev, after.st_ino, after.st_size,
                          after.st_mtime_ns, after.st_ctime_ns)
        if identity != after_identity:
            raise ValueError(f'File changed while hashing: {path}')
        _DIGEST_CACHE[identity] = hasher.hexdigest()
    return _DIGEST_CACHE[identity]


def word_text(words, pair):
    return ' '.join(str(words[i]['word']) for i in range(pair[0], pair[1] + 1)).strip()


def pair(value, label, limit):
    if (not isinstance(value, list) or len(value) != 2 or
        not all(type(n) is int for n in value) or
        not 0 <= value[0] <= value[1] < limit):
        raise ValueError(f'{label}: expected inclusive [first,last] source-word indices')
    return value


def normalized_word(value):
    return re.sub(r'[^a-z]', '', str(value).lower())


def merged_ranges(ranges):
    merged = []
    for first, last in sorted(ranges):
        if merged and first <= merged[-1][1] + 1:
            merged[-1][1] = max(last, merged[-1][1])
        else:
            merged.append([first, last])
    return merged


def normalized_text(value):
    return re.sub(r'\s+', ' ', str(value or '').strip().lower())


def template_findings(rows):
    """Mechanical signs that paper cuts were generated rather than decided.

    Authors one decision at a time write one reason per range. Batch scripts
    tend to stamp a single string over many ranges, paste the clip summary in
    as every reason, or copy rationale between clips. This catches those
    signatures only; distinct reasons are not evidence of a good cut.
    """
    findings = []
    long_reasons = {}
    intents = {}
    for row in rows:
        decisions = row.get('paper_cut')
        if not isinstance(decisions, list):
            continue
        clip_id = row.get('id', '?')
        intent = normalized_text(row.get('editorial_intent'))
        # Any long free-text design field (intent, reading notes, precedent
        # influence...) copied between clips; paths and hashes may be shared.
        for key, value in row.items():
            if (isinstance(value, str) and key not in ('source_words', 'media', 'brain_preflight')
                    and not key.endswith(('sha256', 'path')) and len(value.strip()) >= 80):
                intents.setdefault((key, normalized_text(value)), []).append(clip_id)
        by_reason = {}
        for decision in decisions:
            if not isinstance(decision, dict):
                continue
            reason = normalized_text(decision.get('reason'))
            if not reason:
                continue
            by_reason.setdefault(reason, []).append(decision)
            if intent and reason == intent:
                findings.append(f'{clip_id}: paper_cut reason at {decision.get("word_range")} '
                                'is the editorial_intent copied verbatim')
            if len(reason) >= 40:
                long_reasons.setdefault(reason, set()).add(clip_id)
        for reason, group in by_reason.items():
            # Two one- or two-word filler cuts may honestly share "filler"; a
            # shared reason on any longer range is a stamped template.
            if len(group) > 1 and any(d['word_range'][1] - d['word_range'][0] >= 2 for d in group):
                ranges = [d['word_range'] for d in group]
                findings.append(f'{clip_id}: {len(group)} paper_cut ranges {ranges} share one reason '
                                f'("{reason[:60]}"); give each range its own source-specific reason')
    for (key, _), clips in intents.items():
        if len(clips) > 1:
            findings.append(f'clips {clips} share an identical {key}')
    for reason, clips in long_reasons.items():
        if len(clips) > 1:
            findings.append(f'clips {sorted(clips)} share the reason "{reason[:60]}"')
    return findings


def brain_receipt(row, clip_id, now=None):
    """Check this clip's own live editorial-brain preflight receipt; return its path.

    Proves a fresh hash-valid fetch with required reading for this clip, not that
    the bodies were read or applied.
    """
    value = row.get('brain_preflight')
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{clip_id}: brain_preflight is required: before designing each clip, run the '
                         'find-precedents preflight for its format with a new --out path and cite it here')
    path = Path(value).resolve()
    if not path.is_file():
        raise ValueError(f'{clip_id}: brain_preflight receipt {path} does not exist')
    saved = json.loads(path.read_text())
    receipt = saved.pop('client_receipt', None)
    if not isinstance(receipt, dict) or 'response_sha256' not in receipt or 'fetched_at' not in receipt:
        raise ValueError(f'{clip_id}: brain_preflight is not a saved editorial_context.py --out receipt')
    encoded = json.dumps(saved, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    if hashlib.sha256(encoded.encode('utf-8')).hexdigest() != receipt['response_sha256']:
        raise ValueError(f'{clip_id}: brain_preflight content does not match its receipt hash')
    query = saved.get('query') or {}
    if not query.get('includeRequiredReading') or not saved.get('playbooks'):
        raise ValueError(f'{clip_id}: brain_preflight must be a --preflight fetch with playbooks and required reading')
    fetched = datetime.fromisoformat(receipt['fetched_at'])
    age = ((now or datetime.now(timezone.utc)) - fetched).total_seconds() / 3600
    if age > BRAIN_MAX_AGE_HOURS:
        raise ValueError(f'{clip_id}: brain_preflight was fetched {age:.1f} h ago; re-run the preflight and '
                         're-read it before designing this clip')
    ledger = path.with_name(path.name + '.clips')
    used = set(ledger.read_text().split()) if ledger.exists() else set()
    if used - {clip_id}:
        raise ValueError(f'{clip_id}: brain_preflight was already used to design {sorted(used - {clip_id})}; '
                         'each clip needs its own fresh preflight')
    return path


def paper_cut_selection(row, words, interaction, clip_id):
    """Validate a source-order KEEP/CUT partition and return its kept word ranges."""
    decisions = row.get('paper_cut')
    if not isinstance(decisions, list) or not decisions:
        raise ValueError(f'{clip_id}: v2 requires a complete paper_cut KEEP/CUT ledger')
    cursor = interaction[0]
    kept = []
    for index, decision in enumerate(decisions):
        if not isinstance(decision, dict):
            raise ValueError(f'{clip_id}: paper_cut decision {index} must be an object')
        first, last = pair(decision.get('word_range'), f'{clip_id} paper_cut decision {index}', len(words))
        if first != cursor or last > interaction[1]:
            raise ValueError(f'{clip_id}: paper_cut must cover the interaction exactly in source order')
        action = decision.get('action')
        if action not in ('KEEP', 'CUT'):
            raise ValueError(f'{clip_id}: paper_cut action must be KEEP or CUT')
        if action == 'CUT' and not str(decision.get('reason', '')).strip():
            raise ValueError(f'{clip_id}: CUT decision {index} needs an editorial reason')
        if action == 'KEEP':
            kept.append([first, last])
        cursor = last + 1
    if cursor != interaction[1] + 1 or not kept:
        raise ValueError(f'{clip_id}: paper_cut must cover the interaction and retain speech')

    source_order_keeps = merged_ranges(kept)
    selected = row.get('kept_word_ranges', source_order_keeps)
    if not isinstance(selected, list) or not selected:
        raise ValueError(f'{clip_id}: kept_word_ranges must be nonempty when supplied')
    selected = [pair(p, f'{clip_id} kept span', len(words)) for p in selected]
    if merged_ranges(selected) != source_order_keeps:
        raise ValueError(f'{clip_id}: playback selection does not match paper_cut KEEP words')

    first_index, last_index = selected[0][0], selected[-1][1]
    first_word = normalized_word(words[first_index]['word'])
    if first_word in FILLERS:
        raise ValueError(f'{clip_id}: opening starts on filler word {first_index} ({first_word})')
    if first_word in OPENING_CONNECTIVES and not str(row.get('opening_connective_reason', '')).strip():
        raise ValueError(f'{clip_id}: opening connective {first_word} needs a deliberate hook reason')

    filler_indices = [i for first, last in selected for i in range(first, last + 1)
                      if normalized_word(words[i]['word']) in FILLERS]
    reasons = row.get('retained_fillers', [])
    if not isinstance(reasons, list):
        raise ValueError(f'{clip_id}: retained_fillers must be a list')
    justified = {}
    for item in reasons:
        if not isinstance(item, dict) or type(item.get('word_index')) is not int or not str(item.get('reason', '')).strip():
            raise ValueError(f'{clip_id}: each retained filler needs word_index and reason')
        word_index = item['word_index']
        if word_index in justified:
            raise ValueError(f'{clip_id}: repeated retained-filler justification')
        justified[word_index] = item['reason']
    if set(justified) != set(filler_indices):
        raise ValueError(f'{clip_id}: every retained um/uh/ah/erm/hmm needs an exact-word justification')

    roles = row.get('speaker_roles')
    if not isinstance(roles, dict):
        raise ValueError(f'{clip_id}: speaker_roles are required for paper_cut')
    first_speaker = words[first_index].get('speaker')
    last_speaker = words[last_index].get('speaker')
    for speaker in (first_speaker, last_speaker):
        if not isinstance(speaker, str) or not str(roles.get(speaker, '')).strip():
            raise ValueError(f'{clip_id}: first and last selected speakers need explicit roles')
    if row.get('payoff_speaker') != last_speaker:
        raise ValueError(f'{clip_id}: payoff_speaker does not match the last selected word')
    if roles[last_speaker] == 'questioner' and not str(row.get('questioner_payoff_reason', '')).strip():
        raise ValueError(f'{clip_id}: questioner ending needs an explicit editorial payoff reason')
    return selected, {'first_word_index': first_index, 'first_speaker': first_speaker,
                      'first_role': roles[first_speaker], 'last_word_index': last_index,
                      'last_speaker': last_speaker, 'last_role': roles[last_speaker],
                      'retained_filler_indices': filler_indices,
                      'decision_count': len(decisions)}


def approved_cta(row, playback, spans, transcript, clip_id):
    """Pin an intact catalog-approved asset without inventing spoken-word indices.

    Optional on an ordinary spoken selection. The normalized media must retain
    the full asset, including silent cards; word-boundary tolerances do not apply.
    """
    spec = row.get('approved_cta')
    if spec is None:
        return None
    if not isinstance(spec, dict):
        raise ValueError(f'{clip_id}: approved_cta must be a pinned object')
    pins = {}
    for key in ('offer_plan', 'media_lineage'):
        pin = spec.get(key, {})
        file = Path(pin.get('path', '')).resolve()
        if not file.is_file() or digest(file) != pin.get('sha256'):
            raise ValueError(f'{clip_id}: stale CTA {key}')
        pins[key] = {'path': str(file), 'sha256': pin['sha256']}
    plan = json.loads(Path(pins['offer_plan']['path']).read_text())
    lineage = json.loads(Path(pins['media_lineage']['path']).read_text())
    catalog_path = Path(__file__).resolve().parents[2] / 'highlight/revenue/offers.json'
    catalog = json.loads(catalog_path.read_text())
    offer = catalog['offers'].get(plan.get('offer'))
    if (offer is None or plan.get('manifest_version') != catalog['version']
            or plan.get('cta_sha256') != offer['cta_sha256']
            or plan.get('lead_base') != offer['lead_base']
            or plan.get('workshop_base') != offer['workshop_base']
            or not str(plan.get('rationale', '')).strip()):
        raise ValueError(f'{clip_id}: CTA plan differs from current approved offer')
    original = (catalog_path.parents[1] / offer['cta']).resolve()
    if str(original) != plan.get('cta_asset') or digest(original) != offer['cta_sha256']:
        raise ValueError(f'{clip_id}: original approved CTA changed')
    if hashlib.sha256(playback.encode()).hexdigest() != plan.get('kept_transcript_sha256'):
        raise ValueError(f'{clip_id}: CTA classification belongs to different kept words')
    source = transcript.get('source_pin', {}).get('source_path', str(Path(row['media']).resolve()))
    selected_seconds = [[s['asr_start'], s['asr_end']] for s in spans]
    if plan.get('source') != source or plan.get('source_spans') != selected_seconds:
        raise ValueError(f'{clip_id}: CTA plan belongs to different source ranges')
    media = Path(lineage.get('output', '')).resolve()
    if (lineage.get('schema') != 'highlight.normalized-cta/v1'
            or lineage.get('source') != str(original)
            or lineage.get('source_sha256') != offer['cta_sha256']
            or lineage.get('full_asset_retained') is not True
            or not media.is_file() or digest(media) != lineage.get('output_sha256')):
        raise ValueError(f'{clip_id}: full CTA derivative lineage is missing or stale')
    frames = lineage.get('duration_frames')
    if type(frames) is not int or frames <= 0:
        raise ValueError(f'{clip_id}: CTA needs exact full-asset duration frames')
    return {'role': 'approved_cta', 'group_id': clip_id, 'media': str(media),
            'source_frames': [0, frames], 'fps': lineage['fps'],
            'offer': plan['offer'], 'rationale': plan['rationale'],
            'lead_base': plan['lead_base'], 'workshop_base': plan['workshop_base'],
            'original_asset': str(original), 'original_sha256': offer['cta_sha256'],
            'catalog_path': str(catalog_path), 'catalog_sha256': digest(catalog_path),
            'media_sha256': lineage['output_sha256'], **pins}


def compile_design(path: Path, check_templates: bool = True):
    """check_templates=True is first-time authoring: the template and per-clip
    brain-receipt checks apply. Replay of a compiled revision passes False."""
    design = json.loads(path.read_text())
    schema = design.get('schema')
    if schema not in ('edit.assembly-selection/v1', 'edit.assembly-selection/v2'):
        raise ValueError('expected edit.assembly-selection/v1 or v2')
    rows = design.get('clips')
    if not isinstance(rows, list) or not rows:
        raise ValueError('at least one designed clip is required')
    receipts = {}
    if check_templates and schema == 'edit.assembly-selection/v2':
        findings = template_findings(rows)
        if findings:
            raise ValueError('templated paper cut: ' + '; '.join(findings[:4]))
        for row in rows:
            clip_id = row.get('id')
            receipt = brain_receipt(row, clip_id)
            if receipt in receipts.values():
                raise ValueError(f'{clip_id}: shares a brain_preflight with another clip; each clip needs its own')
            receipts[clip_id] = receipt
    compiled = []
    seen = set()
    for row in rows:
        clip_id = row.get('id')
        if not isinstance(clip_id, str) or not clip_id.strip() or clip_id in seen:
            raise ValueError('clip ids must be unique nonempty text')
        seen.add(clip_id)
        source = Path(row['source_words']).resolve()
        media = Path(row['media']).resolve()
        if not source.is_file() or not media.is_file():
            raise ValueError(f'{clip_id}: source words and media must exist')
        transcript = json.loads(source.read_text())
        words = transcript.get('words')
        if not isinstance(words, list) or not words:
            raise ValueError(f'{clip_id}: source transcript has no indexed words')
        interaction = pair(row.get('interaction_word_range'), f'{clip_id} interaction', len(words))
        paper_cut = None
        if schema == 'edit.assembly-selection/v2':
            selected, paper_cut = paper_cut_selection(row, words, interaction, clip_id)
        else:
            selected = row.get('kept_word_ranges')
            if not isinstance(selected, list) or not selected:
                raise ValueError(f'{clip_id}: kept_word_ranges are required')
            selected = [pair(p, f'{clip_id} kept span', len(words)) for p in selected]
        for first, last in selected:
            if not interaction[0] <= first <= last <= interaction[1]:
                raise ValueError(f'{clip_id}: kept span outside complete interaction')
        for a, b in zip(selected, selected[1:]):
            if not (a[1] < b[0] or b[1] < a[0]):
                raise ValueError(f'{clip_id}: overlapping or repeated source words')
        beats = {}
        for name in ('hook', 'reasoning', 'payoff'):
            anchor = pair(row.get(f'{name}_word_range'), f'{clip_id} {name}', len(words))
            if not any(first <= anchor[0] <= anchor[1] <= last for first, last in selected):
                raise ValueError(f'{clip_id}: {name} words are not in a kept span')
            beats[name] = {'word_range': anchor, 'text': word_text(words, anchor)}
        if not selected[0][0] <= beats['hook']['word_range'][0] <= selected[0][1]:
            raise ValueError(f'{clip_id}: spoken hook must occur in first playback span')
        if not selected[-1][0] <= beats['payoff']['word_range'][1] <= selected[-1][1]:
            raise ValueError(f'{clip_id}: spoken payoff must occur in final playback span')
        if len(selected) == 1:
            reason = row.get('continuous_source_rationale')
            if not isinstance(reason, str) or not reason.strip():
                raise ValueError(f'{clip_id}: one-span selection needs continuous-source rationale')
        spans = []
        for first, last in selected:
            spans.append({'word_range': [first, last], 'text': word_text(words, [first, last]),
                          'asr_start': words[first]['start'], 'asr_end': words[last]['end']})
        playback = ' '.join(span['text'] for span in spans)
        cta = approved_cta(row, playback, spans, transcript, clip_id)
        # Put the unselected continuation next to the literal playback. This
        # exposes a later answer/correction/payoff before the model commits an
        # early ending; it is source context, not a forced extension or gate.
        tail_first = max(last for _, last in selected) + 1
        tail_last = min(interaction[1], tail_first + 499)
        tail = ({'word_range': [tail_first, tail_last],
                 'text': word_text(words, [tail_first, tail_last]),
                 'truncated': tail_last < interaction[1]}
                if tail_first <= interaction[1] else None)
        compiled.append({'id': clip_id, 'media': str(media), 'source_words': str(source),
                         'source_words_sha256': digest(source),
                         'interaction_word_range': interaction,
                         'spans': spans, 'beats': beats,
                         'playback_text': playback,
                         'omitted_source_continuation': tail,
                         'editorial_intent': row.get('editorial_intent', ''),
                         'continuous_source_rationale': row.get('continuous_source_rationale', ''),
                         **({'approved_cta': cta} if cta is not None else {}),
                         **({'paper_cut': paper_cut} if paper_cut is not None else {})})
    for clip_id, receipt in receipts.items():
        # Bind each receipt to the one clip it was fetched for (revisions of that clip may reuse it).
        receipt.with_name(receipt.name + '.clips').write_text(clip_id + '\n')
    return {'schema': 'edit.compiled-assembly/v1', 'design_path': str(path.resolve()),
            'design_sha256': digest(path), 'clips': compiled}


def validate_compiled(path: Path):
    saved = json.loads(path.read_text())
    if saved.get('schema') != 'edit.compiled-assembly/v1':
        raise ValueError('expected edit.compiled-assembly/v1')
    # Replay of an already-compiled revision is provenance, not authoring: the
    # template check applies when a design is first compiled.
    fresh = compile_design(Path(saved['design_path']), check_templates=False)
    if saved != fresh:
        raise ValueError('compiled assembly is stale or does not match source words/design')
    return saved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--design', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('output exists; use a new revision path')
    try:
        result = compile_design(args.design)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.error(str(exc))
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    for clip in result['clips']:
        print(f"\n{clip['id']} — {len(clip['spans'])} kept spans")
        if 'paper_cut' in clip:
            receipt = clip['paper_cut']
            print(f"PAPER CUT: {receipt['decision_count']} source-order decisions; "
                  f"first={receipt['first_word_index']} {receipt['first_speaker']} "
                  f"({receipt['first_role']}); last={receipt['last_word_index']} "
                  f"{receipt['last_speaker']} ({receipt['last_role']}); "
                  f"retained filler IDs={receipt['retained_filler_indices']}")
        for number, span in enumerate(clip['spans'], 1):
            print(f"[{number}: words {span['word_range'][0]}-{span['word_range'][1]}] {span['text']}")
        print('JOINED PLAYBACK:')
        print(clip['playback_text'])


if __name__ == '__main__':
    main()
