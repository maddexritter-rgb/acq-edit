#!/usr/bin/env python3
"""Report source-word and beat regressions between two compiled assemblies.

This is a mechanical review gate, not a judgment that either edit is good.
"""

import argparse
import hashlib
import json
from pathlib import Path


def indices(clip):
    return {i for span in clip["spans"] for i in range(span["word_range"][0], span["word_range"][1] + 1)}


def grouped(numbers):
    values = sorted(numbers)
    if not values:
        return []
    result = []
    start = end = values[0]
    for value in values[1:]:
        if value == end + 1:
            end = value
        else:
            result.append([start, end])
            start = end = value
    result.append([start, end])
    return result


def timing_change(old, new, patch_path):
    """Allow only the exact, explicit timing patch on unchanged word identities."""
    from validate_alignment_patch import validate
    patch_bytes = patch_path.read_bytes()
    patch = json.loads(patch_bytes)
    check = validate(patch)
    if check['issues']:
        raise ValueError('timing patch has unresolved geometry or identity conflicts')
    maps = []
    for clip in (old, new):
        raw = Path(clip['source_words']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != clip['source_words_sha256']:
            raise ValueError('source word file no longer matches compiled hash')
        maps.append(json.loads(raw))
    before, after = maps
    if {k:v for k,v in before.items() if k not in ('words','local_timing_correction')} != {k:v for k,v in after.items() if k not in ('words','local_timing_correction')}:
        raise ValueError('source metadata changed outside timing correction')
    if old['media'] != new['media'] or len(before['words']) != len(after['words']):
        raise ValueError('timing correction cannot change media or word count')
    declared = {p['word_index']:p for p in patch['patch']}
    neighbors = {p['word_index']:p for p in patch['words']}
    changed = []
    for i, (a, b) in enumerate(zip(before['words'], after['words'])):
        idx = a.get('word_index', i)
        if {k:v for k,v in a.items() if k not in ('start','end')} != {k:v for k,v in b.items() if k not in ('start','end')}:
            raise ValueError('timing correction changed word identity or metadata')
        if idx in neighbors:
            n = neighbors[idx]
            if (n['text'],n['start'],n['end'],n.get('speaker')) != (a.get('word',a.get('text')),a['start'],a['end'],a.get('speaker')):
                raise ValueError('patch neighbors do not match the original source')
        if (a['start'],a['end']) != (b['start'],b['end']):
            p = declared.get(idx)
            if not p or (p['start'],p['end']) != (b['start'],b['end']):
                raise ValueError('undeclared or mismatched timing change')
            changed.append(idx)
    if set(changed) != set(declared):
        raise ValueError('patch does not exactly describe changed word timings')
    return {'path':str(patch_path),'sha256':hashlib.sha256(patch_bytes).hexdigest(),
            'word_indices':changed,'status':'EXACT_TIMING_CHANGE_NOT_ACOUSTIC_PROOF'}


def compare(before_path, after_path, timing_patch=None):
    before = json.loads(before_path.read_text())
    after = json.loads(after_path.read_text())
    if before.get("schema") != "edit.compiled-assembly/v1" or after.get("schema") != "edit.compiled-assembly/v1":
        raise ValueError("both inputs must be compiled assemblies")
    first = {clip["id"]: clip for clip in before["clips"]}
    second = {clip["id"]: clip for clip in after["clips"]}
    if set(first) != set(second):
        raise ValueError("clip IDs differ; compare matching revisions only")
    report = {"schema": "edit.assembly-revision-diff/v1", "before": str(before_path),
              "after": str(after_path), "clips": []}
    for clip_id in first:
        old, new = first[clip_id], second[clip_id]
        correction = None
        if old["source_words_sha256"] != new["source_words_sha256"]:
            if timing_patch is None:
                raise ValueError(f"{clip_id}: source transcript changed; a timing-only correction requires --timing-patch")
            correction = timing_change(old, new, Path(timing_patch))
        old_words, new_words = indices(old), indices(new)
        old_hook, new_hook = old["beats"]["hook"], new["beats"]["hook"]
        old_payoff, new_payoff = old["beats"]["payoff"], new["beats"]["payoff"]
        checks = {
            "source_timing_changed": correction is not None,
            "opening_changed": old["spans"][0]["word_range"][0] != new["spans"][0]["word_range"][0],
            "hook_changed": old_hook["word_range"] != new_hook["word_range"],
            "old_hook_words_removed": not set(range(old_hook["word_range"][0], old_hook["word_range"][1] + 1)).issubset(new_words),
            "payoff_changed": old_payoff["word_range"] != new_payoff["word_range"],
            "old_payoff_words_removed": not set(range(old_payoff["word_range"][0], old_payoff["word_range"][1] + 1)).issubset(new_words),
            "same_design_path_changed_in_place": before["design_path"] == after["design_path"] and before["design_sha256"] != after["design_sha256"],
            "selected_words_removed": bool(old_words - new_words)
        }
        report["clips"].append({
            "clip_id": clip_id,
            "review_required": any(checks.values()),
            "checks": checks,
            "timing_correction": correction,
            "old_hook": old_hook,
            "new_hook": new_hook,
            "old_payoff": old_payoff,
            "new_payoff": new_payoff,
            "removed_word_ranges": grouped(old_words - new_words),
            "added_word_ranges": grouped(new_words - old_words)
        })
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    parser.add_argument("--out", type=Path, help="write an immutable JSON receipt")
    parser.add_argument("--timing-patch", type=Path, help="Explicit validated local timing-only correction; words and media must remain identical")
    args = parser.parse_args()
    result = compare(args.before, args.after, args.timing_patch)
    rendered = json.dumps(result, indent=2) + "\n"
    if args.out:
        if args.out.exists():
            parser.error("output exists; use a new revision path")
        args.out.write_text(rendered)
    print(rendered, end="")
    if any(row["review_required"] for row in result["clips"]):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
