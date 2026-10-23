#!/usr/bin/env python3
"""Build one editable Premiere review sequence from designed assemblies or legacy packets."""
from __future__ import annotations

import argparse
from fractions import Fraction
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import quote
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from assembly_job import load, validate_native_packet, validate_provisional_packet
from compile_assembly import digest, validate_compiled


def probe(media):
    raw = subprocess.check_output([
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height,r_frame_rate,duration',
        '-of', 'json', str(media)], text=True)
    row = json.loads(raw)['streams'][0]
    return int(row['width']), int(row['height']), Fraction(row['r_frame_rate']), float(row['duration'])


def probe_audio(media):
    raw = subprocess.check_output([
        'ffprobe', '-v', 'error', '-select_streams', 'a:0',
        '-show_entries', 'stream=sample_rate,channels,bits_per_raw_sample,bits_per_sample',
        '-of', 'json', str(media)], text=True)
    rows = json.loads(raw).get('streams', [])
    if len(rows) != 1:
        raise ValueError(f'{media}: an explicit dialogue audio stream is required')
    row = rows[0]
    channels, sample_rate = int(row['channels']), int(row['sample_rate'])
    depth = int(row.get('bits_per_raw_sample') or row.get('bits_per_sample') or 16)
    if depth == 0:
        depth = 16
    if not 1 <= channels <= 32 or not 8000 <= sample_rate <= 192000 or depth not in (8, 16, 24, 32, 64):
        raise ValueError(f'{media}: unsupported source audio format')
    return channels, sample_rate, depth


def packet_clip(path):
    schema = load(path).get('schema')
    if schema == 'edit.provisional-native-packet/v1':
        packet = validate_provisional_packet(path)
        media = Path(packet['media']['path']).resolve()
        frames = packet['source_frames']
        status = 'PROVISIONAL'
        note = packet['review_note'] + ' Unresolved: ' + ', '.join(
            item['code'] for item in packet['issues'])
    else:
        packet = validate_native_packet(path)
        mapping = load(packet['source_mapping']['path'])
        if mapping.get('clock_basis') != 'identical':
            raise ValueError('measured multicamera packet needs its dedicated adapter')
        media = Path(mapping['media']['path']).resolve()
        rate = Fraction(packet['fps'])
        frames = [[round(a * rate), round(b * rate)] for a, b in packet['source_spans']]
        status = 'FINAL_EDITORIAL_PASS'
        note = 'Final editorial review passed; native playback and human approval remain pending.'
    return {'id': packet['clip_id'], 'media': media, 'frames': frames,
            'fps': Fraction(packet['fps']), 'status': status, 'note': note}


