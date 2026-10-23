#!/usr/bin/env python3
"""Transfer an existing prepared native caption build through the shared bridge.

No caption construction, editorial selection, replacement or silent activation.
The explicit structure describes every imported track and item; caption-owned
card clocks remain bound to the existing builder receipt and resolved manifest.
"""
from pathlib import Path
from fractions import Fraction
import argparse
import copy
import json
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '_shared'))
from premiere_bridge import BridgeError, PremiereBridge, Profile, execute_operation
from premiere_caption_handoff import prepare, map_import, sha, exact
from premiere_stage_handoff import write_creation_handoff
from native_caption_revision import assert_transfer_baseline


def flag(value):
    if type(value) is bool:return value
    if type(value) is int and value in (0, 1):return bool(value)
    raise BridgeError('Native boolean unavailable')


def structure_request(prepared, structure, manifest):
    if structure.get('schema') != 'edit.caption-transfer-structure/v1' or structure.get('prepared_sha256') != prepared['artifacts'][0]['sha256']:
        raise BridgeError('Complete structure is not bound to the prepared project')
    request = copy.deepcopy(structure['expectation'])
    # An empty donor lane can inherit mute and hide every otherwise valid card.
    owned = [t for t in request.get('tracks', []) if t.get('kind') == 'video' and t.get('index') == prepared['track_index']]
    if len(owned) != 1 or flag(owned[0].get('muted')):
        raise BridgeError('Owned caption lane must be explicitly visible before transfer; never unmute unrelated tracks')
    required = {'sequence_id','sequence_name','width','height','frame_duration_ticks','tracks','markers'}
    if set(request) != required or request['sequence_id'] != prepared['sequence_id'] or request['sequence_name'] != prepared['sequence_name'] or [request['width'],request['height']] != prepared['canvas']:
        raise BridgeError('Prepared sequence/structure identity mismatch')
    fps = Fraction(manifest['frame_rate']['numerator'],manifest['frame_rate']['denominator'])
    frame = Fraction(254016000000,1) / fps
    if frame.denominator != 1 or exact(request['frame_duration_ticks']) != frame.numerator:
        raise BridgeError('Prepared rational frame duration mismatch')
    lanes = [t for t in request['tracks'] if t['kind']=='video' and t['index']==prepared['track_index']]
    if len(lanes)!=1 or len(lanes[0]['items'])!=len(prepared['segments']):raise BridgeError('Caption lane not bound to complete structure')
    for item,segment in zip(lanes[0]['items'],prepared['segments']):
        if item['token']!=segment['segment_id'] or item['source_kind']!='graphic' or item['media_path'] is not None or item['speed']!=1 or item['speed_reversed'] is not False or item['disabled'] is not False:
            raise BridgeError('Caption render segment identity/playback mismatch')
        for key in ('start_ticks','end_ticks','source_in_ticks','source_out_ticks'):
            if exact(item[key])!=exact(segment['timing'][key]):raise BridgeError('Caption structure clock mismatch')
    return request


