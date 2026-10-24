"""Remove only a verified owned hook before measuring a fresh finishing layout.

The source plan remains immutable. The hook-free intermediate is a new native
checkpoint; changing other layers is a separate owning-skill operation.
"""
import copy
from common import inside,sha,plan,require,fingerprint
from hook_plan import validate,verify_native


def compare_plans(previous,current):
    require(previous.get('hookContract') and 'hookContract' not in current,'Hook removal requires an existing contract and a hook-free plan')
    require({k:v for k,v in previous.items() if k!='hookContract'}==current,'Hook removal cannot change cuts, captions, framing, audio, graphics or other plan fields')


def prepare(project,packet):
    path=inside(project['root'],packet['previousPlan'])
    require(sha(path)==packet['previousPlanSha256'],'Previous hook plan changed')
    previous=plan(project,{'plan':str(path)});current=plan(project,packet)
    compare_plans(previous,current)
    return previous,current,validate(project,previous)


def filmcraft_target(data,previous,prepared,frame_ticks):
    verify_native(data,previous,prepared,frame_ticks)
    seq=data['project']['items'][str(data['view']['active_sequence'])]['kind']['Sequence']
    require(len(seq['video_tracks'])>1,'Cannot remove the only picture track')
    target=seq['video_tracks'][-1]
    require(not target['locked'],'Owned hook track is locked; reconcile before removal')
    return target['id']


def verify_filmcraft(before,after,previous,prepared,destination,frame_ticks):
    track=filmcraft_target(before,previous,prepared,frame_ticks)
    require(before['view']['active_sequence']==after['view']['active_sequence'],'Hook removal changed active sequence')
    expected=copy.deepcopy(before['project']);actual=after['project']
    seq=expected['items'][str(before['view']['active_sequence'])]['kind']['Sequence']
    require(seq['video_tracks'].pop()['id']==track,'Hook target changed')
    expected['name']=expected['root']['name']=destination
    # Retain bin assets, ID allocation, all other tracks, custom effects and
    # metadata. The native command removes exactly one timeline track.
    require(fingerprint(expected)==fingerprint(actual),'Hook removal changed protected native state')
