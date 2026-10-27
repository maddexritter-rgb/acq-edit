from acq_edit_runtime import skill_scripts
#!/usr/bin/env python3
"""Validate the existing review_xml output/receipt for disposable native import.

Mechanical validation only. No editorial design, Premiere calls or file writes.
"""
from fractions import Fraction
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from datetime import datetime, timezone
from urllib.parse import urlparse, unquote
import xml.etree.ElementTree as ET

TPS = 254016000000


def bounded(path, root):
    path = Path(path).resolve(strict=True)
    if not path.is_file():
        raise ValueError('Source/XML/receipt must be an existing file')
    if not path.is_relative_to(root):
        runtime = root.parent
        auth = json.loads((runtime/'edit-project-authorization.json').read_text())
        lease = json.loads((runtime/'lease.json').read_text())
        now = datetime.now(timezone.utc).timestamp()
        if (auth.get('schema') != 'premiere-agent/edit-project-authorization-v1'
                or auth.get('projectPath') != lease.get('projectPath')
                or lease.get('productionBridgeStopped') is not True
                or datetime.fromisoformat(auth['expiresAt']).timestamp() <= now
                or datetime.fromisoformat(lease['expiresAt']).timestamp() <= now
                or 'lab_import_compiled_assembly' not in auth.get('tools', [])
                or str(path) not in auth.get('readPaths', [])):
            raise ValueError('Source/XML/receipt is outside the exact authorized input set')
    return path


def checked(path, expected, root, *, transcript=False):
    path = bounded(path, root)
    # Full-session word data is larger than an XML packet. Keep both bounded.
    limit = 32_000_000 if transcript else 8_000_000
    if path.stat().st_size > limit:
        raise ValueError('Assembly transcript size limit' if transcript else 'Assembly XML/receipt size limit')
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('Assembly input hash changed')
    return data


def integer(value):
    if isinstance(value, str):
        if not value.isascii() or not value.isdecimal() or str(int(value)) != value:
            raise ValueError('Noncanonical integer frame')
        value = int(value)
    if type(value) is not int or value < 0 or value > 9223372036854775807:
        raise ValueError('Nonnegative integer frame required')
    return value


