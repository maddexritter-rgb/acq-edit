import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {makeAudioEdgeTool,validateAudioEdges,TPS} from '../scripts/native_audio_edges.mjs';
const step=TPS/48000n;
const request=()=>({sample_rate:48000,items:[{node_id:'a1',source_id:'source',media_path:'/source.wav',before:{start:'0',end:String(TPS),inPoint:String(TPS),outPoint:String(TPS*2n)},after:{start:String(step),end:String(TPS-step),inPoint:String(TPS+step),outPoint:String(TPS*2n-step)}}]});
test('one sample preserves source to timeline mapping',()=>assert.equal(validateAudioEdges(request()).items.length,1));
test('rejects millisecond-only rounding and lost sync',()=>{
 const r=request();r.items[0].after.start='1';assert.throws(()=>validateAudioEdges(r),/MISMATCH|SYNC/);
 const q=request();for(const k of ['start','inPoint'])q.items[0].after[k]=String(BigInt(q.items[0].after[k])+1n);assert.throws(()=>validateAudioEdges(q),/SAMPLE_GRID/);
});
test('rejects reordered identity, large rewrites and unsafe tick numbers',()=>{
 const r=request();r.items.push(structuredClone(r.items[0]));assert.throws(()=>validateAudioEdges(r),/UNIQUE/);
 const q=request();q.items[0].after.end='9007199254740992';assert.throws(()=>validateAudioEdges(q),/SAFE_TICK/);
});
function fixture({stale=false,video=false,keyframes=[],ignoreOut=false,collide=false,loseLinks=false,badRelink=false}={}){
 const r=request(),row=r.items[0];
 const clip={nodeId:'a1',disabled:false,projectItem:{nodeId:'source',getMediaPath:()=>'/source.wav',isOffline:()=>false},getSpeed:()=>1,isSpeedReversed:()=>false,components:{numItems:1,0:{properties:{numItems:1,0:{isTimeVarying:()=>true,getKeys:()=>keyframes}}}}};
 let linked=true;const selection=new Set();
 const picture={nodeId:'v1',projectItem:clip.projectItem};
 for(const c of [clip,picture]){c.getLinkedItems=()=>linked?{numItems:2,0:clip,1:picture}:null;c.setSelected=(yes)=>yes?selection.add(c):selection.delete(c);}
 for(const key of ['start','end','inPoint','outPoint']){let v={ticks:row.before[key]};Object.defineProperty(clip,key,{get:()=>v,set:x=>{if(!(ignoreOut&&key==='outPoint'))v=x;if(loseLinks)linked=false;}});}
 if(stale)clip.start={ticks:'1'};
 const track={isLocked:()=>false,clips:{numItems:1,0:clip}};
 if(collide){track.clips.numItems=2;track.clips[1]={nodeId:'peer',start:{ticks:'10'},end:{ticks:String(TPS)},inPoint:{ticks:'0'},outPoint:{ticks:String(TPS-10n)}};}
 const seq={audioTracks:{numTracks:1,0:track},getSelection:()=>[...selection],linkSelection:()=>{if(!badRelink)linked=selection.has(clip)&&selection.has(picture);}};
 const snap=()=>({settings:{audioSampleRate:{ticks:String(step)}},tracks:[{kind:video?0:1,clips:[{id:'a1',...Object.fromEntries(['start','end','inPoint','outPoint'].map(k=>[k,String(clip[k].ticks)]))}]}]});
 const tool=makeAudioEdgeTool({inspectPcm:()=>({sample_rate:48000}),buildToolScript:x=>x,snapshotFunction:'',sendCommand:async code=>{
  try{return vm.runInNewContext('(function(){'+code+'})()',{
   app:{project:{activeSequence:seq}},Time:function(){this.ticks='0'},__labSnapshot:snap,TICKS_PER_SECOND:Number(TPS),
   __findClip:id=>id==='v1'?{clip:picture,trackType:'video',trackIndex:0}:{clip,trackType:video?'video':'audio',trackIndex:0},__result:data=>({success:true,data}),
  });}catch(e){return {success:false,error:String(e)};}
 }},{});
 return {tool,r,clip};
}
test('exact native setter writes both source and timeline, including empty automation',async()=>{
 const {tool,r}=fixture();const got=await tool.handler(r);assert.equal(got.success,true);assert.deepEqual(JSON.parse(JSON.stringify(got.data.items[0].after)),r.items[0].after);
});
for(const [opts,message] of [[{stale:true},'STALE'],[{video:true},'AUDIO_TARGET'],[{keyframes:[{}]},'KEYFRAMED'],[{collide:true},'OVERLAP']]){
 test('preflight refuses '+message+' before mutation',async()=>{const {tool,r,clip}=fixture(opts);const before=String(clip.end.ticks);const got=await tool.handler(r);assert.equal(got.success,false);assert.match(got.error,new RegExp(message));assert.equal(clip.end.ticks,before);});
}
test('silent native setter failure is not accepted within one frame',async()=>{
 const {tool,r}=fixture({ignoreOut:true});const got=await tool.handler(r);assert.equal(got.success,false);assert.match(got.error,/EXACT_AUDIO_EDGE_READBACK_FAILED/);
});
test('restores only original reciprocal pair after setter unlinks it',async()=>{
 const {tool,r}=fixture({loseLinks:true});const got=await tool.handler(r);assert.equal(got.success,true);assert.equal(got.data.restored_link_pairs.length,1);
});
test('failed native relinking remains a failure despite correct geometry',async()=>{
 const {tool,r}=fixture({loseLinks:true,badRelink:true});const got=await tool.handler(r);assert.equal(got.success,false);assert.match(got.error,/PAIR_RESTORE_FAILED/);
});
