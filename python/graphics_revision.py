"""Pinned motion-asset replacement; editorial timing and other layers stay fixed."""
import copy
from pathlib import Path
from common import inside, require, sha, plan, fingerprint


def compare_plans(previous, current, targets):
    require(isinstance(targets,list) and targets and all(type(i)==int for i in targets) and len(set(targets))==len(targets), 'Select unique graphic indices')
    require({k:v for k,v in previous.items() if k!='graphics'}=={k:v for k,v in current.items() if k!='graphics'}, 'Graphic replacement preserves every other plan field')
    old,new=previous.get('graphics',[]),current.get('graphics',[])
    require(len(old)==len(new) and all(0<=i<len(old) for i in targets), 'Graphic order/count and target coverage must remain fixed')
    for i,(a,b) in enumerate(zip(old,new)):
        if i not in targets:
            require(a==b,'Unselected graphic changed');continue
        require({k:v for k,v in a.items() if k not in ['path','sha256']}=={k:v for k,v in b.items() if k not in ['path','sha256']}, 'Graphic replacement preserves placement and duration')
        require(a['path']!=b['path'] and a['sha256']!=b['sha256'], 'Use a new immutable asset with changed content')
    return targets


def prepare(project,packet):
    previous=inside(project['root'],packet['previousPlan'])
    require(sha(previous)==packet['previousPlanSha256'],'Previous published plan changed')
    old,new=plan(project,{'plan':str(previous)}),plan(project,packet)
    return old,new,compare_plans(old,new,packet['graphicIndices'])


def filmcraft_items(data,spec):
    seq=data['project']['items'][str(data['view']['active_sequence'])]['kind']['Sequence']
    ft=254016000000*spec['fps']['denominator']//spec['fps']['numerator'];items=[]
    for i,asset in enumerate(spec.get('graphics',[])):
        track=i+(4 if spec.get('captionContract') else 2)
        require(track<len(seq['video_tracks']),'Native graphic track missing')
        clips=seq['video_tracks'][track]['items'];require(len(clips)==1,'Native graphic track coverage changed')
        clip=clips[0];media=data['project']['items'][str(clip['item'])]['kind'].get('Media',{})
        require(Path(media.get('media',{}).get('File',{}).get('path','')).resolve()==Path(asset['path']).resolve(),'Native graphic source differs from pinned plan')
        require((clip['start'],clip['duration'],clip['source_in'])==(asset['startFrame']*ft,asset['frames']*ft,0),'Native graphic placement changed')
        items.append(clip)
    return items


def filmcraft_targets(data,spec,indices):
    items=filmcraft_items(data,spec)
    seq=data['project']['items'][str(data['view']['active_sequence'])]['kind']['Sequence']
    for i in indices:
        clip=items[i];track=seq['video_tracks'][i+(4 if spec.get('captionContract') else 2)]
        require(not track.get('locked') and clip.get('link') is None and clip.get('group') is None,'Graphic target is locked, linked or grouped; reconcile before replacement')
        require(clip.get('speed')==1 and not clip.get('reverse') and clip.get('frame_hold') is None and clip.get('multicam') is None,'Retimed/held/multicam graphic replacement is unsupported')
        remap=next((e for e in clip['effects'] if e['effect']=='time_remap'),None)
        require(remap and remap['params']['speed']=={'value':{'Float':100.0}},'Animated graphic retiming requires a separate operation')
    return [items[i] for i in indices]


def verify_filmcraft_replacement(before,after,previous,current,indices,destination):
    old_items=filmcraft_targets(before,previous,indices);new_items=filmcraft_items(after,current)
    expected=copy.deepcopy(before['project']);actual=copy.deepcopy(after['project'])
    expected['name']=destination;expected['root']['name']=destination
    added=set(actual['items'])-set(expected['items'])
    require(len(added)==len(indices) and set(expected['items'])<=set(actual['items']),'Replacement must import exactly one new item per selected graphic')
    require(actual['next_id']==expected['next_id']+len(added) and added=={str(i) for i in range(expected['next_id'],actual['next_id'])},'Unexpected native ID allocation during graphic replacement')
    imported=[]
    for index,old in zip(indices,old_items):
        new=new_items[index];key=str(new['item']);require(key in added and key not in imported,'Replacement did not bind a unique new media item');imported.append(key)
        media=actual['items'][key];require(media['kind'].get('Media') and media['id']==new['item'],'Replacement source is not native media')
        require(media['label']==old['label'],'Replacement changed the clip label')
        target=next(c for t in expected['items'][str(before['view']['active_sequence'])]['kind']['Sequence']['video_tracks'] for c in t['items'] if c['id']==old['id'])
        target['item']=new['item']
        # The import is permitted; every pre-existing item and bin entry is protected.
        expected['items'][key]=copy.deepcopy(media)
    expected['root']['children'] += [{'Item':int(i)} for i in imported]
    expected['next_id']=actual['next_id']
    require(before['view']['active_sequence']==after['view']['active_sequence'] and fingerprint(expected)==fingerprint(actual),'Graphic replacement changed protected native state')