def validate(xml_path, xml_sha, expected_path, expected_sha, fixture_root):
    root = Path(fixture_root).resolve(strict=True)
    raw = checked(xml_path, xml_sha, root)
    expected = json.loads(checked(expected_path, expected_sha, root))
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('XML declarations/entities unsupported')
    tree = ET.fromstring(raw)
    if tree.tag != 'xmeml' or tree.get('version') != '4' or len(tree) != 1 or tree[0].tag != 'sequence' or len(tree.findall('.//sequence')) != 1:
        raise ValueError('One canonical xmeml v4 sequence required')
    if expected.get('schema') != 'edit.review-xml-expected/v1':
        raise ValueError('Existing review-XML receipt required')
    seq = tree[0]; rate = Fraction(expected['fps']); step = Fraction(TPS, 1) / rate
    if step.denominator != 1 or rate <= 0:
        raise ValueError('Frame rate not representable in exact ticks')
    frame_ticks = int(step)
    def ticks(frame):
        value = integer(frame) * frame_ticks
        if value > 9223372036854775807:
            raise ValueError('Tick overflow')
        return str(value)
    xml_rate = Fraction(integer(seq.findtext('rate/timebase')))
    ntsc = seq.findtext('rate/ntsc')
    if ntsc not in ('TRUE', 'FALSE'):
        raise ValueError('Explicit NTSC flag required')
    if ntsc == 'TRUE': xml_rate *= Fraction(1000, 1001)
    if xml_rate != rate or seq.findtext('name') != expected['sequence_name'] or integer(seq.findtext('duration')) != integer(expected['timeline_frames']):
        raise ValueError('XML sequence name/rate/duration differs from receipt')
    name = expected['sequence_name']
    if not isinstance(name, str) or not name.strip() or len(name) > 512:
        raise ValueError('Invalid sequence name')
    width = integer(seq.findtext('media/video/format/samplecharacteristics/width'))
    height = integer(seq.findtext('media/video/format/samplecharacteristics/height'))
    if not width or width > 16384 or not height or height > 16384:
        raise ValueError('Unsupported sequence canvas')
    # Existing compiler emits clip placements, not effects, transitions or nested sequences.
    if any(tree.findall('.//' + tag) for tag in ('filter', 'transitionitem', 'generatoritem', 'speed', 'timecode')):
        raise ValueError('Unsupported assembly XML content')
    definitions = {}
    for f in tree.findall('.//file'):
        fid = f.get('id')
        if not fid: raise ValueError('Missing file ID')
        if len(f):
            if fid in definitions: raise ValueError('Duplicate full media definition')
            url = urlparse(f.findtext('pathurl') or '')
            if url.scheme != 'file' or url.netloc not in ('', 'localhost') or url.query or url.fragment:
                raise ValueError('Only local source file URLs supported')
            definitions[fid] = str(bounded(unquote(url.path), root))
    rows = expected.get('items')
    if not isinstance(rows, list) or not 1 <= len(rows) <= 1000:
        raise ValueError('Bounded nonempty assembly required')
    tracks = []
    for kind in ('video', 'audio'):
        found = seq.findall('media/' + kind + '/track')
        if len(found) != 1 or len(found[0]) != len(rows) or any(c.tag != 'clipitem' for c in found[0]):
            raise ValueError('Exactly one unprocessed V1/A1 track required')
        tracks.append(list(found[0]))
    if len(tree.findall('.//clipitem')) != 2 * len(rows):
        raise ValueError('Unexpected XML clip items')
    xml_ids = [c.get('id') for track in tracks for c in track]
    if any(not x for x in xml_ids) or len(set(xml_ids)) != len(xml_ids):
        raise ValueError('Ambiguous XML clip identities')
    result = []; previous_end = 0
    for i, row in enumerate(rows):
        timeline = row['timeline_frames']; source = row['source_frames']
        if not all(isinstance(p, list) and len(p) == 2 for p in (timeline, source)):
            raise ValueError('Exact frame pairs required')
        a, b, sin, sout = map(integer, timeline + source)
        if a < previous_end or b <= a or sout <= sin or b - a != sout - sin:
            raise ValueError('Overlapping or retimed assembly ranges')
        previous_end = b
        media = str(bounded(row['media'], root))
        for kind, track in zip(('video', 'audio'), tracks):
            c = track[i]
            if c.findtext('enabled') != 'TRUE' or [integer(c.findtext(k)) for k in ('start', 'end', 'in', 'out')] != [a, b, sin, sout]:
                raise ValueError('XML range/enabled state differs from receipt')
            files = c.findall('file')
            if len(files) != 1 or definitions.get(files[0].get('id')) != media:
                raise ValueError('XML source differs from receipt')
            links = c.findall('link')
            wanted = {(tracks[k][i].get('id'), media_kind, '1', str(i + 1)) for k, media_kind in enumerate(('video', 'audio'))}
            actual = {(l.findtext('linkclipref'), l.findtext('mediatype'), l.findtext('trackindex'), l.findtext('clipindex')) for l in links}
            if len(links) != 2 or actual != wanted:
                raise ValueError('XML paired AV linkage differs from compiler contract')
            if kind == 'audio' and (c.findtext('sourcetrack/mediatype'), c.findtext('sourcetrack/trackindex')) != ('audio', '1'):
                raise ValueError('Unsupported source audio track')
        result.append({'clip_id': row['clip_id'], 'media_path': media, 'start_ticks': ticks(a), 'end_ticks': ticks(b), 'source_in_ticks': ticks(sin), 'source_out_ticks': ticks(sout)})
    if previous_end != integer(expected['timeline_frames']):
        raise ValueError('Sequence duration differs from last item')
    markers = []
    for marker in seq.findall('marker'):
        if marker.findtext('out') != '-1': raise ValueError('Only compiler point markers supported')
        markers.append({'name': marker.findtext('name') or '', 'comments': marker.findtext('comment') or '', 'start_ticks': ticks(marker.findtext('in'))})
    return {'sequence_name': name, 'frame_ticks': str(frame_ticks), 'duration_ticks': ticks(previous_end), 'width': width, 'height': height, 'items': result, 'markers': markers,
            'proof': 'XML and expected receipt agree mechanically; native AV links, words and sound not verified'}


