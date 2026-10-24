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
    lock=Path(project['root'])/'10_WORK/native.lock'
    with lock.open('a') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if action=='compile':
            from assembly_plan import compile_plan
            return compile_plan(project,packet)
        if action=='captions':
            from caption_plan import prepare_plan
            return prepare_plan(project,packet)
        adapter=importlib.import_module(backend).Adapter(config)
        return getattr(adapter,action)(project,packet)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['doctor','compile','captions','inspect','build','revise','render'])
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
