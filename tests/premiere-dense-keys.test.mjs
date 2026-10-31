import {test} from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {SNAPSHOT_FUNCTION} from '../integrations/premiere-agent/dist/lab/context.js';
import {motionHelpers} from '../integrations/premiere-agent/dist/lab/reframe.js';
import {getLabFreshReframeTools} from '../integrations/premiere-agent/dist/lab/reframe-apply.js';
function host(count) {
 const keys=Array.from({length:count},(_,i)=>({ticks:String(i*8467200000)}));
 const property={displayName:'Anchor Point',getValue:()=>[.5,.5],isTimeVarying:()=>true,getKeys:()=>keys,getValueAtKey:t=>[.3+Number(t.ticks)/8467200000/20000,.5]};
 const collection=items=>Object.assign(items,{numItems:items.length});
 const component={displayName:'Motion',matchName:'AE.ADBE Motion',properties:collection([property])};
 const clip={nodeId:'item',name:'source',projectItem:{nodeId:'source'},start:{ticks:'0'},end:{ticks:String(count*8467200000)},inPoint:{ticks:'0'},outPoint:{ticks:String(count*8467200000)},getSpeed:()=>1,disabled:false,components:collection([component])};
 const sequence={sequenceID:'s',videoTracks:Object.assign([{name:'V1',isLocked:()=>false,isMuted:()=>false,clips:collection([clip])}],{numTracks:1}),audioTracks:{numTracks:0},getSettings:()=>({videoFrameWidth:1080,videoFrameHeight:1920})};
 return {property,app:{project:{path:'/fixture.prproj',activeSequence:sequence,sequences:{0:sequence,numSequences:1}}}};
}
test('native snapshot and reframe readback retain all 7200 frame keys',()=>{
 const context=host(7200);
 const result=vm.runInNewContext(SNAPSHOT_FUNCTION+';__labSnapshot()',context);
 const keys=result.tracks[0].clips[0].components[0].properties[0].keys;
 assert.equal(keys.length,7200);assert.equal(keys.at(-1).ticks,String(7199*8467200000));
 const read=vm.runInNewContext(motionHelpers+';anchorKeys(property)',context);
 assert.equal(read.length,7200);assert.equal(read.at(-1).ticks,keys.at(-1).ticks);
});
test('native key bounds remain enforced without truncation',()=>{
 assert.throws(()=>vm.runInNewContext(SNAPSHOT_FUNCTION+';__labSnapshot()',host(10001)),/LAB_KEYFRAME_LIMIT/);
 assert.throws(()=>vm.runInNewContext(motionHelpers+';anchorKeys(property)',host(10001)),/KEY_LIMIT/);
 const schema=getLabFreshReframeTools({}).lab_apply_reframe_motion.parameters;
 assert.equal(schema.properties.items.items.properties.keys.maxItems,10000);
});

test('disconnected native recovery names only the ACQ Edit Agent',async()=>{
 const {mkdtempSync,writeFileSync,utimesSync,rmSync}=await import('node:fs');
 const {tmpdir}=await import('node:os');
 const {join}=await import('node:path');
 const {sendCommand}=await import('../integrations/premiere-agent/dist/bridge/file-bridge.js');
 const dir=mkdtempSync(join(tmpdir(),'acq-bridge-disconnected-'));
 try {
  for (const state of ['waiting','stale']) {
   const file=join(dir,'bridge-heartbeat.json');
   writeFileSync(file,JSON.stringify({protocolVersion:1,state:state==='stale'?'running':state}));
   if(state==='stale')utimesSync(file,new Date(0),new Date(0));
   const result=await sendCommand('throw Error("must never execute")',{tempDir:dir,timeoutMs:50,failFastOnUnreadyHeartbeat:true});
   assert.equal(result.success,false);assert.match(result.error,/ACQ Edit Agent/);assert.doesNotMatch(result.error,/MCP Bridge/);
  }
 } finally {rmSync(dir,{recursive:true,force:true});}
});
