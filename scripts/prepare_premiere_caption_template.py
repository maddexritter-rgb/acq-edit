#!/usr/bin/env python3
"""Isolate declared native Graphics donors and graft them into an offline copy.

Caption-clips still owns text construction, retargeting and saved-file checks.
This preparation transports a closed generated-media graph only. It never edits
an open project, imports historical footage, or grants visual approval.
"""
import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path
import sys
import uuid
import xml.etree.ElementTree as ET


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def closure(root, seeds):
    ids = {n.get('ObjectID'): n for n in root if n.get('ObjectID')}
    uids = {n.get('ObjectUID'): n for n in root if n.get('ObjectUID')}
    if len(ids)+len(uids) != sum(bool(n.get('ObjectID') or n.get('ObjectUID')) for n in root):
        raise ValueError('Ambiguous native identities')
    pending = [ids[s] for s in seeds]; seen = {}
    while pending:
        node = pending.pop(); key = node.get('ObjectID') or node.get('ObjectUID')
        if key in seen:continue
        if node.tag in ('Sequence','Project','ProjectItem','AudioMediaSource','AudioClipTrackItem'):
            raise ValueError('Donor closure includes unrelated timeline or audio state')
        if node.tag == 'Media':
            if node.findtext('Title') != 'Graphic' or node.findtext('Infinite') != 'true':
                raise ValueError('Only self-contained generated Graphics media are supported')
            for field in ('FilePath','ActualMediaFilePath'):
                value=node.findtext(field)
                if value and not value.isdecimal():raise ValueError('External donor media refused')
        seen[key]=node
        for child in node.iter():
            for attr, lookup in [('ObjectRef',ids),('ObjectURef',uids)]:
                ref=child.get(attr)
                if ref:
                    if ref not in lookup:raise ValueError('Dangling donor reference: '+ref)
                    pending.append(lookup[ref])
    return list(seen.values())


def extract(source, profile_path, output, native, integrity):
    source, output=Path(source),Path(output)
    profile=json.loads(Path(profile_path).read_text())
    if sha(source)!=profile['project_sha256']:raise ValueError('Donor/profile hash differs')
    root=native.load(source); seeds=[d['item_id'] for d in profile['donors'].values()]
    nodes=integrity.materialize_aliases(closure(root,seeds),[root])
    graph=ET.Element('NativeGraphicDonors')
    graph.extend(nodes);integrity.validate_aliases(graph)
    output.mkdir(parents=True,exist_ok=False)
    graph_path=output/'graph.xml';graph_path.write_bytes(ET.tostring(graph,encoding='utf-8',xml_declaration=True))
    # Do not distribute old project paths, transcripts or unrelated profile fields.
    portable={'schema':'acq-edit/premiere-donor-asset-v1','sourceSha256':sha(source),
              'graphSha256':sha(graph_path),'donors':profile['donors'],
              'y_pct':profile['y_pct'],'donorMode':profile.get('donorMode','speaker'),'status':'native-render-and-human-review-required'}
    (output/'profile.json').write_text(json.dumps(portable,indent=2))
    return {'nodes':len(nodes),'graphSha256':portable['graphSha256'],'externalMedia':0}


