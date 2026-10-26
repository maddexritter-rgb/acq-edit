#!/usr/bin/env python3
"""Import the existing compiled v2 assembly through the default Premiere Agent.

Consumes the original compiler XML, expected receipt and resolved selection.
Does not select words, redesign cuts, activate a sequence or approve an edit.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import uuid
from dataclasses import replace
import subprocess

sys.path.insert(0,str(Path(__file__).resolve().parent))
from apply_audio_edges import load_plan, apply_audio_plan

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'_shared'))
from premiere_bridge import BridgeError, PremiereBridge, Profile, execute_operation
from premiere_stage_handoff import write_creation_handoff


def unchanged_projects(before,after,sequence_id):
    old={s['sequence_id']:s for s in before['sequences']};new={s['sequence_id']:s for s in after['sequences']}
    if (len(old)!=len(before['sequences']) or len(new)!=len(after['sequences']) or set(new)-set(old)!={sequence_id}
            or not set(old)<=set(new) or any(old[k]!=new[k] for k in old)
            or before['project_path']!=after['project_path'] or before['active_sequence_id']!=after['active_sequence_id']):
        raise BridgeError('Assembly import changed protected project state or added an unexpected sequence')
    return new[sequence_id]


def apply_assembly(client, *, request, output_dir, validator):
    output_dir=Path(output_dir).resolve();output_dir.mkdir(parents=True,exist_ok=False)
    def record(name,value):
        with (output_dir/name).open('x') as f:json.dump(value,f,indent=2,allow_nan=False)
    proof=validator.validate_compiled_packet(request['xml_path'],request['xml_sha256'],request['expected_path'],request['expected_sha256'],client.profile.fixture_root,request['resolved_path'],request['resolved_sha256'],request['gap_frames'])
    record('compiler-proof.json',proof)
    snapshot=client.inspect('lab_snapshot',{})
    before=client.inspect('inspect_project_sequences',{'project_path':snapshot['projectPath']})['data']
    active=[s for s in before['sequences'] if s['sequence_id']==snapshot['sequenceId']]
    if snapshot.get('sequenceId') is None:
        if before.get('active_sequence_id') is not None or active or before.get('project_path') != snapshot.get('projectPath') or snapshot.get('tracks') != []:
            raise BridgeError('Empty assembly target changed during preflight')
        if client.inspect('lab_snapshot',{}) != snapshot:
            raise BridgeError('Empty assembly target changed during preflight')
    elif len(active)!=1 or any(snapshot.get(k)!=v for k,v in active[0]['snapshot'].items()):
        raise BridgeError('Assembly target changed during preflight')
    record('before.json',before)
    op={'schema':'edit.native-operation/v1','stage':'assembly','operation_id':'assembly-import-'+uuid.uuid4().hex,
        'tool':'lab_import_compiled_assembly','arguments':{**request,'expected_project_revision':before['revision']},
        'target':{'project_path':snapshot['projectPath'],'sequence_id':snapshot['sequenceId'],'expected_revision':snapshot['revision']},
        'intended_changes':['Import one exact compiler-derived sequence with linked native AV'],
        'protected_state':['All existing sequences, source/timeline clocks, settings and effects; no activation']}
    imported=execute_operation(client,op,output_dir/'import-operation.json')
    if imported.get('provenance')!=proof['provenance']:raise BridgeError('Native import provenance differs from the prepared compiler chain')
    sid=imported['sequence_id']
    after=client.inspect('inspect_project_sequences',{'project_path':snapshot['projectPath']})['data'];record('after.json',after)
    created=unchanged_projects(before,after,sid)
    if created['snapshot']!=imported.get('snapshot'):raise BridgeError('Imported sequence changed after native dispatch')
    links=client.inspect('inspect_assembly_links',{'project_path':snapshot['projectPath'],'sequence_id':sid})['data'];record('native-links.json',links)
    result=validator.verify_native(proof['expectation'],links,after,snapshot['projectPath'],sid);record('structure-readback.json',result)
    fresh=client.inspect('inspect_project_sequences',{'project_path':snapshot['projectPath']})['data']
    if fresh!=after:raise BridgeError('Project changed during independent assembly readback')
    # Revalidate original inputs after native work; failure retains the original
    # operation receipt and partial state, never another import attempt.
    if validator.validate_compiled_packet(request['xml_path'],request['xml_sha256'],request['expected_path'],request['expected_sha256'],client.profile.fixture_root,request['resolved_path'],request['resolved_sha256'],request['gap_frames'])!=proof:
        raise BridgeError('Compiler chain changed during assembly import')
    active=client.inspect('lab_snapshot',{})
    if active['projectPath']!=snapshot['projectPath'] or active['sequenceId']!=snapshot['sequenceId']:raise BridgeError('Unexpected activation before assembly checkpoint save')
    save={'schema':'edit.native-operation/v1','stage':'assembly','operation_id':op['operation_id']+'-save','tool':'save_project','arguments':{},
          'target':{'project_path':active['projectPath'],'sequence_id':active['sequenceId'],'expected_revision':active['revision']},
          'intended_changes':['Save the independently verified linked assembly'],'protected_state':['All timeline state']}
    execute_operation(client,save,output_dir/'save-operation.json')
    saved=client.inspect('inspect_project_sequences',{'project_path':snapshot['projectPath']})['data'];record('after-save.json',saved)
    if saved!=after:raise BridgeError('Project changed during save; inspect original receipts')
    handoff=write_creation_handoff(output_dir/'stage-handoff.json',stage='assembly',project_before=before,project_after=saved,sequence_id=sid,sequence_revision=imported['sequence_revision'],receipt=output_dir/'import-operation.json')
    result={'schema':'edit.native-assembly-result/v1','status':'IMPORTED_SAVED_REOPEN_AND_REVIEW_REQUIRED','project_path':snapshot['projectPath'],'sequence_id':sid,
            'native_item_map':result['items'],'stage_handoff':'stage-handoff.json','sequence_revision':handoff['after_revision'],
            'persistence':'reopen_not_run','rendered':'not_run','listening':'not_run','source_processing':'not_verified','editorial_approval':'not_recorded'}
    record('result.json',result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('xml-path','xml-sha256','expected-path','expected-sha256','resolved-path','resolved-sha256','output-dir'):parser.add_argument('--'+key,required=True)
    parser.add_argument('--gap-frames',type=int,required=True)
    parser.add_argument('--audio-plan',type=Path,help='Optional source-sample decisions pinned to this exact expected receipt; opts into the Assembly audio precision Lab extension')
    parser.add_argument('--bridge-profile', default=None, help='Premiere Agent default profile unless explicitly overridden')
    args=parser.parse_args();profile=Profile.load(args.bridge_profile)
    audio_plan=None
    if args.audio_plan:
        audio_plan=load_plan(args.audio_plan,args.expected_path,args.expected_sha256)
        expected=json.loads(Path(args.expected_path).read_text())
        for media in {expected['items'][c['assembly_item_index']]['media'] for c in audio_plan['cuts']}:
            streams=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','a:0','-show_entries','stream=codec_name,sample_rate','-of','json',media]))['streams']
            if len(streams)!=1 or not streams[0]['codec_name'].startswith('pcm_') or int(streams[0]['sample_rate'])!=audio_plan['sample_rate']:
                raise BridgeError('Prepare matching-rate PCM media before importing a sample-precision assembly')
        profile=replace(profile,command=(profile.command[0],str(Path(__file__).with_name('precision_bridge.mjs')),profile.cwd))
    # Use the validator supplied by the selected Premiere Agent implementation.
    # Exact input scope and compiler reproduction are enforced on both sides.
    sys.path.insert(0,str(Path(profile.cwd)/'scripts'))
    spec=importlib.util.spec_from_file_location('selected_lab_assembly_validator',Path(profile.cwd)/'scripts/validate-assembly-import.py')
    validator=importlib.util.module_from_spec(spec);spec.loader.exec_module(validator)
    request={key:getattr(args,key) for key in ('xml_path','xml_sha256','expected_path','expected_sha256','resolved_path','resolved_sha256','gap_frames')}
    client=PremiereBridge(profile)
    try:
        result=apply_assembly(client,request=request,output_dir=args.output_dir,validator=validator)
        if audio_plan:
            result=apply_audio_plan(client,result,audio_plan,expected,Path(args.output_dir)/'audio-precision',Path(args.output_dir)/'stage-handoff.json')
            with (Path(args.output_dir)/'precision-result.json').open('x') as f:json.dump(result,f,indent=2)
        print(json.dumps(result,indent=2))
    finally:client.close()


if __name__=='__main__':main()
