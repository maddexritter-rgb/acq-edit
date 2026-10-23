"""Canvas geometry for native caption Graphics.

A Premiere Graphic records its canvas in more than one place, and only the text
layer Position is normalized:

  * Source Text paragraph box (document fields 2/3) -- absolute pixels;
  * the Graphic's synthetic media, Media > VideoStream > FrameRect -- absolute
    pixels. The Program Monitor edit box and click hit-test are mapped through it;
  * the sequence's own VideoTrackGroup FrameRect -- the target canvas.

A donor authored on one canvas and cloned onto another therefore renders
off-centre (box) and cannot be clicked to edit (media frame), while every
text/run/timing readback still passes. These helpers make that geometry explicit
so the builder and verifier can fail closed on it instead of checking a written
position against itself.
"""
from .decode_graphic_text import document_box

# Rendered centre must land within this many pixels of the intended centre.
CENTER_TOLERANCE_PX = 2.0


def parse_rect(text):
    parts = [float(p) for p in str(text).split(',')]
    if len(parts) != 4:
        raise ValueError(f'Unknown FrameRect {text!r}')
    width, height = parts[2] - parts[0], parts[3] - parts[1]
    if width <= 0 or height <= 0:
        raise ValueError(f'Empty FrameRect {text!r}')
    return int(round(width)), int(round(height))


def _index(root):
    ids = {n.get('ObjectID'): n for n in root if n.get('ObjectID')}
    uids = {n.get('ObjectUID'): n for n in root if n.get('ObjectUID')}

    def resolve(element):
        if element.get('ObjectRef'):
            return ids.get(element.get('ObjectRef'))
        if element.get('ObjectURef'):
            return uids.get(element.get('ObjectURef'))
        return None
    return ids, uids, resolve


def sequence_canvas(root, sequence_uid):
    """(width, height) of a sequence, read from its VideoTrackGroup FrameRect."""
    _, uids, resolve = _index(root)
    sequence = uids.get(sequence_uid)
    if sequence is None or sequence.tag != 'Sequence':
        raise ValueError('Sequence identity required for canvas')
    rects = set()
    for ref in sequence.findall('TrackGroups/TrackGroup/Second'):
        group = resolve(ref)
        if group is not None and group.tag == 'VideoTrackGroup':
            # Saved as a direct child of VideoTrackGroup (observed on Premiere 26 saves).
            text = group.findtext('FrameRect') or group.findtext('TrackGroup/FrameRect')
            if text:
                rects.add(parse_rect(text))
    if len(rects) != 1:
        raise ValueError('Target sequence has no unique video FrameRect; cannot verify caption canvas')
    return rects.pop()


def graphic_media(root, item):
    """(media_node, [video_stream_nodes]) behind a Graphic track item."""
    ids, _, resolve = _index(root)
    sub = ids.get(item.find('ClipTrackItem/SubClip').get('ObjectRef'))
    clip = ids.get(sub.find('Clip').get('ObjectRef'))
    source = ids.get(clip.find('Clip/Source').get('ObjectRef'))
    media = None
    for element in source.iter():
        target = resolve(element) if element is not source else None
        if target is not None and target.tag == 'Media':
            media = target
            break
    if media is None:
        raise ValueError('Graphic has no synthetic media; cannot verify its canvas')
    streams = []
    for element in media.iter():
        target = resolve(element) if element is not media else None
        if target is not None and target.tag == 'VideoStream':
            streams.append(target)
    if not streams:
        raise ValueError('Graphic media has no VideoStream; cannot verify its canvas')
    return media, streams


def media_canvas(root, item):
    rects = {parse_rect(s.findtext('FrameRect')) for s in graphic_media(root, item)[1]
             if s.findtext('FrameRect')}
    if len(rects) != 1:
        raise ValueError('Graphic media has no unique FrameRect')
    return rects.pop()


def media_consumers(root, media):
    """Track items (other than via this media) that share a Graphic media node."""
    ids, uids, resolve = _index(root)
    key = media.get('ObjectUID') or media.get('ObjectID')
    sources = {n.get('ObjectID') for n in root
               if n.get('ObjectID') and any((e.get('ObjectURef') or e.get('ObjectRef')) == key
                                            for e in n.iter())}
    clips = {n.get('ObjectID') for n in root
             if n.get('ObjectID') and n.find('Clip/Source') is not None
             and n.find('Clip/Source').get('ObjectRef') in sources}
    subs = {n.get('ObjectID') for n in root
            if n.get('ObjectID') and n.find('Clip') is not None and n.find('Clip').get('ObjectRef') in clips}
    return [n.get('ObjectID') for n in root
            if n.tag == 'VideoClipTrackItem' and n.find('ClipTrackItem/SubClip') is not None
            and n.find('ClipTrackItem/SubClip').get('ObjectRef') in subs]


def geometry_problems(*, canvas, media, position, box, mode, y_pct):
    """Independent geometry gate for one caption graphic.

    `canvas` is the target sequence, `media` the Graphic's media frame, `position`
    the normalized text-layer Position, `box` the paragraph (width, height) or None
    for point text. The intended centre comes from the profile (x=0.5, y=y_pct), never
    from the graphic itself, so a wrong donor cannot vouch for its own position.
    `y_pct=None` (a legacy receipt with no recorded intent) still checks the media
    frame and that the box fits, but cannot check the centre.
    """
    width, height = canvas
    problems = []
    check_centre = y_pct is not None
    if tuple(media) != tuple(canvas):
        problems.append(f'graphic media is {media[0]}x{media[1]} but the sequence is {width}x{height}: '
                        'the Program Monitor edit box and click target are drawn through the media frame '
                        'and land off the text. Retarget the donor with retarget_native_donor.py')
    want_x = 0.5 * width
    want_y = float(y_pct) / 100.0 * height if check_centre else None
    if box is None:
        if mode == 'donor' and check_centre:
            got_x, got_y = position[0] * width, position[1] * height
            if abs(got_x - want_x) > CENTER_TOLERANCE_PX or abs(got_y - want_y) > CENTER_TOLERANCE_PX:
                problems.append(f'point-text anchor at ({got_x:.1f},{got_y:.1f})px, intended ({want_x:.1f},{want_y:.1f})px')
        return problems
    box_w, box_h = box
    if box_w > width + 0.5 or box_h > height + 0.5:
        problems.append(f'paragraph box {box_w:g}x{box_h:g}px is larger than the {width}x{height} frame '
                        '(authored on a bigger canvas); retarget the donor with retarget_native_donor.py')
    if mode != 'donor':
        problems.append('paragraph-box donor in explicit_centered mode: Position is the box top-left, so '
                        'forcing it to x=0.5 puts the box origin at the frame centre')
        return problems
    left, top = position[0] * width, position[1] * height
    got_x, got_y = left + box_w / 2.0, top + box_h / 2.0
    if check_centre and (abs(got_x - want_x) > CENTER_TOLERANCE_PX
                         or abs(got_y - want_y) > CENTER_TOLERANCE_PX):
        problems.append(f'text box centre renders at ({got_x:.1f},{got_y:.1f})px, intended '
                        f'({want_x:.1f},{want_y:.1f})px on {width}x{height}')
    if left < -0.5 or top < -0.5 or left + box_w > width + 0.5 or top + box_h > height + 0.5:
        problems.append(f'text box ({left:.1f},{top:.1f},{box_w:g}x{box_h:g}) extends off the {width}x{height} frame')
    return problems


def payload_box(payload_bytes):
    return document_box(payload_bytes)
