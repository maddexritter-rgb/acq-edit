#!/usr/bin/env python3
"""Validate project identity before importing the one selected native adapter."""
import argparse
import importlib
import json
import sys
import fcntl
import os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from common import read,inside,require


def execute(action,backend,config_path,project_path=None,packet_path=None):
    require(action != 'hooks', 'Opening text hooks have been removed from this toolkit')
    config=read(config_path)
    if config.get('python'):os.environ['ACQ_EDIT_SHARED_PYTHON']=config['python']
    if action=='doctor':return importlib.import_module(backend).Adapter(config).doctor()
    require(project_path and packet_path,'Native operations require a project and packet')
    project=read(project_path)
    require(project['backend']==backend,'Backend is fixed within a project')
    if os.environ.get('ACQ_EDIT_NATIVE_OPERATION_DIR'):
        import uuid
        operation_id=os.environ.get('ACQ_EDIT_NATIVE_OPERATION_ID','')
        require(str(uuid.UUID(operation_id))==operation_id,'Invalid native operation identity')
        directory=inside(Path(project['root'])/'10_WORK',os.environ['ACQ_EDIT_NATIVE_OPERATION_DIR'])
        require(directory.name==operation_id and directory.parent.name=='native-operations' and directory.is_dir(),'Native operation journal differs from project')
    packet=read(inside(project['root'],packet_path))
    require(not (action=='revise' and packet.get('kind') in ('text-hook','text-hook-remove')), 'Opening text hooks have been removed; preserve legacy projects and use their pinned toolkit version')
    if action=='reconcile':
        require(backend=='premiere','Dedicated native reconciliation is currently Premiere-only')
        packet={**packet,'_evidencePath':str(inside(project['root'],packet_path))}
    lock=Path(project['root'])/'10_WORK/native.lock'
    with lock.open('a') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if action in ('compile', 'captions', 'reference'):
            # These branches only prepare artifacts; they never instantiate an editor adapter.
            try:
                if action == 'compile':
                    from assembly_plan import compile_plan as prepare
                elif action == 'captions':
                    from caption_plan import prepare_plan as prepare
                else:
                    from reference_style import prepare_plan as prepare
                return prepare(project, packet)
            except Exception as error:
                from common import sha
                return {'schema': 'acq-edit/preparation-failure-v1', 'status': 'validation-failed',
                        'action': action, 'projectId': project['id'], 'backend': backend,
                        'packetSha256': sha(inside(project['root'], packet_path)),
                        'nativeEditorStarted': False, 'error': str(error),
                        'repair': 'Correct the input in a new artifact; preserve this attempt and retry preparation.'}
        adapter=importlib.import_module(backend).Adapter(config)
        require(callable(getattr(adapter,action,None)),f'{backend} does not support native {action}; no other engine was selected')
        return getattr(adapter,action)(project,packet)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['doctor','compile','captions','hooks','reference','inspect','open','build','revise','render','complete','reconcile'])
    parser.add_argument('--backend',choices=['filmcraft','premiere','resolve'],required=True)
    parser.add_argument('--config',required=True)
    parser.add_argument('--project');parser.add_argument('--packet')
    args=parser.parse_args()
    try:
        print(json.dumps(execute(args.action,args.backend,args.config,args.project,args.packet),indent=2))
        return 0
    except Exception as error:
        print(json.dumps({'status':'failed','error':str(error),'retrySafe':False}),file=sys.stderr)
        return 1


if __name__=='__main__':sys.exit(main())