def verify_native(expected, links, project, project_path, sequence_id):
    """Compare compiler intent to native links and an independent sequence snapshot.

    Pass the data fields from inspect_assembly_links / inspect_project_sequences.
    This verifies observed native state, not compiler provenance, persistent state,
    rendered sound or the editorial quality of the selection.
    """
    if (links.get('project_path') != project_path or links.get('sequence_id') != sequence_id
            or project.get('project_path') != project_path
            or links.get('verification') != 'stable_native_link_membership'):
        raise ValueError('Exact native project/sequence link evidence required')
    sequences = [s for s in project['sequences'] if s['sequence_id'] == sequence_id]
    if len(sequences) != 1 or sequences[0]['name'] != expected['sequence_name']:
        raise ValueError('Native assembly sequence identity mismatch')
    snapshot = sequences[0]['snapshot']
    if snapshot.get('projectPath') != project_path or snapshot.get('sequenceId') != sequence_id:
        raise ValueError('Independent snapshot identity mismatch')
    settings = snapshot['settings']
    if [settings.get('videoFrameWidth'), settings.get('videoFrameHeight')] != [expected['width'], expected['height']] or links['frame_duration_ticks'] != expected['frame_ticks']:
        raise ValueError('Native assembly canvas or rational frame duration mismatch')
    want_markers = [{'name': m['name'], 'comments': m['comments'], 'start': m['start_ticks'], 'end': m['start_ticks']} for m in expected['markers']]
    if snapshot.get('markers') != want_markers:
        raise ValueError('Native assembly markers mismatch')
    rows = links['items']; clips = {}
    for row in rows:
        key = (row['kind'], row['track_index'], row['item_index'])
        if key in clips or row['track_index'] != 0 or row['kind'] not in ('video', 'audio'):
            raise ValueError('Unexpected or duplicate native assembly item')
        clips[key] = row
    count = len(expected['items'])
    if set(clips) != {(kind, 0, i) for kind in ('video', 'audio') for i in range(count)}:
        raise ValueError('Native assembly item inventory mismatch')
    native_ids = [r['item']['node_id'] for r in rows]
    if any(not isinstance(x, str) or not x for x in native_ids) or len(set(native_ids)) != len(native_ids):
        raise ValueError('Ambiguous native assembly item identity')
    independent = {}
    track_keys = set()
    for track in snapshot['tracks']:
        kind = {0: 'video', 1: 'audio'}.get(track['kind'])
        if kind is None or (kind, track['index']) in track_keys:
            raise ValueError('Independent track inventory ambiguous')
        track_keys.add((kind, track['index']))
        for i, clip in enumerate(track['clips']):
            independent[kind, track['index'], i] = clip
    if set(independent) != set(clips):
        raise ValueError('Independent assembly item inventory mismatch')
    mapping = []
    for i, want in enumerate(expected['items']):
        pair = [clips[kind, 0, i] for kind in ('video', 'audio')]
        v, a = (r['item'] for r in pair)
        if not v['source_id'] or v['source_id'] != a['source_id']:
            raise ValueError('Paired native AV source identities differ')
        for kind, row, peer in [('video', pair[0], a), ('audio', pair[1], v)]:
            item = row['item']; other = independent[kind, 0, i]
            if row['linked_node_ids'] != [peer['node_id']]:
                raise ValueError('Native AV link membership differs from compiler pair')
            if item['media_path'] != want['media_path'] or item['offline'] is not False:
                raise ValueError('Native assembly media path/offline mismatch')
            if item['speed'] != 1 or item['speed_reversed'] is not False or item['disabled'] is not False:
                raise ValueError('Native assembly playback mismatch')
            if other['id'] != item['node_id'] or other['sourceId'] != item['source_id'] or other['speed'] != 1 or other['disabled'] is not False:
                raise ValueError('Independent assembly identity/playback mismatch')
            for key, field in [('start_ticks', 'start'), ('end_ticks', 'end'), ('source_in_ticks', 'inPoint'), ('source_out_ticks', 'outPoint')]:
                # Preserve exact string representation; never pass through seconds.
                if not isinstance(item[key], str) or item[key] != want[key] or other[field] != want[key]:
                    raise ValueError('Native assembly source/timeline ticks mismatch')
        mapping.append({'assembly_item_index': i, 'clip_id': want['clip_id'], 'video_node_id': v['node_id'], 'audio_node_id': a['node_id'], 'source_node_id': v['source_id']})
    return {'status': 'NATIVE_ASSEMBLY_STRUCTURE_AND_LINKS_PASS', 'project_path': project_path, 'sequence_id': sequence_id,
            'items': mapping, 'persistence': 'not_run', 'rendered': 'not_run', 'words_and_sound': 'not_verified'}


