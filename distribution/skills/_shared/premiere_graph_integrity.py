"""Offline prepared-project graph checks; never edit an open Premiere project.

Callers own dependency selection, ID remapping and protected-object comparison.
This module neither broadens supported native routes nor infers track ownership.
"""
import copy
import xml.etree.ElementTree as ET


def binary_pool(roots):
    pool = {}
    for root in roots:
        for node in root.iter():
            key = node.get('BinaryHash')
            if not key or not (node.text or '').strip():
                continue
            value = (node.tag, ''.join(node.text.split()), node.get('Encoding'))
            if key in pool and pool[key][0] != value:
                raise ValueError('Conflicting binary payload: ' + key)
            pool[key] = (value, node)
    return pool


def materialize_aliases(nodes, source_roots):
    """Return isolated clones with every alias resolved from authoritative roots.

    Includes binary metadata such as ModificationState, not just Source Text.
    Reject conflicts/missing providers before returning anything to the caller.
    """
    pool = binary_pool([*source_roots, *nodes])
    clones = [copy.deepcopy(n) for n in nodes]
    for root in clones:
        for node in root.iter():
            key = node.get('BinaryHash')
            if not key:
                continue
            if key not in pool:
                raise ValueError('Unresolved binary payload: ' + key)
            _, provider = pool[key]
            if node.tag != provider.tag:
                raise ValueError('Binary payload tag mismatch: ' + key)
            if not (node.text or '').strip():
                node.text = provider.text
                for k, v in provider.attrib.items():
                    if k not in ('ObjectID', 'ObjectUID', 'ObjectRef', 'ObjectURef'):
                        node.set(k, v)
    return clones


def validate_aliases(root):
    pool = binary_pool([root])
    for node in root.iter():
        if node.get('BinaryHash') and node.get('BinaryHash') not in pool:
            raise ValueError('Unresolved binary payload: ' + node.get('BinaryHash'))
    return len(pool)


def master_sources(root, sequence_uid, track_uid):
    ids = {n.get('ObjectID'): n for n in root if n.get('ObjectID')}
    seqs = [n for n in root if n.tag == 'Sequence' and n.get('ObjectUID') == sequence_uid]
    if len(seqs) != 1:
        raise ValueError('Exact sequence required')
    groups = [ids[x.get('ObjectRef')] for x in seqs[0].findall('TrackGroups/TrackGroup/Second')]
    groups = [g for g in groups if g.tag == 'AudioTrackGroup']
    if len(groups) != 1:
        raise ValueError('Supported single audio group required')
    group = groups[0]
    refs = [x.get('ObjectURef') for x in group.findall('TrackGroup/Tracks/Track')]
    tracks = [n for n in root if n.tag == 'AudioClipTrack' and n.get('ObjectUID') == track_uid]
    if refs.count(track_uid) != 1 or len(tracks) != 1:
        raise ValueError('Exact owned audio track required')
    master = ids[group.find('MasterTrack').get('ObjectRef')]
    inlet = ids[master.find('Inlet').get('ObjectRef')]
    sources = inlet.find('Sources')
    if sources is None or inlet.tag != 'AudioTrackInlet':
        raise ValueError('Unsupported master inlet shape')
    return inlet, sources


def connect_owned_track(root, *, sequence_uid, track_uid, expected_sources):
    """Connect a declared new/grafted track on a caller-owned OFFLINE copy only.

    expected_sources is an exact ordered list from the preparation snapshot.
    Submixes, custom routing and native acceptance require separate verification.
    """
    inlet, sources = master_sources(root, sequence_uid, track_uid)
    current = [n.get('ObjectURef') for n in sources]
    if current != expected_sources or len(set(current)) != len(current):
        raise ValueError('Master routing changed or duplicates present')
    if [n.get('Index') for n in sources] != list(map(str, range(len(current)))):
        raise ValueError('Unsupported inlet index layout')
    if track_uid not in current:
        ET.SubElement(sources, 'Source', {'Index': str(len(current)), 'ObjectURef': track_uid})
    return {'changed_object': inlet.get('ObjectID'), 'track_uid': track_uid,
            'before': current, 'after': [n.get('ObjectURef') for n in sources],
            'native_mix_verified': False}
