#!/usr/bin/env python3
"""Apply frozen dialogue output gain using the packaged native Level primitives.

Calibration measures rendered output against source, including fixture routing.
The final real mix must still be measured: native parameter values alone do not
establish equal routing in another sequence. No music selection is performed.
"""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import sys
import uuid


def run(a):
    sys.path.insert(0, str(a.skills/'_shared'))
    from premiere_bridge import PremiereBridge, Profile, execute_operation
    spec=importlib.util.spec_from_file_location('native_level',a.skills/'music/scripts/apply_native_music.py')
    level=importlib.util.module_from_spec(spec);spec.loader.exec_module(level)
    read=lambda p:json.loads(Path(p).read_text())
    plan=read(a.plan);expected=read(a.baseline)
    gain=plan['audio']['gainDb']
    if isinstance(gain,bool) or not isinstance(gain,(float,int)) or not -12<=gain<=12:raise ValueError('Bounded explicit dialogue gain required')
    a.output.mkdir()
    def write(name,value):
        with (a.output/name).open('x') as f:json.dump(value,f,indent=2)
    client=PremiereBridge(Profile.load(a.profile))
    try:
        before=level.inspect(client)
        full=client.inspect('lab_snapshot',{})
        projected={k:expected[k] for k in before['snapshot']}
        if full!=expected or before['snapshot']!=projected or before['revision']!=expected['revision'] or before['project_path']!=str(a.project.resolve()) or before['sequence_id']!=a.sequence:raise ValueError('Native baseline changed')
        track=next(t for t in before['audio_tracks'] if t['index']==0)
        if track['locked'] or track['muted'] or track['transition_count']:raise ValueError('Dialogue track is not directly writable')
        items=track['clips'];cuts=plan['cuts']
        if len(items)!=len(cuts) or not items:raise ValueError('Dialogue count differs from frozen cuts')
        sources={s['id']:s for s in plan['sources']}
        requests=[]
        for item,cut in zip(items,cuts):
            source=sources[cut.get('audioSourceId',cut['sourceId'])]
            sample_ticks=level.TPS//48000
            clocks=(int(item['start_ticks']),int(item['end_ticks'])-int(item['start_ticks']),int(item['source_offset_ticks'])+int(item['source_in_ticks']))
            wanted=(cut['audioRecordSample']*sample_ticks,cut['audioSamples']*sample_ticks,cut['audioInSample']*sample_ticks)
            if clocks!=wanted or item['media_path']!=source['path'] or item['speed']!=1 or item['speed_reversed']:raise ValueError('Dialogue source clocks differ from frozen design')
            raw=item['level']
            # Imported native clips can enable animation without creating keys.
            if not raw or raw['keyframes_supported'] is not True or raw['keys'] or abs(raw['value']-0.1778279410038923)>1e-6:raise ValueError('Existing dialogue automation/gain requires a revision plan')
            descriptor={f:raw[f] for f in level.PARAMETER_FIELDS}
            values,evidence=level.calibrated_values(a.calibration,descriptor,{gain})
            request={f:item[f] for f in level.ITEM_FIELDS}
            request.update(parameter=descriptor,keys=[{'ticks':item['source_in_ticks'],'value':values[gain]},{'ticks':item['source_out_ticks'],'value':values[gain]}])
            requests.append(request)
        write('before.json',before)
        write('inputs.json',{'plan':level.artifact(a.plan),'baseline':level.artifact(a.baseline),'calibration':evidence,'gainDb':gain,'qualification':'Fixture output gain; real mix verification required'})
        state=before
        for i,request in enumerate(requests):
            current=level.inspect(client)
            if current!=state:raise ValueError('Intervening native changes; stop without replay')
            operation={'schema':'edit.native-operation/v1','stage':'music','operation_id':'dialogue-level-'+uuid.uuid4().hex,'tool':'lab_apply_music_envelope','arguments':request,
                'target':{'project_path':a.project.as_posix(),'sequence_id':a.sequence,'expected_revision':current['revision']},
                'intended_changes':['Frozen dialogue gain only, through calibrated native Level transport'],
                'protected_state':['All cuts, picture, captions, graphics, music and other audio properties']}
            verification={'operation':operation,'baseline':copy.deepcopy(current['snapshot'])}
            write(f'item-{i+1:02}-verification-plan.json',verification)
            execute_operation(client,operation,a.output/f'item-{i+1:02}.json',120)
            state=level.inspect(client);level.verify(verification,state)
            write(f'item-{i+1:02}-after.json',state)
        save={'schema':'edit.native-operation/v1','stage':'music','operation_id':'dialogue-save-'+uuid.uuid4().hex,'tool':'save_project','arguments':{},
              'target':{'project_path':a.project.as_posix(),'sequence_id':a.sequence,'expected_revision':state['revision']},
              'intended_changes':['Save verified dialogue gain'],'protected_state':['All timeline state']}
        execute_operation(client,save,a.output/'save.json',120)
        after=level.inspect(client)
        if state!=after:raise ValueError('Native state changed while saving')
        write('after.json',after)
        return {'items':len(items),'gainDb':gain,'nativeVerification':'only explicit dialogue Level properties changed','renderedMix':'pending','listening':'not performed','userApproved':False}
    finally:
        if not client.unsettled and not client.transport.pending:client.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('skills','profile','project','plan','baseline','calibration','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--sequence',required=True)
    print(json.dumps(run(p.parse_args()),indent=2))
