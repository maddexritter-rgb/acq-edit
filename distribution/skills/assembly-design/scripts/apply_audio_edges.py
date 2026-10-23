#!/usr/bin/env python3
"""Apply source-sample decisions to an existing compiler-derived native assembly.

Invoked by apply_native_assembly --audio-plan. It never selects or deletes words.
The base import remains frame-aligned; this owned stage applies independent audio
edges and produces the final handoff rather than rounding them back into XML.
"""
import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'_shared'))
from premiere_bridge import BridgeError, execute_operation
from premiere_stage_handoff import write_handoff

TPS=254016000000
KEYS=('start','end','inPoint','outPoint')


def load_plan(path, expected_path, expected_hash):
    plan=json.loads(Path(path).read_text())
    if plan.get('schema')!='edit.assembly-audio-edges/v1':raise BridgeError('Unknown audio edge plan')
    if plan.get('expected_sha256')!=expected_hash or hashlib.sha256(Path(expected_path).read_bytes()).hexdigest()!=expected_hash:
        raise BridgeError('Audio decisions do not pin this exact compiled assembly receipt')
    if plan.get('sample_rate') not in (44100,48000,96000):raise BridgeError('Unsupported audio sample rate')
    if not isinstance(plan.get('cuts'),list) or not 1<=len(plan['cuts'])<=128:raise BridgeError('A bounded list of audio decisions is required')
    indices=set()
    for cut in plan['cuts']:
        idx=cut.get('assembly_item_index');samples=cut.get('source_samples')
        if type(idx) is not int or idx<0 or idx in indices:raise BridgeError('Unique assembly item index required')
        indices.add(idx)
        if not isinstance(samples,list) or len(samples)!=2 or any(type(v) is not int or v<0 for v in samples) or samples[1]<=samples[0]:raise BridgeError('Positive integer source-sample span required')
        if not cut.get('reason') or not cut.get('evidence') or cut.get('status') not in ('PROPOSED','LOCALLY_INSPECTED','LISTENED','EDITOR_APPROVED'):
            raise BridgeError('Each audio edge decision needs its reason, evidence and actual review status')
    return plan


def bind(plan, expected, native_map, links):
    rows={x['assembly_item_index']:x for x in native_map}
    native={x['item']['node_id']:x for x in links['items']}
    frame_ticks=Fraction(TPS,1)/Fraction(expected['fps']);step=TPS//plan['sample_rate']
    if frame_ticks.denominator!=1:raise BridgeError('Frame clock is not exactly representable')
    result=[]
    for decision in plan['cuts']:
        index=decision['assembly_item_index']
        if index not in rows or index>=len(expected['items']):raise BridgeError('Assembly item outside compiled receipt')
        mapping=rows[index];exp=expected['items'][index];row=native.get(mapping['audio_node_id'])
        if not row or row['kind']!='audio':raise BridgeError('Native audio identity not found')
        a=row['item'];b=dict(zip(KEYS,[a['start_ticks'],a['end_ticks'],a['source_in_ticks'],a['source_out_ticks']]))
        base=[str(n*int(frame_ticks)) for n in exp['timeline_frames']+exp['source_frames']]
        if list(b.values())!=base or a['media_path']!=exp['media'] or a['source_id']!=mapping['source_node_id']:
            raise BridgeError('Audio media or geometry differs from the pinned assembly')
        i,o=(v*step for v in decision['source_samples'])
        wanted={'start':str(int(b['start'])+i-int(b['inPoint'])), 'end':str(int(b['end'])+o-int(b['outPoint'])), 'inPoint':str(i),'outPoint':str(o)}
        if any(int(v)<0 or int(v)%step for v in wanted.values()):raise BridgeError('Sync-preserving edit does not fit the sequence sample grid')
        result.append({'node_id':mapping['audio_node_id'],'source_id':a['source_id'],'media_path':a['media_path'],'before':b,'after':wanted})
    return {'sample_rate':plan['sample_rate'],'items':result}