def validate_compiled_packet(xml_path, xml_sha, expected_path, expected_sha, fixture_root, resolved_path, resolved_sha, gap_frames):
    """Reproduce the existing writer output from its original v2 design chain.

    The new route accepts no legacy packet or replacement span-only design. This
    is technical provenance, not a new editorial review or approval gate.
    """
    root = Path(fixture_root).resolve(strict=True)
    expected = validate(xml_path, xml_sha, expected_path, expected_sha, str(root))
    gap_frames = integer(gap_frames)
    resolved_path = bounded(resolved_path, root)
    resolved = json.loads(checked(resolved_path, resolved_sha, root))
    if resolved.get('schema') != 'edit.resolved-assembly/v1':
        raise ValueError('Original resolved assembly file required')
    compiled_path = bounded(resolved['compiled_path'], root)
    compiled_sha = resolved['compiled_sha256']
    compiled = json.loads(checked(compiled_path, compiled_sha, root))
    design_path = bounded(compiled['design_path'], root)
    design_sha = compiled['design_sha256']
    design = json.loads(checked(design_path, design_sha, root))
    if design.get('schema') != 'edit.assembly-selection/v2':
        raise ValueError('New native construction requires the original v2 paper-cut selection')
    artifacts = {str(resolved_path): resolved_sha, str(compiled_path): compiled_sha, str(design_path): design_sha,
                 str(bounded(xml_path, root)): xml_sha, str(bounded(expected_path, root)): expected_sha}
    media = {}
    transcripts = set()
    for clip in compiled['clips']:
        words = bounded(clip['source_words'], root)
        checked(words, clip['source_words_sha256'], root, transcript=True)
        transcripts.add(str(words))
        artifacts[str(words)] = clip['source_words_sha256']
        source = bounded(clip['media'], root); info = source.stat()
        media[str(source)] = {'path': str(source), 'size': str(info.st_size), 'mtime_ns': str(info.st_mtime_ns)}
        cta = clip.get('approved_cta')
        if cta:
            for key in ('offer_plan', 'media_lineage'):
                pin = cta[key]
                pinned = bounded(pin['path'], root)
                checked(pinned, pin['sha256'], root)
                artifacts[str(pinned)] = pin['sha256']
            catalog = bounded(cta['catalog_path'], root)
            checked(catalog, cta['catalog_sha256'], root)
            artifacts[str(catalog)] = cta['catalog_sha256']
            for key, hash_key in (('media', 'media_sha256'), ('original_asset', 'original_sha256')):
                asset = bounded(cta[key], root)
                if hashlib.sha256(asset.read_bytes()).hexdigest() != cta[hash_key]:
                    raise ValueError('Approved CTA asset identity changed')
                info = asset.stat()
                media[str(asset)] = {'path': str(asset), 'size': str(info.st_size), 'mtime_ns': str(info.st_mtime_ns)}
    # Bound design references before the canonical compiler opens them.
    for row in design['clips']:
        source, words = bounded(row['media'], root), bounded(row['source_words'], root)
        if str(source) not in media or str(words) not in artifacts:
            raise ValueError('Design references differ from compiled source identities')
    scripts = skill_scripts()
    code_paths = [scripts/name for name in ('review_xml.py', 'compile_assembly.py', 'assembly_job.py')]
    code_hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in code_paths}
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location('assembly_bridge_canonical_writer', scripts/'review_xml.py')
    writer = importlib.util.module_from_spec(spec); spec.loader.exec_module(writer)
    # validate_compiled inside designed_clips recomputes literal words, paper cut,
    # omitted continuation and all original compiler fields without changing them.
    with tempfile.TemporaryDirectory(prefix='assembly-reproduction-', dir=root) as directory:
        rebuilt = Path(directory)/'reproduced.xml'
        writer.build([], expected['sequence_name'], rebuilt, gap_frames=gap_frames, assemblies_path=resolved_path)
        if rebuilt.read_bytes() != checked(xml_path, xml_sha, root):
            raise ValueError('XML is not the exact existing writer output for this resolved selection')
        if json.loads(rebuilt.with_suffix('.expected.json').read_text()) != json.loads(checked(expected_path, expected_sha, root)):
            raise ValueError('XML receipt differs from original compiled/resolved selection')
    for p, sha in artifacts.items(): checked(p, sha, root, transcript=p in transcripts)
    for p, prior in media.items():
        info = bounded(p, root).stat()
        if str(info.st_size) != prior['size'] or str(info.st_mtime_ns) != prior['mtime_ns']:
            raise ValueError('Source media changed during compiler validation')
    if any(hashlib.sha256(Path(p).read_bytes()).hexdigest() != sha for p, sha in code_hashes.items()):
        raise ValueError('Canonical compiler changed during validation')
    return {'expectation': expected, 'provenance': {'schema': 'edit.assembly-compiler-provenance/v1',
            'artifacts': [{'path': p, 'sha256': sha} for p, sha in sorted(artifacts.items())],
            'canonical_code': [{'path': p, 'sha256': sha} for p, sha in sorted(code_hashes.items())],
            'media': list(media.values()), 'gap_frames': gap_frames,
            'verification': 'canonical_v2_selection_recompiled_and_exact_xml_reproduced',
            'media_identity_scope': 'path_size_mtime_not_content_hash', 'editorial_review': 'not_performed'}}


if __name__ == '__main__':
    try:
        if sys.argv[1:2] == ['--compiled']:
            print(json.dumps(validate_compiled_packet(*sys.argv[2:])))
        else:
            print(json.dumps(validate(*sys.argv[1:])))
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
