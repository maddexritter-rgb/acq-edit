"""Inspect native Resolve music bindings, clocks, metadata and channel routing."""
import json
from pathlib import Path
from common import require
from audio_plan import resolve_music_frames, same_native_frame
from resolve_graphics import inspect as inspect_timeline, fresh_paths


def source(spec, index):
    bed = spec['audio']['music'][index]
    return next(s for s in spec['sources'] if s['id'] == bed['sourceId'])


def items(timeline, spec, targets=()):
    clips = timeline.GetItemListInTrack('audio', 2) or []
    beds = spec.get('audio', {}).get('music', [])
    require(len(clips) == len(beds), 'Native music coverage changed')
    for index, (item, bed) in enumerate(zip(clips, beds)):
        timing = resolve_music_frames(spec, bed)
        media = item.GetMediaPoolItem()
        require(media and Path(media.GetClipProperty('File Path')).resolve() == Path(source(spec, index)['path']).resolve(),
                'Native music source differs from pinned plan')
        require(all(same_native_frame(a, b) for a, b in zip(
                (item.GetStart(True), item.GetDuration(True), item.GetLeftOffset(True)),
                (bed['startFrame'], timing['samples'], timing['sourceInSample']))), 'Native music timing changed')
        if index in targets:
            require(not timeline.GetIsTrackLocked('audio', 2) and not item.GetLinkedItems(), 'Music target is locked or linked')
            require(item.GetTakesCount() is None and item.GetSelectedTakeIndex() is None, 'Unexpected audio take API state; reconcile for this Resolve version')
            require(item.GetFusionCompCount() == 0, 'Music with a Fusion composition requires a dedicated revision')
            require(item.GetSourceStartFrame() == timing['sourceInSample'] and
                    item.GetSourceEndFrame() == timing['sourceInSample'] + timing['samples'],
                    'Retimed music source extent differs from placement')
    return clips


def inspect(adapter, project, duplicate=False, indices=()):
    detail = inspect_timeline(adapter, project, duplicate, [('audio', 1, i) for i in indices])
    timeline = project.GetCurrentTimeline()
    detail['audioMappings'] = {
        f'{track}:{index}': json.loads(item.GetSourceAudioChannelMapping())
        for track in range(1, timeline.GetTrackCount('audio') + 1)
        for index, item in enumerate(timeline.GetItemListInTrack('audio', track) or [])
    }
    return detail


def fresh_media(pool, spec, indices):
    fresh_paths(pool, [source(spec, i)['path'] for i in indices])