def verify_structure(request, project, full):
    """Independent Python comparison of two native read surfaces after dispatch."""
    seqs=[s for s in project['sequences'] if s['sequence_id']==request['sequence_id']]
    if len(seqs)!=1 or full.get('id')!=request['sequence_id']:raise BridgeError('Independent sequence identity mismatch')
    snapshot=seqs[0]['snapshot']
    if seqs[0]['name']!=request['sequence_name'] or [full.get('width'),full.get('height')]!=[request['width'],request['height']]:raise BridgeError('Independent canvas/name mismatch')
    if str((full.get('frameRate') or {}).get('ticks'))!=request['frame_duration_ticks']:raise BridgeError('Independent native frame duration unavailable/mismatched')
    if snapshot.get('markers')!=request['markers']:raise BridgeError('Imported markers differ')
    rich={('video' if t['kind']==0 else 'audio',t['index']):t for t in snapshot['tracks']}
    raw={(kind,t['index']):t for kind,key in [('video','videoTracks'),('audio','audioTracks')] for t in full[key]}
    wanted={(t['kind'],t['index']):t for t in request['tracks']}
    if len(wanted)!=len(request['tracks']) or set(rich)!=set(wanted) or set(raw)!=set(wanted):raise BridgeError('Independent track inventory mismatch')
    mapped=[];ids=set()
    for key,track in wanted.items():
        a,b=rich[key],raw[key]
        if a['name']!=track['name'] or b['name']!=track['name'] or flag(a['locked'])!=track['locked'] or flag(a['muted'])!=track['muted'] or flag(b['isLocked'])!=track['locked'] or flag(b['isMuted'])!=track['muted'] or b.get('transitionCount')!=0:
            raise BridgeError('Independent track state mismatch')
        if len(a['clips'])!=len(track['items']) or len(b['clips'])!=len(track['items']):raise BridgeError('Independent item inventory mismatch')
        for expected,c,d in zip(track['items'],a['clips'],b['clips']):
            if c['id']!=d['nodeId'] or not c['id'] or c['id'] in ids:raise BridgeError('Independent native item identity mismatch')
            ids.add(c['id'])
            for want,field,other in [('start_ticks','start','startTicks'),('end_ticks','end','endTicks'),('source_in_ticks','inPoint','inPointTicks'),('source_out_ticks','outPoint','outPointTicks')]:
                if exact(c[field])!=exact(expected[want]) or exact(d[other])!=exact(expected[want]):raise BridgeError('Independent source/timeline clock mismatch')
            if c['speed']!=expected['speed'] or d.get('speed')!=expected['speed'] or flag(d.get('reversed'))!=expected['speed_reversed'] or flag(c['disabled'])!=expected['disabled']:raise BridgeError('Independent playback mismatch')
            if [fx['matchName'] for fx in c['components']]!=expected['component_match_names']:raise BridgeError('Independent component chain mismatch')
            if expected['source_kind']=='media':
                if not c['sourceId'] or c['sourceId']!=d.get('sourceNodeId') or flag(d.get('sourceOffline')) or '/' + d.get('sourceMediaPath','').lstrip('/')!='/' + expected['media_path'].lstrip('/'):
                    raise BridgeError('Independent imported media linkage mismatch')
            mapped.append({'token':expected['token'],'node_id':c['id'],'source_id':c['sourceId'],'kind':key[0],'track_index':key[1]})
    return {'status':'DECLARED_STRUCTURE_READBACK_PASS','items':mapped,'imported_effect_values':'not_verified','persistence':'not_run','rendered':'not_run'}


