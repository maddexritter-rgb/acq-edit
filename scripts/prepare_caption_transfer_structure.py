#!/usr/bin/env python3
"""Bind a caption builder's new lane to the inspected pre-build native structure.
Existing track source clocks come from two native read surfaces. New caption
clocks come from the caption owner's receipt. Import must verify the result.
"""
import argparse,json,hashlib
from pathlib import Path

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('snapshot','full','prepared','receipt','output'):p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--graphic-components',nargs='+',required=True);a=p.parse_args();read=lambda p:json.loads(p.read_text());s=read(a.snapshot);full=read(a.full);r=read(a.receipt)
 if s['sequenceId']!=full['id']:raise ValueError('Native read surfaces differ')
 tracks=[]
 for track in s['tracks']:
  kind='video' if track['kind']==0 else 'audio';raw=next(t for t in full[kind+'Tracks'] if t['index']==track['index']);items=[]
  if len(track['clips'])!=len(raw['clips']):raise ValueError('Native item counts differ')
  for c,d in zip(track['clips'],raw['clips']):
   if c['id']!=d['nodeId'] or c['sourceId']!=d['sourceNodeId']:raise ValueError('Native item identity differs')
   row={'token':kind+'-'+c['id'],'source_kind':'media','media_path':d['sourceMediaPath'],'speed':c['speed'],'speed_reversed':bool(d['reversed']),'disabled':bool(c['disabled']),'component_match_names':[f['matchName'] for f in c['components']]}
   for target,field,other in [('start_ticks','start','startTicks'),('end_ticks','end','endTicks'),('source_in_ticks','inPoint','inPointTicks'),('source_out_ticks','outPoint','outPointTicks')]:
    if c[field]!=d[other]:raise ValueError('Native clock readback differs')
    row[target]=c[field]
   items.append(row)
  tracks.append({'kind':kind,'index':track['index'],'name':track['name'],'muted':bool(track['muted']),'locked':bool(track['locked']),'items':items})
 index=r['track_index']
 if index!=len([t for t in tracks if t['kind']=='video']):raise ValueError('New caption lane must append to unchanged video lanes')
 items=[{'token':c['id'],'source_kind':'graphic','media_path':None,'speed':1,'speed_reversed':False,'disabled':False,'component_match_names':a.graphic_components,**{k:c['timing'][k] for k in ('start_ticks','end_ticks','source_in_ticks','source_out_ticks')}} for c in r['cards']]
 tracks.append({'kind':'video','index':index,'name':'Video '+str(index+1),'muted':False,'locked':False,'items':items})
 result={'schema':'edit.caption-transfer-structure/v1','prepared_sha256':hashlib.sha256(a.prepared.read_bytes()).hexdigest(),'expectation':{'sequence_id':r['sequence_uid'],'sequence_name':r['sequence_name'],'width':full['width'],'height':full['height'],'frame_duration_ticks':full['frameRate']['ticks'],'tracks':tracks,'markers':s['markers']}}
 with a.output.open('x') as f:json.dump(result,f,indent=2)
 print(json.dumps({'tracks':len(tracks),'captionStates':len(items),'status':'declared-awaiting-native-verification'}))
if __name__=='__main__':main()