def apply_audio_plan(client, result, plan, expected, output_dir, previous_handoff):
    out=Path(output_dir);out.mkdir(parents=True,exist_ok=False)
    def record(name,value):
        with (out/name).open('x') as f:json.dump(value,f,indent=2,allow_nan=False)
    def project():return client.inspect('inspect_project_sequences',{'project_path':result['project_path']})['data']
    def operate(tool,args,label):
        active=client.inspect('lab_snapshot',{})
        op={'schema':'edit.native-operation/v1','stage':'assembly','operation_id':'audio-'+label+'-'+uuid.uuid4().hex,'tool':tool,'arguments':args,
            'target':{'project_path':active['projectPath'],'sequence_id':active['sequenceId'],'expected_revision':active['revision']},
            'intended_changes':[label+' for the explicitly imported assembly'],
            'protected_state':['All picture, other audio, effects, selected-word compiler chain and other sequences']}
        return execute_operation(client,op,out/(label+'-operation.json'))
    before_project=project();record('project-before.json',before_project);restore=before_project['active_sequence_id'];sid=result['sequence_id']
    links=client.inspect('inspect_assembly_links',{'project_path':result['project_path'],'sequence_id':sid})['data'];args=bind(plan,expected,result['native_item_map'],links)
    record('decision-plan.json',plan);record('bound-audio-edges.json',args);record('links-before.json',links)
    if restore!=sid:operate('set_active_sequence',{'sequence_id':sid},'activate')
    before=client.inspect('lab_snapshot',{});record('before.json',before)
    if before['sequenceId']!=sid:raise BridgeError('Audio target changed before execution')
    native=operate('lab_apply_assembly_audio_edges',args,'edges');record('native-result.json',native)
    after=client.inspect('lab_snapshot',{});record('after.json',after)
    raw_before={k:v for k,v in before.items() if k not in ('revision','revisionScope','uxp')};raw_after={k:v for k,v in after.items() if k not in ('revision','revisionScope','uxp')}
    wanted=copy.deepcopy(raw_before);changes={r['node_id']:r['after'] for r in args['items']}
    for track in wanted['tracks']:
        for clip in track['clips']:
            if clip['id'] in changes:
                if track['kind']!=1:raise BridgeError('Audio operation targeted picture')
                clip.update(changes[clip['id']])
    if raw_after!=wanted or native.get('snapshot')!=wanted:raise BridgeError('Exact audio or protected-state mismatch')
    new_links=client.inspect('inspect_assembly_links',{'project_path':result['project_path'],'sequence_id':sid})['data'];record('links-after.json',new_links)
    groups=lambda data:{r['item']['node_id']:r['linked_node_ids'] for r in data['items']}
    if groups(links)!=groups(new_links):raise BridgeError('Native AV link membership changed')
    operate('save_project',{},'save')
    if client.inspect('lab_snapshot',{})!=after:raise BridgeError('State changed during audio checkpoint save')
    if restore!=sid:operate('set_active_sequence',{'sequence_id':restore},'restore')
    final=project();record('project-after.json',final)
    old={r['sequence_id']:r for r in before_project['sequences']};new={r['sequence_id']:r for r in final['sequences']}
    if set(old)!=set(new) or any(old[k]!=new[k] for k in old if k!=sid) or final['active_sequence_id']!=restore or new[sid]['snapshot']!=raw_after:raise BridgeError('Protected project state changed')
    handoff=write_handoff(out/'stage-handoff.json',stage='assembly',before=raw_before,after=raw_after,before_revision=before['revision'],after_revision=after['revision'],receipts=[out/'edges-operation.json',out/'save-operation.json'],previous=previous_handoff)
    answer={**result,'status':'SAMPLE_EDGES_SAVED_REOPEN_AND_LISTEN_REQUIRED','sequence_revision':after['revision'],'stage_handoff':str(out/'stage-handoff.json'),'audio_edges':str(out/'bound-audio-edges.json'),'audio_decisions':str(out/'decision-plan.json'),'listening':'not_run','persistence':'reopen_not_run','audio_pcm_validation':'input_codec_and_rate_checked; this edit still requires rendered comparison'}
    record('result.json',answer)
    return answer