def apply_transfer(client, *, project_path, receipt_path, manifest_path, structure_path, output_dir, native):
    output_dir=Path(output_dir).resolve();output_dir.mkdir(parents=True,exist_ok=False)
    def record(name,data):
        with (output_dir/name).open('x') as f:json.dump(data,f,indent=2,allow_nan=False)
    structure_path=Path(structure_path).resolve();structure_hash=sha(structure_path)
    prepared=prepare(project_path,receipt_path,manifest_path,native)
    structure=json.loads(structure_path.read_text());manifest=json.loads(Path(manifest_path).read_text())
    request=structure_request(prepared,structure,manifest)
    snapshot=client.inspect('lab_snapshot',{})
    before=client.inspect('inspect_project_sequences',{'project_path':snapshot['projectPath']})['data']
    active=[s for s in before['sequences'] if s['sequence_id']==snapshot['sequenceId']]
    if len(active)!=1 or any(snapshot.get(k)!=v for k,v in active[0]['snapshot'].items()):raise BridgeError('Active baseline changed while planning transfer')
    if sha(structure_path)!=structure_hash:raise BridgeError('Declared structure changed during planning')
    assert_transfer_baseline(prepared.get('revision_precondition'),before)
    request.update(prepared_path=prepared['artifacts'][0]['path'],prepared_sha256=prepared['artifacts'][0]['sha256'],expected_project_revision=before['revision'])
    record('prepared.json',prepared);record('structure.json',{'path':str(structure_path),'sha256':structure_hash,'structure':structure});record('before.json',before)
    operation={'schema':'edit.native-operation/v1','stage':'captions','operation_id':'caption-transfer-'+uuid.uuid4().hex,'tool':'lab_import_prepared_caption_sequence','arguments':request,
               'target':{'project_path':snapshot['projectPath'],'sequence_id':snapshot['sequenceId'],'expected_revision':snapshot['revision']},
               'intended_changes':['Import the exact prepared caption sequence and declared track/item structure'],
               'protected_state':['All existing destination sequences, source/timeline ranges, effects and settings; no activation']}
    result=execute_operation(client,operation,output_dir/'transfer-operation.json')
    after=client.inspect('inspect_project_sequences',{'project_path':snapshot['projectPath']})['data'];record('after.json',after)
    card_map=map_import(prepared,before,after)
    created=[s for s in after['sequences'] if s['sequence_id']==prepared['sequence_id']][0]
    if created['snapshot']!=result.get('snapshot'):raise BridgeError('Imported caption sequence changed after native dispatch')
    full=client.inspect('get_full_sequence_info',{'sequence_id':prepared['sequence_id']})['data'];record('independent-sequence.json',full)
    checked=verify_structure(request,after,full)
    fresh=client.inspect('inspect_project_sequences',{'project_path':snapshot['projectPath']})['data']
    if fresh!=after or any(sha(a['path'])!=a['sha256'] for a in prepared['artifacts']) or sha(structure_path)!=structure_hash:raise BridgeError('Artifacts or native state changed during independent verification')
    assert_transfer_baseline(prepared.get('revision_precondition'),fresh)
    snapshot=client.inspect('lab_snapshot',{})
    if snapshot['sequenceId']!=before['active_sequence_id']:raise BridgeError('Unexpected activation before checkpoint save')
    save={'schema':'edit.native-operation/v1','stage':'captions','operation_id':operation['operation_id']+'-save','tool':'save_project','arguments':{},'target':{'project_path':snapshot['projectPath'],'sequence_id':snapshot['sequenceId'],'expected_revision':snapshot['revision']},'intended_changes':['Save the verified imported caption sequence'],'protected_state':['All timeline state']}
    execute_operation(client,save,output_dir/'save-operation.json')
    saved=native.verify(snapshot['projectPath'],receipt_path)
    post_save=client.inspect('inspect_project_sequences',{'project_path':snapshot['projectPath']})['data']
    if post_save!=after:raise BridgeError('Native state changed during save; inspect original receipts')
    handoff=write_creation_handoff(output_dir/'stage-handoff.json',stage='captions',project_before=before,project_after=post_save,sequence_id=prepared['sequence_id'],sequence_revision=result['sequence_revision'],receipt=output_dir/'transfer-operation.json')
    record('card-map.json',card_map);record('structure-readback.json',checked)
    output={'schema':'edit.caption-transfer-result/v1','status':'IMPORTED_SAVED_REOPEN_AND_RENDER_REQUIRED','target_project':snapshot['projectPath'],'sequence_id':prepared['sequence_id'],'sequence_revision':handoff['after_revision'],'stage_handoff':'stage-handoff.json','native_result':result,'saved_file':{'path':snapshot['projectPath'],'sha256':sha(snapshot['projectPath']),'verification':saved},'card_map':'card-map.json','structure_readback':'structure-readback.json','persistence':'reopen_not_run','rendered':'not_run','text_editability':'not_proven','targeted_revision':'not_implemented'}
    if prepared.get('revision_precondition'):
        output['targeted_revision']='SCOPED_OFFLINE_REBUILD_IMPORTED_AS_NEW_SEQUENCE_NO_IN_PLACE_REPLACEMENT'
        output['revision_precondition']=prepared['revision_precondition']
    record('result.json',output)
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['project','receipt','manifest','structure','output-dir']:parser.add_argument('--'+name,required=True)
    parser.add_argument('--bridge-profile', default=None, help='Premiere Agent default profile unless explicitly overridden')
    args=parser.parse_args()
    sys.path.append(str(Path("__ACQ_SKILLS__/caption-clips/scripts")))
    import premiere_native_cards as native
    client=PremiereBridge(Profile.load(args.bridge_profile))
    try:print(json.dumps(apply_transfer(client,project_path=args.project,receipt_path=args.receipt,manifest_path=args.manifest,structure_path=args.structure,output_dir=args.output_dir,native=native),indent=2))
    finally:client.close()


if __name__=='__main__':main()
