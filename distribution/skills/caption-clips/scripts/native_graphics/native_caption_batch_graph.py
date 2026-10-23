"""Build independent native graphic objects from an explicit donor/run plan.

Offline construction only; does not insert into a timeline, save, or approve.
"""
import base64
import copy
import uuid
import xml.etree.ElementTree as ET
from .native_graph_clone import clone_graph, place_graph
from .native_run_topology_probe import rebuild_runs
from .decode_graphic_text import decode_runs


def insert_batch(root, *, sequence_uid, track_index, expected_old_item_ids, receipts):
    """Replace only an explicitly identified, unshared scratch track's references.

    Old objects remain in the project graph. No deletion of media or other edits.
    Caller must pass a scratch root, and save/reopen validation is still required.
    """
    objects = {n.get('ObjectID'): n for n in root if n.get('ObjectID')}
    uids = {n.get('ObjectUID'): n for n in root if n.get('ObjectUID')}
    def resolve(ref):
        return objects[ref.get('ObjectRef')] if ref.get('ObjectRef') else uids[ref.get('ObjectURef')]
    def references(element, node):
        return ((node.get('ObjectID') is not None and element.get('ObjectRef') == node.get('ObjectID'))
                or (node.get('ObjectUID') is not None and element.get('ObjectURef') == node.get('ObjectUID')))
    sequences = [n for n in root.findall('Sequence') if n.get('ObjectUID') == sequence_uid]
    if len(sequences) != 1:
        raise ValueError('Exact unique sequence required')
    tracks = []
    for ref in sequences[0].findall('TrackGroups/TrackGroup/Second'):
        group = resolve(ref)
        if group.tag == 'VideoTrackGroup':
            tracks.extend(resolve(t) for t in group.findall('TrackGroup/Tracks/Track')
                          if t.get('Index') == str(track_index))
    if len(tracks) != 1:
        raise ValueError('Exact unique caption track required')
    track = tracks[0]
    track_id = track.get('ObjectID') or track.get('ObjectUID')
    if sum(references(e,track) for e in root.iter()) != 1:
        raise ValueError('Shared track cannot be replaced')
    # A shared group can expose a singly-referenced track to several sequences.
    owners = [g for g in root if any(references(t,track)
              for t in g.findall('TrackGroup/Tracks/Track'))]
    if len(owners) != 1 or sum(references(e,owners[0])
                               for e in root.iter()) != 1:
        raise ValueError('Shared track group cannot be replaced')
    container = track.find('ClipTrack/ClipItems/TrackItems')
    if container is None and list(expected_old_item_ids) == []:
        # A track Premiere created but never populated saves ClipItems with only
        # MediaType/Index -- no TrackItems child at all. The profile contract already
        # allows `expected_item_ids: []`, so create the empty container (as the first
        # child, where Premiere writes it) instead of refusing a legitimately empty track.
        clip_items = track.find('ClipTrack/ClipItems')
        if clip_items is not None and all(e.tag in ('MediaType', 'Index') for e in clip_items):
            container = ET.Element('TrackItems', {'Version': '1'})
            clip_items.insert(0, container)
    if container is None or any(e.tag != 'TrackItem' for e in container):
        raise ValueError('Unsupported caption track container')
    old_ids = [e.get('ObjectRef') for e in container]
    if old_ids != list(expected_old_item_ids):
        raise ValueError('Caption track changed from expected state')
    new_ids = [r['item_id'] for r in receipts]
    if not new_ids or len(set(new_ids)) != len(new_ids):
        raise ValueError('Unique nonempty generated card list required')
    prior_end = -1
    for r in receipts:
        node = objects[r['item_id']]
        if node.tag != 'VideoClipTrackItem':
            raise ValueError('Generated object is not a video item')
        a = int(node.findtext('ClipTrackItem/TrackItem/Start'))
        b = int(node.findtext('ClipTrackItem/TrackItem/End'))
        if a < prior_end or b <= a:
            raise ValueError('Invalid generated interval order')
        if str(a) != r['timing']['start_ticks'] or str(b) != r['timing']['end_ticks']:
            raise ValueError('Generated interval differs from receipt')
        if any(e.get('ObjectRef') == r['item_id'] for e in root.iter()):
            raise ValueError('Generated item already has a consumer')
        prior_end = b
    for child in list(container):
        container.remove(child)
    for i, oid in enumerate(new_ids):
        ET.SubElement(container, 'TrackItem', {'Index': str(i), 'ObjectRef': oid})
    return dict(sequence_uid=sequence_uid, track_id=track_id,
                replaced_reference_count=len(old_ids), inserted_count=len(new_ids),
                originals_retained=True, native_verified=False)


def build_batch(root, plan, payloads):
    if not plan:
        raise ValueError('Nonempty card plan required')
    ids = [c['id'] for c in plan]
    if len(set(ids)) != len(ids):
        raise ValueError('Unique caption IDs required')
    result = copy.deepcopy(root)
    receipts = []
    previous_end = -1
    for card in plan:
        if card['start_ticks'] < previous_end:
            raise ValueError('Single caption lane must be ordered and nonoverlapping')
        cloned = clone_graph(result, card['donor_item_id'],
                             shared_ids=set(card['shared_ids']),
                             allowed_external_uids=set(card['external_uids']))
        timing = place_graph(cloned, start_ticks=card['start_ticks'], end_ticks=card['end_ticks'],
                             animation_elapsed_ticks=card.get('animation_elapsed_ticks', 0))
        params = [n for n in cloned['nodes'] if n.findtext('Name') == 'Source Text']
        if len(params) != 1:
            raise ValueError('Exactly one text layer required for this batch path')
        node = params[0].find('StartKeyframeValue')
        if node is None:
            raise ValueError('Missing text payload')
        old = base64.b64decode(node.text) if node.get('Encoding') == 'base64' and node.text else payloads[node.get('BinaryHash')]
        new = rebuild_runs(old, card['runs'])
        decoded = decode_runs(new)
        expected = ''.join(text for _, text in card['runs'])
        if ''.join(r['text'] for r in decoded) != expected:
            raise ValueError('Caption text failed independent decode')
        payload_id = str(uuid.uuid4())
        node.set('Encoding', 'base64')
        node.set('BinaryHash', payload_id)
        node.text = base64.b64encode(new).decode('ascii')
        result.extend(cloned['nodes'])
        receipts.append(dict(id=card['id'], item_id=cloned['seed_id'], timing=timing,
                             text=expected, payload_hash=payload_id,
                             object_count=len(cloned['nodes']), native_verified=False))
        previous_end = card['end_ticks']
    return result, receipts
