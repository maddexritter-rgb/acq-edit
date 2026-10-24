import test from 'node:test';
import assert from 'node:assert/strict';
import {validatePlan} from '../dist/contracts.js';

function fixture(){
 const project={id:'project',backend:'filmcraft'};
 const plan={schema:'acq-edit/plan-v1',projectId:project.id,backend:project.backend,
  fps:{numerator:25,denominator:1},width:640,height:360,sampleRate:48000,
  editorial:{reviewed:true,sha256:'selection'},brain:{sha256:'brain'},sources:[{id:'source',projectId:project.id}],
  cuts:[{sourceId:'source',frames:175,sourceInFrame:0,recordFrame:0,audioInSample:0,audioSamples:336000,wordIds:['word'],boundaryEvidence:'Synthetic fixture'}],
  captions:[],captionContract:{path:'handoff.json',sha256:'hash',helperHashes:{}},
  captionVisibility:{schema:'acq-edit/caption-visibility-v1',owner:'caption-clips',reason:'Opening hook',evidence:'Synthetic fixture',hiddenRanges:[{startFrame:0,endFrame:126}]}};
 return {project,plan};
}
test('caption visibility publication validates owner, engine and exact frame ranges',()=>{
 const {project,plan}=fixture();validatePlan(plan,project);
 for(const hiddenRanges of [[],[{startFrame:-1,endFrame:1}],[{startFrame:0,endFrame:176}],[{startFrame:0.5,endFrame:2}],[{startFrame:0,endFrame:5},{startFrame:4,endFrame:6}]]){
  assert.throws(()=>validatePlan({...plan,captionVisibility:{...plan.captionVisibility,hiddenRanges}},project),/caption range/);
 }
 for(const change of [{owner:'text-hook'},{reason:''},{evidence:null}])assert.throws(()=>validatePlan({...plan,captionVisibility:{...plan.captionVisibility,...change}},project),/handoff/);
 assert.throws(()=>validatePlan({...plan,captionContract:undefined},project),/ownership/);
 assert.throws(()=>validatePlan({...plan,backend:'resolve'},{...project,backend:'resolve'}),/ownership/);
});
test('caption visibility can be absent on a restored plan',()=>{
 const {project,plan}=fixture();delete plan.captionVisibility;validatePlan(plan,project);
});