def graft(project, asset, sequence_uid, output, out_profile, native, integrity):
    project, asset, output, out_profile=map(Path,(project,asset,output,out_profile))
    if output.exists() or out_profile.exists():raise FileExistsError('Fresh outputs required')
    profile=json.loads((asset/'profile.json').read_text())
    if profile['schema']!='acq-edit/premiere-donor-asset-v1' or sha(asset/'graph.xml')!=profile['graphSha256']:
        raise ValueError('Donor asset changed')
    donor_mode=profile.get('donorMode','speaker')
    if donor_mode not in ('speaker','style'):raise ValueError('Unknown donor selection mode')
    donor_key='donors_by_style' if donor_mode=='style' else 'donors'
    root=native.load(project); before={n.get('ObjectID') or n.get('ObjectUID'):ET.tostring(n) for n in root}
    source=ET.parse(asset/'graph.xml').getroot(); seeds=[d['item_id'] for d in profile['donors'].values()]
    nodes=integrity.materialize_aliases(closure(source,seeds),[source])
    if len(nodes)!=len(source):raise ValueError('Unreferenced asset objects refused')
    ids=native.objects(root);uids={n.get('ObjectUID'):n for n in root if n.get('ObjectUID')}
    seq=uids[sequence_uid]
    if seq.tag!='Sequence':raise ValueError('Sequence target required')
    groups=[ids[r.get('ObjectRef')] for r in seq.findall('TrackGroups/TrackGroup/Second')]
    groups=[g for g in groups if g.tag=='VideoTrackGroup']
    if len(groups)!=1:raise ValueError('Unique video group required')
    group=groups[0];refs=group.find('TrackGroup/Tracks');index=len(refs)
    if [r.get('Index') for r in refs]!=list(map(str,range(index))) or index<1:
        raise ValueError('Unsupported video lane layout')
    base=uids[refs[0].get('ObjectURef')]
    if base.tag!='VideoClipTrack':raise ValueError('Direct video track required')
    # Track skeleton owns no media references after its existing items are cleared.
    track=copy.deepcopy(base);track_uid=str(uuid.uuid4());track.set('ObjectUID',track_uid)
    for tag in ('ClipItems','TransitionItems'):
        section=track.find('ClipTrack/'+tag)
        if section is None:raise ValueError('Incomplete track skeleton')
        for child in list(section):
            if child.tag not in ('MediaType','Index'):section.remove(child)
        section.find('Index').text=str(index)
    ET.SubElement(track.find('ClipTrack/ClipItems'),'TrackItems',{'Version':'1'})
    track.find('ClipTrack/Track/Index').text=str(index)
    next_id=int(group.findtext('TrackGroup/NextTrackID'))
    track.find('ClipTrack/Track/ID').text=str(next_id)
    for e in track.iter():
        if e.get('ObjectRef') or e.get('ObjectURef'):raise ValueError('Track skeleton has shared effects; unsupported')
    first=max(map(int,ids))+1
    mapping={n.get('ObjectID'):str(first+i) for i,n in enumerate(nodes) if n.get('ObjectID')}
    uidmap={n.get('ObjectUID'):str(uuid.uuid4()) for n in nodes if n.get('ObjectUID')}
    for node in nodes:
        for e in node.iter():
            for attr,lookup in [('ObjectID',mapping),('ObjectRef',mapping),('ObjectUID',uidmap),('ObjectURef',uidmap)]:
                if e.get(attr):e.set(attr,lookup[e.get(attr)])
        root.append(node)
    root.append(track);ET.SubElement(refs,'Track',{'Index':str(index),'ObjectURef':track_uid})
    group.find('TrackGroup/NextTrackID').text=str(next_id+1)
    integrity.validate_aliases(root)
    for node in root:
        key=node.get('ObjectID') or node.get('ObjectUID')
        if key in before and node is not group and ET.tostring(node)!=before[key]:
            raise ValueError('Protected original object changed')
    output.write_bytes(gzip.compress(ET.tostring(root,encoding='utf-8',xml_declaration=True)))
    result={'project_sha256':sha(output),'sequence_uid':sequence_uid,'track_index':index,
            'expected_item_ids':[],'y_pct':profile['y_pct'],
            donor_key:{name:{**d,'item_id':mapping[d['item_id']]} for name,d in profile['donors'].items()},
            'asset_graph_sha256':profile['graphSha256'],'status':'native-render-and-human-review-required'}
    out_profile.write_text(json.dumps(result,indent=2))
    return {'output':str(output),'trackIndex':index,'protectedObjects':len(before)-1,'nativeVerified':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--skills',type=Path,required=True)
    sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('extract')
    for arg in ('source','profile','output'):p.add_argument('--'+arg,required=True)
    p=sub.add_parser('graft')
    for arg in ('project','asset','sequence-uid','output','out-profile'):p.add_argument('--'+arg,required=True)
    args=parser.parse_args();sys.path.insert(0,str(args.skills.resolve()/'caption-clips/scripts'));sys.path.insert(0,str(args.skills.resolve()/'_shared'))
    import premiere_native_cards as native
    import premiere_graph_integrity as integrity
    result=extract(args.source,args.profile,args.output,native,integrity) if args.action=='extract' else graft(args.project,args.asset,args.sequence_uid,args.output,args.out_profile,native,integrity)
    print(json.dumps(result,indent=2))
