#!/usr/bin/env python3
"""Deterministic auxiliary-track transport; no speech selection or media mutation."""
import sys,json,copy
from pathlib import Path
from urllib.parse import quote
import xml.etree.ElementTree as ET
T=254016000000

def build(xml,expected,coverage):
 root=ET.fromstring(xml);seq=root.find('sequence');video=seq.find('media/video');audio=seq.find('media/audio');e=json.loads(expected);ft=int(e['frame_ticks']);items=e['items'];out=[]
 for si,source in enumerate(coverage['sources']):
  camera=source['kind']=='camera';vi=si+1 if camera else None;ai=si+1
  vt=ET.SubElement(video,'track') if camera else None;at=ET.SubElement(audio,'track');offset=int(source['delta_ticks']);fileid=f'coverage-file-{si}';definition=False
  for i,w in enumerate(items):
   a=int(w['source_in_ticks'])+offset;b=int(w['source_out_ticks'])+offset
   if a<int(source['in_ticks']) or b>int(source['out_ticks']):raise ValueError('Coverage outside intact RAW source occurrence')
   af=a//ft;bf=af+(int(w['end_ticks'])-int(w['start_ticks']))//ft;vid=f'coverage-v-{si}-{i}';aid=f'coverage-a-{si}-{i}'
   peers=[(vid,'video',vi+1)] if camera else [];peers.append((aid,'audio',ai+1))
   # Two standalone WAV tracks form a reciprocal audio-only pair.
   if not camera:peers.append((f'coverage-a-{5 if si==4 else 4}-{i}','audio',7 if si==4 else 6))
   for kind,track,cid in ([('video',vt,vid)] if camera else [])+[('audio',at,aid)]:
    c=ET.SubElement(track,'clipitem',id=cid)
    for k,val in [('name',Path(source['media_path']).name),('enabled','FALSE'),('duration',(int(w['end_ticks'])-int(w['start_ticks']))//ft),('start',int(w['start_ticks'])//ft),('end',int(w['end_ticks'])//ft),('in',af),('out',bf)]:ET.SubElement(c,k).text=str(val)
    file=ET.SubElement(c,'file',id=fileid)
    if not definition:
     definition=True;ET.SubElement(file,'name').text=Path(source['media_path']).name;ET.SubElement(file,'pathurl').text='file://localhost'+quote(source['media_path']);ET.SubElement(file,'duration').text=str(source['duration_frames']);rate=ET.SubElement(file,'rate');ET.SubElement(rate,'timebase').text='24';ET.SubElement(rate,'ntsc').text='TRUE';m=ET.SubElement(file,'media')
     if camera:
      v=ET.SubElement(m,'video');sc=ET.SubElement(v,'samplecharacteristics');ET.SubElement(sc,'width').text=str(source['width']);ET.SubElement(sc,'height').text=str(source['height']);r=ET.SubElement(sc,'rate');ET.SubElement(r,'timebase').text='24';ET.SubElement(r,'ntsc').text='TRUE';ET.SubElement(sc,'pixelaspectratio').text='square';ET.SubElement(sc,'fielddominance').text='none'
     au=ET.SubElement(m,'audio');sc=ET.SubElement(au,'samplecharacteristics');ET.SubElement(sc,'depth').text='24';ET.SubElement(sc,'samplerate').text='48000';ET.SubElement(sc,'channelcount').text=str(source['channels']);ET.SubElement(au,'channelcount').text=str(source['channels'])
    if kind=='audio':st=ET.SubElement(c,'sourcetrack');ET.SubElement(st,'mediatype').text='audio';ET.SubElement(st,'trackindex').text='1'
    for ref,k,t in peers:
     link=ET.SubElement(c,'link');ET.SubElement(link,'linkclipref').text=ref;ET.SubElement(link,'mediatype').text=k;ET.SubElement(link,'trackindex').text=str(t);ET.SubElement(link,'clipindex').text=str(i+1)
     if k=='audio':ET.SubElement(link,'groupindex').text='1'
    out.append({'kind':kind,'track_index':vi if kind=='video' else ai,'item_index':i,'media_path':source['media_path'],'start_ticks':w['start_ticks'],'end_ticks':w['end_ticks'],'source_in_ticks':str(a),'source_out_ticks':str(b),'import_source_in_ticks':str(af*ft),'import_source_out_ticks':str(bf*ft),'disabled':True,'peer_tracks':[{'kind':k,'track_index':t-1} for ref,k,t in peers if ref!=cid]})
 return ET.tostring(root,encoding='unicode'),out
if __name__=='__main__':
 x,e,c,o=sys.argv[1:];xml,items=build(Path(x).read_text(),Path(e).read_text(),json.loads(Path(c).read_text()));Path(o).write_text(xml);print(json.dumps({'items':items}))
