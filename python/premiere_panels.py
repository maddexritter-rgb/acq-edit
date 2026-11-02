"""Execute and verify frozen two-camera split decisions in native Premiere.

The framing owner supplies measured source-local curves. This module never chooses
cameras, tracks faces, changes source words or substitutes rendered media.
"""
from fractions import Fraction
from pathlib import Path
import copy, math, struct
from common import require


def near(a,b):
    if isinstance(b,list):return isinstance(a,list) and len(a)==len(b) and all(near(x,y) for x,y in zip(a,b))
    return type(a) in (int,float) and type(b) in (int,float) and math.isfinite(a) and abs(a-b)<1e-5


def request(spec,cut,source_ids,name,tracks=(1,2,3)):
    require((spec['width'],spec['height'])==(1080,1920),'Native split requires 1080x1920')
    shot=spec['framing']['shots'][cut['id']]
    require(shot['mode']=='panel-layout' and len(shot['panels'])==2,'Two explicit camera panels required')
    tick=Fraction(254016000000*spec['fps']['denominator'],spec['fps']['numerator'])
    require(tick.denominator==1,'Exact native frame clock required');tick=int(tick)
    sources={s['id']:s for s in spec['sources']};panels=[]
    for i,panel in enumerate(shot['panels']):
        require(panel['rect']==dict(x=0,y=i*960,width=1080,height=960),'Ordered top/bottom half-frame rectangles required')
        sr=panel['sourceRange'];crop=panel['crop'];source=sources[sr['sourceId']]
        require(sr['sha256']==source['sha256'] and sr['frames']==cut['frames'],'Frozen camera source or duration differs')
        require(crop['mode']=='tracked-crop' and len(crop['xByFrame'])==cut['frames'],'Dense panel tracking required')
        require(near(crop['width']/crop['height'],1080/960),'Panel crop aspect differs')
        keys=[[round((x+crop['width']/2)/crop['sourceWidth'],8),round((crop['y']+crop['height']/2)/crop['sourceHeight'],8)] for x in crop['xByFrame']]
        require(all(all(type(v) in (int,float) and math.isfinite(v) and 0<=v<=1 for v in k) for k in keys),'Panel keys invalid')
        scale=struct.unpack('!f',struct.pack('!f',960/crop['height']*100))[0]
        panels.append(dict(source_id=source_ids[sr['sourceId']],media_path=str(Path(source['path']).resolve()),source_in_ticks=str(sr['inFrame']*tick),source_out_ticks=str((sr['inFrame']+sr['frames'])*tick),scale=scale,anchor_keys=keys))
    return dict(name=name,start_ticks=str(cut['recordFrame']*tick),end_ticks=str((cut['recordFrame']+cut['frames'])*tick),frame_ticks=str(tick),tracks=list(tracks),panels=panels)


def component(item,name):
    found=[c for c in item['components'] if c['matchName']==name]
    require(len(found)==1,'Missing or duplicate native component: '+name)
    return found[0]


def prop(item,component_name,name):
    found=[p for p in component(item,component_name)['properties'] if p['name']==name]
    require(len(found)==1,'Missing or duplicate native property: '+name)
    return found[0]


def static(item,name,value):
    p=prop(item,'AE.ADBE Motion',name)
    require(not p.get('keys') and near(p['value'],value),'Native panel transform changed: '+name)


