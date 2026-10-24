"""Change selected source bindings in a new Resolve-native DRT, not a converter.

All existing archive bytes except selected audio MediaRef/MediaFilePath leaves
remain intact. New media descriptors come from a native donor export. Import,
full native readback and parent preservation are mandatory acceptance steps.
"""
import html
import re
import zipfile
from common import require, sha
from resolve_precision import SCHEMA_VERSION, field, read_time
from audio_plan import resolve_music_frames, same_native_frame


def replace_field(block, key, value):
    pattern, _ = field(block, key)
    return re.sub(pattern, lambda _: ('<' + key + '>').encode() + value + ('</' + key + '>').encode(), block)


def archive_entries(path):
    with zipfile.ZipFile(path) as archive:
        entries = [(info, archive.read(info.filename)) for info in archive.infolist()]
    require(len({i.filename for i, _ in entries}) == len(entries), 'Duplicate archive entry')
    for info, data in entries:
        if info.filename.endswith('.xml'):
            require(SCHEMA_VERSION in data, 'Unqualified Resolve archive version')
    return entries


def sequence(entries):
    matches = [(i, d) for i, d in entries if i.filename.startswith('SeqContainer/') and i.filename.endswith('.xml')]
    require(len(matches) == 1, 'Expected one native sequence container')
    return matches[0]


def audio_tracks(data):
    region = re.findall(rb'<AudioTrackVec>(.*?)</AudioTrackVec>', data, re.S)
    require(len(region) == 1, 'Ambiguous audio track vector')
    return list(re.finditer(rb'<Sm2TiTrack\b[^>]*>.*?</Sm2TiTrack>', region[0], re.S)), region[0]


def clips(track):
    return list(re.finditer(rb'<Sm2TiAudioClip\b[^>]*>.*?</Sm2TiAudioClip>', track, re.S))


def verify_clip(block, spec, index):
    bed = spec['audio']['music'][index]
    source = next(s for s in spec['sources'] if s['id'] == bed['sourceId'])
    require(html.unescape(field(block, 'MediaFilePath')[1].decode()) == source['path'], 'Archive music source differs')
    timing = resolve_music_frames(spec, bed)
    for key, expected in [('Start', bed['startFrame']), ('In', timing['sourceInSample']), ('Duration', timing['samples'])]:
        require(same_native_frame(read_time(field(block, key)[1].decode()), expected), 'Archive music timing differs: ' + key)


def patch_checkpoint(parent, donor, target, previous, current, indices):
    require(not target.exists(), 'Replacement archive exists; reconcile before retrying')
    parent_hash, donor_hash = sha(parent), sha(donor)
    entries, donors = archive_entries(parent), archive_entries(donor)
    seq_info, seq = sequence(entries); _, donor_seq = sequence(donors)
    tracks, region = audio_tracks(seq); donor_tracks, _ = audio_tracks(donor_seq)
    require(len(tracks) >= 2 and len(donor_tracks) == 1, 'Unexpected native music/donor track coverage')
    selected_track = tracks[1].group(); old_clips = clips(selected_track); donor_clips = clips(donor_tracks[0].group())
    require(len(old_clips) == len(previous['audio']['music']) and len(donor_clips) == len(indices), 'Archive clip coverage differs')
    pools = [(i, d) for i, d in entries if i.filename.startswith('MediaPool/') and i.filename.endswith('MpFolder.xml')]
    require(len(pools) == 1, 'Nested native archive bins need separate qualification')
    pool_info, pool = pools[0];folder = re.search(rb'<Sm2MpFolder DbId="([^"]+)"', pool)
    require(folder and pool.count(b'</MediaVec>') == 1, 'Ambiguous native media folder')
    donor_pool = b'\n'.join(d for i, d in donors if i.filename.startswith('MediaPool/') and i.filename.endswith('MpFolder.xml'))
    changes, new_media, proof = [], [], []
    for position, index in enumerate(indices):
        old, new = old_clips[index], donor_clips[position].group()
        verify_clip(old.group(), previous, index);verify_clip(new, current, index)
        ref = field(new, 'MediaRef')[1]
        media = re.findall(rb'<Sm2MpAudioClip DbId="' + re.escape(ref) + rb'">.*?</Sm2MpAudioClip>', donor_pool, re.S)
        require(len(media) == 1 and ref not in pool and ref not in seq, 'Donor source identity is missing or already used')
        require(ref not in [r for r, _ in new_media], 'Replacement donor identities must be distinct')
        new_media.append((ref, replace_field(media[0], 'MpFolder', folder[1])))
        block = replace_field(old.group(), 'MediaRef', ref)
        block = replace_field(block, 'MediaFilePath', field(new, 'MediaFilePath')[1])
        changes.append((old.start(), old.end(), block))
        proof.append({'musicIndex': index, 'oldMediaRef': field(old.group(), 'MediaRef')[1].decode(), 'newMediaRef': ref.decode()})
    for start, end, block in sorted(changes, reverse=True):
        selected_track = selected_track[:start] + block + selected_track[end:]
    updated_region = region[:tracks[1].start()] + selected_track + region[tracks[1].end():]
    seq = seq.replace(b'<AudioTrackVec>' + region + b'</AudioTrackVec>', b'<AudioTrackVec>' + updated_region + b'</AudioTrackVec>', 1)
    pool = pool.replace(b'</MediaVec>', b''.join(b'<Element>' + m + b'</Element>' for _, m in new_media) + b'</MediaVec>', 1)
    with target.open('xb') as file, zipfile.ZipFile(file, 'w', zipfile.ZIP_DEFLATED) as output:
        for info, data in entries:
            output.writestr(info, seq if info.filename == seq_info.filename else pool if info.filename == pool_info.filename else data)
    require(sha(parent) == parent_hash and sha(donor) == donor_hash, 'Input native archive changed')
    return {'schema': 'acq-edit/resolve-music-binding-v1', 'archiveVersion': '21.1.1.0010/17',
            'parentSha256': parent_hash, 'donorSha256': donor_hash, 'replacementSha256': sha(target),
            'bindings': proof, 'status': 'awaiting-native-import-and-readback'}
