#!/usr/bin/env python3
"""Bind prepared headline lanes to the complete independently inspected edit.

The caption owner performs text/timing verification and native transfer. This
only declares the unchanged base structure plus its two new headline lanes.
"""
import argparse
import json
from pathlib import Path
import sys


def run(a):
    sys.path.insert(0,str(a.skills/'caption-clips/scripts'))
    import premiere_native_cards as native
    from premiere_caption_handoff import prepare,sha
    read=lambda p:json.loads(Path(p).read_text())
    prep=read(a.preparation);snapshot=read(a.snapshot);full=read(a.full)['data']
    if full['id']!=snapshot['sequenceId'] or sha(prep['source']['path'])!=prep['source']['sha256'] or sha(prep['prepared']['path'])!=prep['prepared']['sha256']:raise ValueError('Native baseline or prepared file changed')
    a.output.mkdir();tracks=[]
    for t in snapshot['tracks']:
        kind='video' if t['kind']==0 else 'audio'
        raw=next(v for v in full[kind+'Tracks'] if v['index']==t['index'])
        if raw['name']!=t['name'] or len(raw['clips'])!=len(t['clips']) or raw['transitionCount']:raise ValueError('Native inspection surfaces differ')
        items=[]
        for c,d in zip(t['clips'],raw['clips']):
            if c['id']!=d['nodeId'] or c['start']!=d['startTicks'] or c['end']!=d['endTicks'] or c['inPoint']!=d['inPointTicks'] or c['outPoint']!=d['outPointTicks']:raise ValueError('Independent native clip clocks differ')
            path=d.get('sourceMediaPath');graphic=not path
            chain=[v['matchName'] for v in c['components']]
            if graphic and chain.count('AE.ADBE Text')!=1:raise ValueError('Unsupported generated media')
            items.append({'token':'preserved-'+c['id'],'source_kind':'graphic' if graphic else 'media','media_path':path or None,
                          'start_ticks':c['start'],'end_ticks':c['end'],'source_in_ticks':c['inPoint'],'source_out_ticks':c['outPoint'],
                          'speed':c['speed'],'speed_reversed':bool(d['reversed']),'disabled':c['disabled'],'component_match_names':chain})
        tracks.append({'kind':kind,'index':t['index'],'name':t['name'],'muted':t['muted'],'locked':t['locked'],'items':items})
    receipts=[]
    for i,line in enumerate(prep['lines']):
        r=read(line['receipt']);r['sequence_uid']=prep['sequence_uid'];r['target']=prep['prepared']['path']
        receipt=a.output/f'line-{i+1}.receipt.json';receipt.write_text(json.dumps(r,indent=2))
        native.verify(prep['prepared']['path'],receipt)
        manifest=Path(line['receipt']).parent/'manifest.json'
        handoff=prepare(prep['prepared']['path'],receipt,manifest,native)
        receipts.append({'receipt':str(receipt),'manifest':str(manifest),'handoff':handoff})
        items=[]
        for card in r['cards']:
            items.append({'token':card['id'],'source_kind':'graphic','media_path':None,
                          **{k:card['timing'][k] for k in ('start_ticks','end_ticks','source_in_ticks','source_out_ticks')},
                          'speed':1,'speed_reversed':False,'disabled':False,
                          'component_match_names':['AE.ADBE Opacity','AE.ADBE Motion','AE.ADBE Graphic Group','AE.ADBE Geometry2','AE.ADBE Text']})
        tracks.append({'kind':'video','index':r['track_index'],'name':f"Video {r['track_index']+1}",'muted':False,'locked':False,'items':items})
    tracks.sort(key=lambda t:({'video':0,'audio':1}[t['kind']],t['index']))
    expectation={'sequence_id':prep['sequence_uid'],'sequence_name':r['sequence_name'],'width':full['width'],'height':full['height'],'frame_duration_ticks':str(full['frameRate']['ticks']),'tracks':tracks,'markers':snapshot['markers']}
    structure={'schema':'edit.caption-transfer-structure/v1','prepared_sha256':prep['prepared']['sha256'],'expectation':expectation}
    path=a.output/'structure.json';path.write_text(json.dumps(structure,indent=2))
    result={'project':prep['prepared']['path'],'receipt':receipts[-1]['receipt'],'manifest':receipts[-1]['manifest'],'structure':str(path),'allLines':receipts,'native':'not_imported','userApproved':False}
    (a.output/'prepared-transfer.json').write_text(json.dumps(result,indent=2))
    return {k:v for k,v in result.items() if k!='allLines'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('skills','preparation','snapshot','full','output'):p.add_argument('--'+name,type=Path,required=True)
    print(json.dumps(run(p.parse_args()),indent=2))
