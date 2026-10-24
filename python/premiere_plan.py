"""Bind planned dialogue cuts to read-only native Premiere source/link evidence.

Assembly Design owns the selection. This checks direct source-linked V1/A1
execution; it neither designs cuts nor infers linkage from coincident timing.
"""
import re
from fractions import Fraction
from pathlib import Path
from common import require, fingerprint


def exact_ticks(value):
    require(isinstance(value,str) and re.fullmatch(r'0|[1-9][0-9]{0,18}',value) and int(value)<=9223372036854775807,'Premiere native ticks are not exact unsigned tick strings')
    return int(value)


def verify_source_cuts(spec,snapshot,links):
    require(isinstance(links,dict) and links.get('project_path')==snapshot['projectPath'] and links.get('sequence_id')==snapshot['sequenceId'],'Native source inspection targets another project or sequence')
    require(links.get('verification') in ['stable_native_link_membership','stable_complete_paged_native_link_membership'],'Stable native link readback required; inferred linkage is insufficient')
    frame=Fraction(254016000000*spec['fps']['denominator'],spec['fps']['numerator']);sample=Fraction(254016000000,spec['sampleRate'])
    require(frame.denominator==sample.denominator==1,'Premiere source clocks require exact frame/sample ticks')
    frame,sample=int(frame),int(sample)
    require(exact_ticks(links['frame_duration_ticks'])==frame,'Native source frame grid differs from the plan')
    sources={s['id']:Path(s['path']).resolve() for s in spec['sources']}
    rows=links.get('items');require(isinstance(rows,list),'Native source item inventory missing')
    ids=set();positions=set();native={}
    for row in rows:
        key=(row['kind'],row['track_index'],row['item_index']);node=row['item']['node_id']
        require(row['kind'] in ['video','audio'] and type(row['track_index']) is int and row['track_index']>=0 and type(row['item_index']) is int and row['item_index']>=0,'Native source position is invalid')
        require(isinstance(node,str) and bool(node) and node not in ids and key not in positions,'Native source inventory has duplicate identities or positions')
        ids.add(node);positions.add(key);native[key]=row
    expected={}
    for kind,kind_id in [('video',0),('audio',1)]:
        tracks=[t for t in snapshot['tracks'] if t['kind']==kind_id and t['index']==0]
        require(len(tracks)==1 and tracks[0]['muted'] is False,'Planned picture/dialogue track is missing or muted')
        clips=tracks[0]['clips'];selected=[row for row in rows if row['kind']==kind and row['track_index']==0]
        require(len(clips)==len(selected)==len(spec['cuts']),'Native picture/dialogue cut coverage differs from the plan')
        for i,(cut,clip) in enumerate(zip(spec['cuts'],clips)):
            row=native.get((kind,0,i));require(row is not None,'Native source item order differs')
            item=row['item'];source_id=cut['sourceId'] if kind=='video' else cut.get('audioSourceId',cut['sourceId'])
            require(item.get('source_id') and item.get('media_path') and Path(item['media_path']).is_absolute() and Path(item['media_path']).resolve()==sources[source_id] and item.get('offline') is False,'Native cut source differs or is offline: '+cut['id']+' '+kind)
            require(item.get('speed')==1 and item.get('speed_reversed') is False and item.get('disabled') is False,'Native cut is retimed, reversed or disabled: '+cut['id']+' '+kind)
            start=cut['recordFrame']*frame if kind=='video' or 'audioRecordSample' not in cut else cut['audioRecordSample']*sample
            source_in=cut['sourceInFrame']*frame if kind=='video' else cut['audioInSample']*sample
            duration=cut['frames']*frame if kind=='video' else cut['audioSamples']*sample
            wanted=(start,start+duration,source_in,source_in+duration)
            actual=tuple(exact_ticks(item[k]) for k in ['start_ticks','end_ticks','source_in_ticks','source_out_ticks'])
            require(actual==wanted,'Native source or record clocks differ from the plan: '+cut['id']+' '+kind)
            require(clip['id']==item['node_id'] and clip['sourceId']==item['source_id'] and tuple(exact_ticks(clip[k]) for k in ['start','end','inPoint','outPoint'])==actual,'Native snapshot and source inspection disagree')
            require(clip.get('speed')==1 and clip.get('disabled') is False,'Native snapshot cut playback differs')
            expected[(kind,i)]=row
    mapping=[]
    for i,cut in enumerate(spec['cuts']):
        v,a=expected[('video',i)],expected[('audio',i)]
        require(v['linked_node_ids']==[a['item']['node_id']] and a['linked_node_ids']==[v['item']['node_id']],'Native picture/dialogue pair is not exclusively and reciprocally linked: '+cut['id'])
        mapping.append({'cutId':cut['id'],'videoNodeId':v['item']['node_id'],'audioNodeId':a['item']['node_id'],'pictureSourceId':cut['sourceId'],'audioSourceId':cut.get('audioSourceId',cut['sourceId'])})
    return {'schema':'acq-edit/premiere-source-cuts-v1','projectPath':snapshot['projectPath'],'sequenceId':snapshot['sequenceId'],'snapshotRevision':snapshot['revision'],'cutsFingerprint':fingerprint(spec['cuts']),'nativeLinksFingerprint':fingerprint(links),'mapping':mapping,'qualification':'direct native V1/A1 sources, exact clocks and links; not speech listening or finishing approval'}
