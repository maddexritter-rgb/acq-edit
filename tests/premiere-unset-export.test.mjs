import {test} from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import vm from 'node:vm';
const unset='-101606400000000000',step=8467200000;
function generated(overrides={}){
 const baseline={project:'/p.prproj',sequence:'seq',state:{tracks:[],settings:{}},in_ticks:unset,out_ticks:unset,...overrides};
 const run=spawnSync('python3',['-c',`import sys,json
sys.path.insert(0,'distribution/skills/edit/scripts')
from pp_export_clips import export_script
j=json.load(sys.stdin)
print(export_script(j,{'start_ticks':'0','end_ticks':'254016000000'},'/preset.epr','/clip.mp4',48000,8467200000))`],{input:JSON.stringify(baseline),encoding:'utf8'});
 if(run.status)throw Error(run.stderr);return {script:run.stdout,baseline};
}
function host(script,{end='254016000000',fail=false,changeMarks=false,inMark=unset,outMark=unset}={}){
 let writes=0,exports=0,mode;
 const seq={sequenceID:'seq',end,videoTracks:{numTracks:0},audioTracks:{numTracks:0},getSettings:()=>({}),getInPointAsTime:()=>({ticks:inMark}),getOutPointAsTime:()=>({ticks:outMark}),setInPoint:v=>{writes++;inMark=String(v*254016000000);},setOutPoint:v=>{writes++;outMark=String(v*254016000000);},exportAsMediaDirect:(p,pr,m)=>{exports++;mode=m;if(changeMarks)inMark='0';if(fail)throw Error('HOST_EXPORT_FAILURE');return 0;}};
 const context=vm.createContext({app:{project:{path:'/p.prproj',activeSequence:seq},encoder:{ENCODE_ENTIRE:0,ENCODE_IN_TO_OUT:1}},File:function(p){this.exists=p==='/preset.epr';}});
 return {run:()=>vm.runInContext('(function(){'+script+'})()',context),state:()=>({writes,exports,mode,inMark,outMark})};
}
test('whole unset sequence exports without ever mutating marks',()=>{const h=host(generated().script);h.run();assert.deepEqual(h.state(),{writes:0,exports:1,mode:0,inMark:unset,outMark:unset});});
test('duration mismatch refuses before export and mark mutations',()=>{const h=host(generated().script,{end:String(step*31)});assert.throws(h.run,/WHOLE_SEQUENCE_DURATION_MISMATCH/);assert.equal(h.state().exports,0);assert.equal(h.state().writes,0);});
test('failed whole export leaves unset markers untouched',()=>{const h=host(generated().script,{fail:true});assert.throws(h.run,/HOST_EXPORT_FAILURE/);assert.equal(h.state().writes,0);assert.equal(h.state().inMark,unset);});
test('unexpected host marker change fails postcondition',()=>{const h=host(generated().script,{changeMarks:true});assert.throws(h.run,/MARK_RESTORE_FAILED/);});
test('mixed unset and arbitrary negative marks still fail closed',()=>{assert.throws(()=>generated({in_ticks:'0'}),/Nonnegative decimal/);assert.throws(()=>generated({in_ticks:'-1',out_ticks:'-1'}),/Nonnegative decimal/);});
test('existing explicit marks restore after successful export',()=>{const g=generated({in_ticks:'8467200000',out_ticks:'16934400000'});const h=host(g.script,{inMark:g.baseline.in_ticks,outMark:g.baseline.out_ticks});h.run();assert.equal(h.state().mode,1);assert.equal(h.state().inMark,g.baseline.in_ticks);assert.equal(h.state().outMark,g.baseline.out_ticks);});
