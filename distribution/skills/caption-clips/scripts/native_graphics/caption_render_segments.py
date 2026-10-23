"""Partition semantic caption cards at cuts without erasing their display holds.

One semantic card owns its words once. Its render segments repeat that already
revealed text across a shot boundary, with an explicit animation offset. This
does not approve timing, speech, or a card that already contains future words.
"""
from copy import deepcopy

def partition(cards, cut_frames):
    cuts=sorted(set(cut_frames))
    if any(type(c) is not int or c<0 for c in cuts):raise ValueError('Invalid cut frame')
    segments=[];ids=set();prior_end=0
    for card in cards:
        cid=card['id'];start=card['start_frame'];end=card['end_frame']
        if cid in ids or type(start) is not int or type(end) is not int or start<prior_end or end<=start:
            raise ValueError('Unique, ordered, nonoverlapping positive cards required')
        ids.add(cid);prior_end=end
        boundaries=[start]+[c for c in cuts if start<c<end]+[end]
        for i,(a,b) in enumerate(zip(boundaries,boundaries[1:])):
            segment=deepcopy(card)
            segment.update(id=f'{cid}/segment-{i+1}',semantic_card_id=cid,
                           start_frame=a,end_frame=b,
                           animation_elapsed_frames=a-start,
                           continuation=i>0,source_coverage_owner=i==0)
            segments.append(segment)
        if sum(b-a for a,b in zip(boundaries,boundaries[1:]))!=end-start:
            raise AssertionError('Partition changed visible duration')
    return segments