def verify(spec,cut,entry,project,links):
    r=entry['request'];result=entry['result'];source_ids={p['sourceRange']['sourceId']:q['source_id'] for p,q in zip(spec['framing']['shots'][cut['id']]['panels'],r['panels'])}
    require(request(spec,cut,source_ids,r['name'],r['tracks'])==r,'Native split request differs from frozen framing')
    require(result['project_path']==project['project_path'],'Native split project differs')
    sequences={s['sequence_id']:s for s in project['sequences']};master=sequences[result['sequence_id']]['snapshot']
    require(project['active_sequence_id']==result['sequence_id'],'Intended master must remain active')
    require(len(result['panels'])==2 and len(result['placements'])==3,'Native split graph incomplete')
    duration=int(r['end_ticks'])-int(r['start_ticks']);tick=int(r['frame_ticks'])
    panel_ids=[]
    for i,(p,pin) in enumerate(zip(r['panels'],result['panels'])):
        sid=pin['sequence_id'];panel_ids.append(sid);s=sequences[sid];snap=s['snapshot']
        require(s['name']==r['name']+'_PANEL_'+str(i),'Panel identity changed')
        settings=snap['settings'];require((settings['videoFrameWidth'],settings['videoFrameHeight'],str(settings['videoFrameRate']['ticks']))==(1080,960,r['frame_ticks']),'Panel canvas/frame clock changed')
        require(not any(t['clips'] for t in snap['tracks'] if t['kind']==1),'Panel contains duplicated audio')
        rows=[(t,c) for t in snap['tracks'] if t['kind']==0 for c in t['clips']]
        require(len(rows)==1,'Unexpected panel picture layers');t,item=rows[0]
        require(not t['muted'] and not item['disabled'] and item['speed']==1 and item['id']==pin['picture_item_id'],'Panel playback or item changed')
        require((item['start'],item['end'],item['inPoint'],item['outPoint'])==('0',str(duration),p['source_in_ticks'],p['source_out_ticks']),'Panel exact source clocks changed')
        require([c['matchName'] for c in item['components']]==['AE.ADBE Opacity','AE.ADBE Motion'],'Unsupported panel effects; preserve and reconcile')
        require(near(prop(item,'AE.ADBE Opacity','Opacity')['value'],100),'Panel opacity changed')
        static(item,'Position',[.5,.5]);static(item,'Scale',p['scale']);static(item,'Rotation',0)
        for edge in ['Left','Top','Right','Bottom']:static(item,'Crop '+edge,0)
        keys=prop(item,'AE.ADBE Motion','Anchor Point').get('keys',[])
        expected=[{'ticks':str(int(p['source_in_ticks'])+j*tick),'value':v} for j,v in enumerate(p['anchor_keys'])]
        require(len(keys)==len(expected) and all(a['ticks']==b['ticks'] and near(a['value'],b['value']) for a,b in zip(keys,expected)),'Native dense panel keys changed')
        link=links[sid];require(link['project_path']==project['project_path'] and link['sequence_id']==sid and link['verification'] in ('stable_native_panel_sources',),'Stable panel source inspection required')
        found=[x['item'] for x in link['items'] if x['kind']=='video' and x['item']['node_id']==item['id']]
        require(len(found)==1 and found[0]['media_path']==p['media_path'] and found[0]['offline'] is False and found[0]['speed_reversed'] in (False,0) and found[0]['is_sequence'] is False,'Panel is offline, flattened, reversed or uses another source')
    require(len(set(panel_ids))==2,'Independent camera panel sequences required')
    native_sources=[]
    for i,pin in enumerate(result['placements']):
        track=[t for t in master['tracks'] if t['kind']==0 and t['index']==r['tracks'][i]]
        require(len(track)==1 and not track[0]['muted'],'Split track disabled')
        overlap=[c for c in track[0]['clips'] if int(c['end'])>int(r['start_ticks']) and int(c['start'])<int(r['end_ticks'])]
        require(len(overlap)==1,'Ambiguous split picture coverage');c=overlap[0];panel=1 if i==0 else 0
        require(c['id']==pin['node_id'] and c['sourceId']==pin['source_id'] and pin['sequence_id']==panel_ids[panel] and c['name']==r['name']+'_PANEL_'+str(panel),'Split nest identity differs')
        native_sources.append(c['sourceId'])
        require((c['start'],c['end'],c['inPoint'],c['outPoint'])==(r['start_ticks'],r['end_ticks'],'0',str(duration)) and c['speed']==1 and not c['disabled'],'Split nest clock or playback changed')
        static(c,'Position',[.5,.75 if i==0 else .25]);static(c,'Anchor Point',[.5,.5]);static(c,'Scale',115 if i==1 else 100);static(c,'Rotation',0)
        require([x['matchName'] for x in c['components']]==['AE.ADBE Opacity','AE.ADBE Motion']+(['AE.ADBE Drop Shadow'] if i==1 else []),'Unsupported split effect')
        require(near(prop(c,'AE.ADBE Opacity','Opacity')['value'],100),'Split opacity changed')
        if i==1:
            for name,want in {'Opacity':98,'Direction':180,'Distance':49.700008392334,'Softness':150}.items():
                p=prop(c,'AE.ADBE Drop Shadow',name);require(not p.get('keys') and near(p['value'],want),'Shadow controls changed')
            p=prop(c,'AE.ADBE Drop Shadow','Shadow Only');require(p['value'] is True and not p.get('keys'),'Shadow is not shadow-only')
    require(native_sources[1]==native_sources[2] and native_sources[0]!=native_sources[1],'Top image and shadow must share one nest; bottom independent')
    require(not any(c['sourceId'] in native_sources for t in master['tracks'] if t['kind']==1 for c in t['clips']),'Silent/duplicate panel audio remains')
    return {'cutId':cut['id'],'panels':panel_ids,'keys':sum(len(p['anchor_keys']) for p in r['panels']),'verification':'native-source-clocks-dense-keys-independent-panels-linked-shadow','visualApproval':False}


def reconcile_caption_copy(spec,cut,entry,project,links,caption_receipt):
    """Bind preserved panel identities to a caption builder's new master UID.

    This is a new observed-state receipt, never a rewrite of construction history.
    Every camera item, nest identity, clock, key and shadow must still pass verify.
    """
    require(caption_receipt['target']==project['project_path'] and caption_receipt['sequence_uid']==project['active_sequence_id'],'Caption copy target differs')
    require(caption_receipt['insertion']['sequence_uid']==entry['result']['sequence_id'] and caption_receipt['insertion'].get('originals_retained') is True,'Caption copy does not continue original master')
    rebound=copy.deepcopy(entry)
    rebound['reconciliation']={'kind':'caption-copy-native-readback','originalProject':entry['result']['project_path'],'originalSequence':entry['result']['sequence_id'],'constructionHistoryUnchanged':True}
    rebound['result']['project_path']=project['project_path'];rebound['result']['sequence_id']=project['active_sequence_id']
    verify(spec,cut,rebound,project,links)
    return rebound
