#!/usr/bin/env python3
"""Measure raw Premiere Level values on one explicitly owned disposable sequence.

Create the empty project through Premiere UI first. This helper uses the packaged
bridge and music validator; it never turns an assumed mapping into calibration.
Each failed attempt is retained and must be reconciled before another operation.
"""
import argparse
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import math
from pathlib import Path
import re
import sys
import uuid
import wave
import xml.etree.ElementTree as ET


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)


def setup(fixture, preset):
    source = fixture/'00_SOURCE/calibration-stereo.wav'
    if source.exists():
        raise ValueError('Fixture source already exists; do not recreate')
    source.parent.mkdir(parents=True, exist_ok=True)
    raw = bytearray()
    for i in range(4*48000):
        for hz in (440, 880):
            raw.extend(int((2**23-1)*0.25*math.sin(2*math.pi*hz*i/48000)).to_bytes(3, 'little', signed=True))
    with wave.open(str(source), 'wb') as audio:
        audio.setparams((2, 3, 48000, 0, 'NONE', 'not compressed'))
        audio.writeframes(raw)
    tree = ET.parse(preset)
    expected = {'ADBEAudioRatePerSecond':'48000', 'ADBEAudioNumChannels':'1', 'ADBEAudioSampleType':'2'}
    for key,value in expected.items():
        nodes=[n for n in tree.getroot().findall('ExporterParam') if n.findtext('ParamIdentifier')==key]
        if len(nodes)!=1 or nodes[0].findtext('ParamValue')!=value:
            raise ValueError('Expected vendor 48 kHz mono 24-bit PCM preset')
        if key=='ADBEAudioNumChannels':nodes[0].find('ParamValue').text='2'
    target=fixture/'10_WORK/stereo48-24.epr'
    if target.exists():raise ValueError('Preset output exists')
    tree.write(target,encoding='utf-8',xml_declaration=True)
    return {'source':str(source),'preset':str(target)}