def designed_clips(path):
    """Bind resolved source frames to the exact model-selected words compiled earlier."""
    resolved = load(path)
    if resolved.get('schema') != 'edit.resolved-assembly/v1':
        raise ValueError('expected edit.resolved-assembly/v1; raw moment/window manifests are refused')
    compiled_path = Path(resolved['compiled_path']).resolve()
    if digest(compiled_path) != resolved.get('compiled_sha256'):
        raise ValueError('compiled selection changed after boundary resolution')
    compiled = validate_compiled(compiled_path)
    rows = resolved.get('clips')
    if not isinstance(rows, list) or len(rows) != len(compiled['clips']):
        raise ValueError('resolved clip set differs from compiled selection')
    clips = []
    for row, design in zip(rows, compiled['clips']):
        clip_id = design['id']
        if row.get('id') != clip_id:
            raise ValueError('resolved clip order differs from compiled selection')
        media = Path(design['media'])
        width, height, fps, _ = probe(media)
        if width * 9 != height * 16:
            raise ValueError(f'{clip_id}: expected 16:9 source, got {width}x{height}')
        frames = row.get('source_frames')
        if not isinstance(frames, list) or len(frames) != len(design['spans']):
            raise ValueError(f'{clip_id}: every designed span needs one resolved frame span')
        for pair, span in zip(frames, design['spans']):
            if (not isinstance(pair, list) or len(pair) != 2 or
                not all(type(n) is int for n in pair) or pair[0] >= pair[1]):
                raise ValueError(f'{clip_id}: bad integer source-frame span')
            if abs(float(Fraction(pair[0], 1) / fps) - span['asr_start']) > 2.0 or \
               abs(float(Fraction(pair[1], 1) / fps) - span['asr_end']) > 2.0:
                raise ValueError(f'{clip_id}: resolved frames do not match selected source words')
        status = row.get('status', 'EDITOR_REVIEW')
        if status not in ('EDITOR_REVIEW', 'MEASURED_EDGES', 'PROVISIONAL_SEAM'):
            raise ValueError(f'{clip_id}: invalid editor-review boundary status')
        issues = row.get('boundary_issues', [])
        if not isinstance(issues, list) or (status == 'PROVISIONAL_SEAM') != bool(issues):
            raise ValueError(f'{clip_id}: provisional status and boundary issues disagree')
        note = row.get('note', 'Designed assembly; editor to review.')
        if not isinstance(note, str):
            raise ValueError(f'{clip_id}: note must be text')
        if issues and not all(isinstance(issue, dict) and issue.get('code') for issue in issues):
            raise ValueError(f'{clip_id}: boundary issues need explicit codes')
        cta = design.get('approved_cta')
        clips.append({'id': clip_id, 'media': media, 'frames': frames,
                      'fps': fps, 'status': status, 'note': note,
                      **({'gap_after': 0, 'role': 'body', 'group_id': clip_id} if cta else {})})
        if cta:
            cta_media = Path(cta['media'])
            cw, ch, cr, duration = probe(cta_media)
            if ((cw, ch, cr) != (width, height, fps)
                    or Fraction(cta['fps']) != fps
                    or cta['source_frames'] != [0, round(duration * fps)]):
                raise ValueError(f'{clip_id}: CTA must be the complete matching-format approved asset')
            clips.append({'id': clip_id + '__CTA', 'media': cta_media,
                          'frames': [cta['source_frames']], 'fps': fps,
                          'status': 'APPROVED_ASSET', 'role': 'approved_cta',
                          'group_id': clip_id, 'offer': cta['offer'],
                          'note': f"{cta['offer']}: {cta['rationale']} | Resource: {cta['lead_base']} | Workshop: {cta['workshop_base']}"})
    return clips


