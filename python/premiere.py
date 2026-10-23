"""Guarded Agent Lab adapter. Uses canonical scope/lease and stage owners."""
import sys
from pathlib import Path
from common import *
sys.path.insert(0,str(SKILLS/'_shared'))
from premiere_bridge import Profile,PremiereBridge,execute_operation
class Adapter:
 def __init__(self,config):self.config=config;self.profile=Profile.load(config.get('premiereProfile'))
 def doctor(self):
  client=PremiereBridge(self.profile)
  try:return {'backend':'premiere','ping':client.inspect('ping',{}),'snapshot':client.inspect('lab_snapshot',{}),'profileMode':self.profile.mode}
  finally:client.close()
 def inspect(self,project,packet):
  client=PremiereBridge(self.profile)
  try:
   state=client.inspect('lab_snapshot',{});require(state['projectPath']==str(inside(project['root'],packet['nativeProject'])),'Wrong native Premiere project');return {'state':state,'fingerprint':fingerprint(state)}
  finally:client.close()
 def execute(self,project,packet):
  require(self.profile.mode=='scoped-edit','Production stages require scoped-edit profile');state=self.inspect(project,packet);require(state['fingerprint']==packet['expectedFingerprint'],'Native state changed; reconcile user edits')
  # Each operation was compiled by its owning canonical skill. The bridge checks exact
  # project, stage, input/output paths and the single-writer lease for every operation.
  receipts=[];client=PremiereBridge(self.profile)
  try:
   for index,operation in enumerate(packet['operations']):
    require(operation['stage'] in ['assembly','reframe','captions','music','export'],'Unknown stage owner');receipt=inside(project['root'],Path(packet['receiptDirectory'])/f'{index:03}.json');require(not receipt.exists(),'Operation receipt exists; reconcile instead of replaying');receipts.append(execute_operation(client,operation,receipt,timeout=packet.get('timeoutSeconds',120)))
  finally:client.close()
  return {'receipts':receipts,'status':'inspect-native-state-before-publishing'}
 build=execute
 revise=execute
 render=execute