def run(args):
    sys.path.insert(0,str(args.skills/'_shared'))
    from premiere_bridge import PremiereBridge, Profile, execute_operation
    spec=importlib.util.spec_from_file_location('owned_music',args.skills/'music/scripts/apply_native_music.py')
    music=importlib.util.module_from_spec(spec);spec.loader.exec_module(music)
    profile=Profile.load(args.profile)
    fixture=args.fixture.resolve();project=fixture/'10_WORK/ACQ_Music_Level_Calibration.prproj'
    if profile.mode!='lab' or not fixture.is_relative_to(Path(profile.fixture_root).resolve()):
        raise ValueError('Disposable lab profile and fixture root required')
    if args.action=='setup':return setup(fixture,args.preset_source)
    runtime=Path(profile.cwd)/'lab/runtime'
    client=PremiereBridge(profile)
    try:
        snapshot=client.inspect('lab_snapshot',{})
        if snapshot['projectPath']!=str(project):raise ValueError('Select the exact calibration project')
        if args.action=='lease':
            if (runtime/'writer.lock').exists():raise ValueError('Unresolved native writer; reconcile first')
            lease=json.loads((runtime/'lease.json').read_text())
            if lease.get('owner')!=args.owner or not lease.get('productionBridgeStopped'):
                raise ValueError('Existing exclusive ownership is required')
            write(fixture/'10_WORK/previous-lease.json',lease)
            lease.update(projectPath=str(project),expiresAt=(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat())
            temp=runtime/'lease.calibration-new.json';write(temp,lease);temp.replace(runtime/'lease.json')
            return {'leased':str(project),'owner':args.owner}
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',args.attempt):raise ValueError('Invalid attempt name')
        work=fixture/'10_WORK'/args.attempt
        work.mkdir()  # exclusive attempt; never replay
        def operate(tool,arguments,label,stage='music'):
            snap=client.inspect('lab_snapshot',{})
            if snap['projectPath']!=str(project):raise ValueError('Calibration project changed')
            op={'schema':'edit.native-operation/v1','stage':stage,'operation_id':'music-cal-'+uuid.uuid4().hex,
                'tool':tool,'arguments':arguments,'target':{'project_path':str(project),'sequence_id':snap['sequenceId'],'expected_revision':snap['revision']},
                'intended_changes':['isolated native gain calibration: '+label],
                'protected_state':['all other open projects; no production sequence mutation']}
            return execute_operation(client,op,work/(label+'.json'),120)
        source=fixture/'00_SOURCE/calibration-stereo.wav'
        if args.action=='build':
            if snapshot['sequenceId'] is not None:raise ValueError('Build requires a new empty calibration project')
            imported=operate('import_media',{'file_paths':[str(source)],'suppress_ui':True},'import','assembly')
            write(work/'import-result.json',imported)
            created=operate('create_sequence_from_clips',{'name':'ACQ Music Level Calibration','item_ids':[source.name]},'sequence','assembly')
            operate('set_active_sequence',{'sequence_id':created['id']},'select','assembly')
            operate('save_project',{},'save')
            state=music.inspect(client);write(work/'inspection.json',state)
            return {'sequence':created,'inspection':str(work/'inspection.json')}
        state=music.inspect(client)
        clips=[c for t in state['audio_tracks'] for c in t['clips']]
        if len(clips)!=1 or any(t['clips'] for t in state['snapshot']['tracks'] if t['kind']==0):
            raise ValueError('Calibration requires exactly one audio item and no video items')
        item=clips[0]
        if item['media_path']!=str(source) or item['start_ticks']!='0' or item['end_ticks']!=str(4*music.TPS) or item['source_in_ticks']!='0' or item['source_offset_ticks']!='0':
            raise ValueError('Calibration source or duration differs')
        parameter={f:item['level'][f] for f in music.PARAMETER_FIELDS}
        native=args.native_value
        if native is None or not math.isfinite(native) or not 0<=native<=1 or args.db is None or not math.isfinite(args.db):raise ValueError('Supply raw hypothesis and intended dB')
        request={f:item[f] for f in music.ITEM_FIELDS}
        request.update(parameter=parameter,keys=[{'ticks':item['source_in_ticks'],'value':native},{'ticks':item['source_out_ticks'],'value':native}])
        operate('lab_apply_music_envelope',request,'envelope')
        rendered=work/'rendered.wav'
        operate('export_sequence',{'output_path':str(rendered),'preset_path':str(fixture/'10_WORK/stereo48-24.epr'),'work_area_only':False},'export','export')
        calibration={'schema':'edit.music-level-calibration/v1','host_version':profile.host_version,'backend':'CEP/ExtendScript','parameter':parameter,
                     'samples':[{'db':args.db,'native_value':native,'source_wav':music.artifact(source),'rendered_wav':music.artifact(rendered),
                                 'native_receipt':music.artifact(work/'envelope.json'),'export_receipt':music.artifact(work/'export.json')}]}
        path=work/'calibration.json';write(path,calibration)
        result=music.calibrated_values(path,parameter,{args.db})
        write(work/'verified.json',{'nativeValues':result[0],'qualification':'measured PCM gain only; no editorial or human approval'})
        operate('save_project',{},'save')
        return {'calibration':str(path),'verifiedNativeValues':result[0]}
    finally:
        if not client.unsettled and not client.transport.pending:client.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['setup','lease','build','sample'])
    p.add_argument('--skills',type=Path,required=True);p.add_argument('--profile',type=Path,required=True)
    p.add_argument('--fixture',type=Path,required=True);p.add_argument('--owner',default='')
    p.add_argument('--preset-source',type=Path);p.add_argument('--attempt',default='build-v1')
    p.add_argument('--db',type=float);p.add_argument('--native-value',type=float)
    print(json.dumps(run(p.parse_args()),indent=2))
