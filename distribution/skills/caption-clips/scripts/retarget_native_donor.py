#!/usr/bin/env python3
"""Retarget native caption donors to the canvas of the sequence they will caption.

A Graphic donor stores its canvas in absolute pixels in two places that the text
layer's normalized Position does not cover:

  1. the Source Text paragraph box (document fields 2/3, every document copy);
  2. the Graphic's synthetic media frame (Media > VideoStream > FrameRect), plus
     the donor track item's own FrameRect.

A donor authored on a 2160x3840 template and cloned into 1080x1920 without this
step renders off-centre (1) and cannot be clicked to edit in the Program Monitor,
because the edit box is mapped through the 2160x3840 media frame (2).

This scales (1) and sets (2) to the target sequence canvas, keeps the donor's
normalized Position (so its authored centre is preserved exactly), then runs the
same geometry gate the builder runs. It never overwrites its input.

Usage:
  retarget_native_donor.py --project PREP.prproj --profile style_profile.json \\
      --output PREP_<W>x<H>.prproj --out-profile style_profile_<W>x<H>.json
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

from native_graphics.decode_graphic_text import document_box, scale_text_boxes
from native_graphics.native_canvas import (geometry_problems, graphic_media, media_canvas,
                                           media_consumers, sequence_canvas)
from premiere_native_cards import (load, objects, payload, pool, position_mode, text_node,
                                   text_position)


def donor_items(profile):
    donors = {**(profile.get('donors') or {}), **(profile.get('donors_by_style') or {})}
    if not donors:
        raise ValueError('Profile declares no donors')
    return {name: str(d['item_id']) for name, d in donors.items()}


def retarget(project, profile_path, output, out_profile, *, normalize_generated_aliases=False):
    output, out_profile = Path(output), Path(out_profile)
    for path in (output, out_profile):
        if path.exists():
            raise FileExistsError(path)
    project = Path(project)
    source_hash = hashlib.sha256(project.read_bytes()).hexdigest()
    profile = json.loads(Path(profile_path).read_text())
    if profile['project_sha256'] != source_hash:
        raise ValueError('Prepared project changed; refresh the profile after reviewing edits')
    root = load(project)
    shared = pool(root)
    ids = objects(root)
    canvas = sequence_canvas(root, profile['sequence_uid'])
    mode = position_mode(profile)
    report = []
    touched_media = set()
    donors = donor_items(profile)
    # Read every donor's ORIGINAL canvas before mutating anything: donors cloned from
    # one template share a single media node, so retargeting the first would make the
    # second look already-retargeted and its paragraph box would never be scaled.
    original = {item_id: media_canvas(root, ids[item_id]) for item_id in donors.values()}
    for name, item_id in donors.items():
        item = ids[item_id]
        before = original[item_id]
        node = text_node(root, item)
        data = payload(node, shared)
        box_before = document_box(data)
        row = dict(donor=name, item_id=item_id, media_before=list(before), box_before=box_before)
        if tuple(before) != tuple(canvas):
            scale_x, scale_y = canvas[0] / before[0], canvas[1] / before[1]
            if abs(scale_x - scale_y) > 1e-9:
                raise ValueError(f'Donor {item_id} canvas {before[0]}x{before[1]} and target '
                                 f'{canvas[0]}x{canvas[1]} differ in aspect; re-author the donor')
            if box_before is not None:
                scaled, count = scale_text_boxes(data, scale_x, scale_y)
                # A fresh inline payload: the donor's own node only, never a shared pool entry.
                node.set('Encoding', 'base64')
                node.set('BinaryHash', str(uuid.uuid4()))
                node.text = base64.b64encode(bytes(scaled)).decode()
                row['boxes_scaled'] = count
            media, streams = graphic_media(root, item)
            key = media.get('ObjectUID') or media.get('ObjectID')
            if key not in touched_media:
                others = [i for i in media_consumers(root, media) if i not in donors.values()]
                for stream in streams:
                    stream.find('FrameRect').text = f'0,0,{canvas[0]},{canvas[1]}'
                touched_media.add(key)
                # The synthetic media is shared by every graphic cloned from the same
                # template. Record who else now reads the new frame; in a prepared
                # scratch copy those are template leftovers, never the source project.
                row['shared_media_other_items'] = len(others)
            rect = item.find('FrameRect')
            if rect is not None:
                rect.text = f'0,0,{canvas[0]},{canvas[1]}'
            row['scale'] = scale_x
        after_box = document_box(payload(text_node(root, item), shared))
        problems = geometry_problems(canvas=canvas, media=media_canvas(root, item),
                                     position=text_position(root, item)[0], box=after_box,
                                     mode=mode, y_pct=profile['y_pct'])
        if problems:
            raise ValueError(f'Donor {item_id} still does not fit {canvas[0]}x{canvas[1]} after '
                             'retargeting (its authored centre is not the profile centre?): ' + '; '.join(problems))
        row.update(media_after=list(media_canvas(root, item)), box_after=after_box)
        report.append(row)
    alias_changes = []
    if normalize_generated_aliases:
        from premiere_caption_handoff import normalize_aliases
        targets = set()
        for item_id in donors.values():
            media, _ = graphic_media(root, ids[item_id])
            if media.findtext('Infinite') != 'true' or media.findtext('Title') != 'Graphic':
                raise ValueError('Alias normalization only supports generated Graphics')
            targets.add((media.findtext('ImplementationID'), media.findtext('FilePath')))
        alias_changes = normalize_aliases(root, targets, canvas)
    if hashlib.sha256(project.read_bytes()).hexdigest() != source_hash:
        raise ValueError('Prepared project changed during retarget')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as f:
        f.write(gzip.compress(ET.tostring(root, encoding='utf-8', xml_declaration=True), mtime=0))
    new_profile = dict(profile, project_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                       donor_canvas=list(canvas))
    new_profile['retarget'] = dict(source_project=str(project.resolve()), source_sha256=source_hash,
                                   target_canvas=list(canvas), donors=report,
                                   status='OFFLINE_RETARGETED_REQUIRES_PREMIERE_SAVE_REOPEN_RENDER_AND_CLICK_TEST')
    if normalize_generated_aliases:
        new_profile['retarget']['generated_alias_changes'] = alias_changes
        new_profile['retarget']['alias_scope'] = 'Prepared copy only; all generated media descriptors with exact implementation/path identity. Native persistence and render still required.'
    with out_profile.open('x') as f:
        json.dump(new_profile, f, indent=2)
    return new_profile


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--project', required=True)
    ap.add_argument('--profile', required=True)
    ap.add_argument('--output', required=True)
    ap.add_argument('--out-profile', required=True)
    ap.add_argument('--normalize-generated-aliases', action='store_true', help='Experimental: align cached stream canvases sharing the exact generated donor media identity, in the output copy only')
    a = ap.parse_args()
    result = retarget(a.project, a.profile, a.output, a.out_profile, normalize_generated_aliases=a.normalize_generated_aliases)
    print(json.dumps(dict(output=a.output, profile=a.out_profile, donor_canvas=result['donor_canvas'],
                          donors=result['retarget']['donors']), indent=2))


if __name__ == '__main__':
    main()