def build(packet_paths, name, output, gap_frames=480, assemblies_path=None):
    if output.exists() or output.with_suffix('.expected.json').exists():
        raise ValueError('review output exists; use a new revision path')
    clips = designed_clips(assemblies_path) if assemblies_path else [packet_clip(Path(p)) for p in packet_paths]
    if not clips:
        raise ValueError('at least one clip is required')
    files = {c['media']: probe(c['media']) for c in clips}
    audio_formats = {media: probe_audio(media) for media in files}
    width, height, fps, _ = files[clips[0]['media']]
    if any(r != fps for _, _, r, _ in files.values()):
        raise ValueError('all review sources need matching frame rate')
    if any(w * height != h * width for w, h, _, _ in files.values()):
        raise ValueError('mixed review resolutions need matching aspect ratio')
    width, height = max(((w, h) for w, h, _, _ in files.values()), key=lambda size: size[0] * size[1])
    if any(c['fps'] != fps for c in clips):
        raise ValueError('packet frame rate differs from source')
    if gap_frames < 0:
        raise ValueError('negative review gap')
    timebase = round(fps)
    ntsc = 'TRUE' if fps.denominator != 1 else 'FALSE'
    rate_xml = f'<rate><timebase>{timebase}</timebase><ntsc>{ntsc}</ntsc></rate>'
    ids = {media: f'file-{n}' for n, media in enumerate(files, 1)}
    written = set()

    def file_ref(media):
        fid = ids[media]
        if media in written:
            return f'<file id="{fid}"/>'
        written.add(media)
        source_width, source_height, _, duration = files[media]
        channels, sample_rate, depth = audio_formats[media]
        url = 'file://localhost' + quote(str(media), safe='/')
        return (f'<file id="{fid}"><name>{escape(media.name)}</name>'
                f'<pathurl>{url}</pathurl><duration>{round(duration * fps)}</duration>'
                f'<width>{source_width}</width><height>{source_height}</height>{rate_xml}<media>'
                f'<video><samplecharacteristics><width>{source_width}</width><height>{source_height}</height>'
                f'{rate_xml}<anamorphic>FALSE</anamorphic><pixelaspectratio>square</pixelaspectratio>'
                '<fielddominance>none</fielddominance></samplecharacteristics></video>'
                f'<audio><samplecharacteristics><depth>{depth}</depth><samplerate>{sample_rate}</samplerate>'
                f'</samplecharacteristics><channelcount>{channels}</channelcount></audio></media></file>')

    video, audio, markers, expected = [], [], [], []
    timeline = 0
    item = 0
    for n, clip in enumerate(clips, 1):
        markers.append((timeline, f'CLIP {n:02d} - {clip["id"]} [{clip["status"]}]', clip['note']))
        media = clip['media']
        limit = round(files[media][3] * fps)
        for span_number, span in enumerate(clip['frames'], 1):
            start, end = span
            if not 0 <= start < end <= limit:
                raise ValueError(f'bad source span: {clip["id"]} {start}-{end}')
            item += 1
            duration = end - start
            vid, aid = f'clipitem-{item*2-1}', f'clipitem-{item*2}'
            label = escape(f'{clip["id"]}_{span_number:02d}')
            common = (f'<name>{label}</name><enabled>TRUE</enabled>'
                      f'<duration>{duration}</duration><start>{timeline}</start>'
                      f'<end>{timeline+duration}</end><in>{start}</in><out>{end}</out>')
            links = (f'<link><linkclipref>{vid}</linkclipref><mediatype>video</mediatype>'
                     f'<trackindex>1</trackindex><clipindex>{item}</clipindex></link>'
                     f'<link><linkclipref>{aid}</linkclipref><mediatype>audio</mediatype>'
                     f'<trackindex>1</trackindex><clipindex>{item}</clipindex><groupindex>1</groupindex></link>')
            video.append(f'<clipitem id="{vid}">{common}{file_ref(media)}{links}</clipitem>')
            audio.append(f'<clipitem id="{aid}">{common}{file_ref(media)}'
                         '<sourcetrack><mediatype>audio</mediatype><trackindex>1</trackindex>'
                         f'</sourcetrack>{links}</clipitem>')
            expected.append({'clip_id': clip['id'], 'media': str(media),
                             'timeline_frames': [timeline, timeline+duration],
                             'source_frames': span, 'status': clip['status'],
                             **({key: clip[key] for key in ('role', 'group_id', 'offer') if key in clip})})
            timeline += duration
        if n < len(clips):
            timeline += clip.get('gap_after', gap_frames)
    marker_xml = ''.join(
        f'<marker><name>{escape(label)}</name><comment>{escape(note)}</comment>'
        f'<in>{frame}</in><out>-1</out></marker>' for frame, label, note in markers)
    seq = escape(name)
    xml = (f'<?xml version="1.0" encoding="utf-8"?><xmeml version="4"><sequence id="{seq}">'
           f'<duration>{timeline}</duration><name>{seq}</name><width>{width}</width>'
           f'<height>{height}</height>{rate_xml}<media><video><format><samplecharacteristics>'
           '<pixelaspectratio>square</pixelaspectratio><anamorphic>FALSE</anamorphic>'
           f'<fielddominance>none</fielddominance><colordepth>24</colordepth><width>{width}</width>'
           f'<height>{height}</height>{rate_xml}</samplecharacteristics></format><track>'
           + ''.join(video) + '</track></video><audio><format><samplecharacteristics>'
           '<depth>16</depth><samplerate>48000</samplerate></samplecharacteristics></format><track>'
           + ''.join(audio) + '</track></audio></media>' + marker_xml + '</sequence></xmeml>')
    output.write_text(xml)
    receipt = {'schema': 'edit.review-xml-expected/v1', 'sequence_name': name,
               'fps': str(fps), 'timeline_frames': timeline, 'items': expected}
    output.with_suffix('.expected.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    source = ap.add_mutually_exclusive_group(required=True)
    source.add_argument('--packets', help='JSON list of legacy guarded packet paths')
    source.add_argument('--assemblies', type=Path, help='edit.resolved-assembly/v1 tied to compiled source words')
    ap.add_argument('--name', required=True)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--gap-frames', type=int, default=480)
    args = ap.parse_args()
    try:
        packet_paths = json.loads(args.packets) if args.packets else []
        result = build(packet_paths, args.name, args.out, args.gap_frames, args.assemblies)
    except (ValueError, KeyError, TypeError, OSError, subprocess.CalledProcessError) as exc:
        ap.error(str(exc))
    print(json.dumps({'clips': len(set(item['clip_id'] for item in result['items'])), 'items': len(result['items']),
                      'timeline_frames': result['timeline_frames']}))


if __name__ == '__main__':
    main()
