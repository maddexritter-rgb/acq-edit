#!/usr/bin/env python3
"""Run one new, scoped native split regression from a supplied exact plan."""
import argparse,json,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--toolkit',type=Path,required=True);p.add_argument('--template',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--id',required=True);p.add_argument('--name',required=True);a=p.parse_args()
sys.path.insert(0,str(a.toolkit/'.local/skills/_shared'))
from premiere_bridge import Profile,PremiereBridge,execute_operation
client=PremiereBridge(Profile.load(a.toolkit/'.local/premiere-profile.json'))
a.output.mkdir(exist_ok=False);plan=json.loads(a.template.read_text());plan['operation_id']=a.id;plan['arguments']['name']=a.name
try:
 state=client.inspect('inspect_project_sequences',{'project_path':plan['target']['project_path']});(a.output/'before-project.json').write_text(json.dumps(state,indent=2))
 snap=client.inspect('lab_snapshot',{})
 if snap['sequenceId']!=plan['target']['sequence_id']:
  activate={'schema':'edit.native-operation/v1','stage':'reframe','operation_id':a.id+'-activate','tool':'set_active_sequence','arguments':{'sequence_id':plan['target']['sequence_id']},'target':{'project_path':snap['projectPath'],'sequence_id':snap['sequenceId'],'expected_revision':snap['revision']},'intended_changes':['Activate intended regression master'],'protected_state':['All source items and edits']}
  (a.output/'activate.json').write_text(json.dumps(activate,indent=2));execute_operation(client,activate,a.output/'activate-receipt.json')
 snap=client.inspect('lab_snapshot',{});plan['target']['expected_revision']=snap['revision']
 (a.output/'operation.json').write_text(json.dumps(plan,indent=2));result=execute_operation(client,plan,a.output/'receipt.json');print(json.dumps(result,indent=2))
finally:client.close()
