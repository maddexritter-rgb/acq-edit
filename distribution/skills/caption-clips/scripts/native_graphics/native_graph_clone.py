"""Clone explicitly selected Premiere object graphs without modifying originals.

Shared boundaries must be declared by object ID, never guessed by tag. The
caller still owns source clocks, text payloads, timeline insertion and validation.
"""
import copy
import uuid
import xml.etree.ElementTree as ET


def place_graph(cloned, *, start_ticks, end_ticks, animation_elapsed_ticks=0):
    """Place an isolated synthetic graphic while retaining its source-clock keys.

    Does not stretch animation to fit duration. Short cards may end during the
    entrance; source availability and native rendering still require validation.
    """
    if (type(start_ticks) is not int or type(end_ticks) is not int
            or start_ticks < 0 or end_ticks <= start_ticks):
        raise ValueError('Positive integer-tick interval required')
    if type(animation_elapsed_ticks) is not int or animation_elapsed_ticks < 0:
        raise ValueError('Nonnegative integer animation elapsed ticks required')
    nodes = {n.get('ObjectID'): n for n in cloned['nodes']}
    item = nodes[cloned['seed_id']]
    if item.tag != 'VideoClipTrackItem':
        raise ValueError('Graphic video track item required')
    clip_item = item.find('ClipTrackItem')
    subclip = nodes[clip_item.find('SubClip').get('ObjectRef')]
    clip = nodes[subclip.find('Clip').get('ObjectRef')]
    if clip.tag != 'VideoClip':
        raise ValueError('Isolated video clip required')
    source_in = int(clip.findtext('Clip/InPoint'))
    donor_source_in = source_in
    old_out = int(clip.findtext('Clip/OutPoint'))
    source_in += animation_elapsed_ticks
    duration = end_ticks-start_ticks
    # Resolve all required fields before mutation; no source/media object edits.
    start_node = clip_item.find('TrackItem/Start')
    track_item = clip_item.find('TrackItem')
    end_node = clip_item.find('TrackItem/End')
    out_node = clip.find('Clip/OutPoint')
    in_node = clip.find('Clip/InPoint')
    id_node = clip.find('Clip/ClipID')
    if any(n is None for n in (track_item,end_node,in_node,out_node,id_node)):
        raise ValueError('Incomplete native clip timing fields')
    # Premiere omits an explicit Start when a saved item begins at tick zero.
    if start_node is None:
        start_node = ET.SubElement(track_item, 'Start')
    start_node.text, end_node.text = str(start_ticks), str(end_ticks)
    in_node.text = str(source_in)
    out_node.text = str(source_in+duration)
    id_node.text = str(uuid.uuid4())
    return dict(start_ticks=str(start_ticks), end_ticks=str(end_ticks),
                source_in_ticks=str(source_in), source_out_ticks=str(source_in+duration),
                donor_duration_ticks=str(old_out-donor_source_in),
                animation_elapsed_ticks=str(animation_elapsed_ticks),
                animation_policy='RETAIN_SOURCE_CLOCK_NO_STRETCH',
                native_verified=False)


def clone_graph(root, seed_id, *, shared_ids, allowed_external_uids):
    nodes = {n.get('ObjectID'): n for n in root if n.get('ObjectID') is not None}
    if len(nodes) != sum(n.get('ObjectID') is not None for n in root):
        raise ValueError('Duplicate object IDs')
    if seed_id not in nodes or seed_id in shared_ids:
        raise ValueError('Seed must be a unique cloned object')
    if not set(shared_ids) <= nodes.keys():
        raise ValueError('Unknown shared boundary')
    pending, visited = [seed_id], set()
    while pending:
        oid = pending.pop()
        if oid in visited or oid in shared_ids:
            continue
        if oid not in nodes:
            raise ValueError('Dangling object reference: '+oid)
        node = nodes[oid]
        if node.get('ObjectUID'):
            raise ValueError('UID-bearing clone requires explicit UID remapping')
        visited.add(oid)
        for element in node.iter():
            if element.get('ObjectURef') not in (None, *allowed_external_uids):
                raise ValueError('Undeclared UID reference')
            if element.get('ObjectRef'):
                pending.append(element.get('ObjectRef'))
    if any(not oid.isdecimal() for oid in nodes):
        raise ValueError('Numeric object IDs required')
    first = max(map(int, nodes), default=0)+1
    mapping = {oid: str(first+i) for i,oid in enumerate(sorted(visited, key=int))}
    clones = []
    for oid in sorted(visited, key=int):
        node = copy.deepcopy(nodes[oid])
        node.set('ObjectID', mapping[oid])
        for element in node.iter():
            ref = element.get('ObjectRef')
            if ref in mapping:
                element.set('ObjectRef', mapping[ref])
        clones.append(node)
    return dict(seed_id=mapping[seed_id], mapping=mapping, nodes=clones,
                shared_ids=sorted(shared_ids), external_uids=sorted(allowed_external_uids))
