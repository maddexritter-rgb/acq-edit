#!/usr/bin/env python3
"""Export exact native review frames through the selected repository bridge."""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import sys
import uuid


def run(a):
    sys.path.insert(0,str(a.skills/'_shared'))
    from premiere_bridge import PremiereBridge,Profile,execute_operation
    rate=Fraction(a.rate)
    if rate<=0 or any(f<0 for f in a.frames):raise ValueError('Positive rate and nonnegative frames required')
    a.output.mkdir();client=PremiereBridge(Profile.load(a.profile))
    try:
        def call(tool,arguments,name):
            state=client.inspect('lab_snapshot',{})
            if state['projectPath']!=str(a.project.resolve()):raise ValueError('Exact project changed')
            if tool!='set_active_sequence' and state['sequenceId']!=a.sequence:raise ValueError('Exact sequence changed')
            operation={'schema':'edit.native-operation/v1','stage':'export','operation_id':'graphics-review-'+uuid.uuid4().hex,'tool':tool,'arguments':arguments,
                       'target':{'project_path':state['projectPath'],'sequence_id':state['sequenceId'],'expected_revision':state['revision']},
                       'intended_changes':[name+' for native graphic inspection'],'protected_state':['All existing timeline content and all prior sequences.']}
            return execute_operation(client,operation,a.output/(name+'.json'),120)
        call('set_active_sequence',{'sequence_id':a.sequence},'select')
        info=client.inspect('get_full_sequence_info',{'sequence_id':a.sequence})['data']
        if Fraction(254016000000,int(info['frameRate']['ticks']))!=rate:raise ValueError('Native frame rate differs')
        before=client.inspect('lab_snapshot',{})
        for frame in a.frames:
            if float(Fraction(frame,1)/rate)>=info['durationSeconds']:raise ValueError('Review frame outside sequence')
            image=a.output/f'frame-{frame:04}.png'
            call('export_frame',{'output_path':str(image),'time_seconds':float(Fraction(frame,1)/rate)},f'export-{frame:04}')
            if not image.is_file() or not image.stat().st_size:raise ValueError('Native frame missing')
        call('save_project',{},'save')
        after=client.inspect('lab_snapshot',{})
        if before!=after:raise ValueError('Native timeline changed while exporting review frames')
        (a.output/'inspection.json').write_text(json.dumps(after,indent=2))
        return {'frames':[str(a.output/f'frame-{f:04}.png') for f in a.frames],'timelineUnchanged':True,'visualReview':'not_performed','userApproved':False}
    finally:
        if not client.unsettled and not client.transport.pending:client.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('skills','profile','project','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--sequence',required=True);p.add_argument('--rate',required=True);p.add_argument('--frames',type=int,nargs='+',required=True)
    print(json.dumps(run(p.parse_args()),indent=2))
