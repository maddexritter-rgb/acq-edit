import {test} from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {graphicAssetScript,validateGraphicAsset} from '../integrations/premiere-agent/dist/lab/graphic-asset.js';
import {SNAPSHOT_FUNCTION} from '../integrations/premiere-agent/dist/lab/context.js';
const request={media_path:'/asset.png',media_sha256:'a'.repeat(64),track_index:1,track_id:'v2',start_ticks:'0',end_ticks:'1278547200000',width:1080,height:1920,frame_duration_ticks:'8467200000'};
function host({occupied=false,wrongCanvas=false,wrongMarks=false,corrupt=false,registered=false,explicit=false,quantized=false,consumed=false,nativeOrigin=0}={}){
 let imports=0,overwrites=0,protectedValue='original',inTicks='0',outTicks='0';
 const collection=a=>Object.defineProperty(a,'numItems',{get:()=>a.length});
 const source={nodeId:'asset',type:1,name:'asset.png',getMediaPath:()=>'/asset.png',isSequence:()=>false,isOffline:()=>false,setInPoint:()=>{inTicks='0';},setOutPoint:v=>{outTicks=wrongMarks?'1':String(Math.round(v*254016000000)-(quantized?7197120000:0));},getInPoint:()=>({ticks:inTicks}),getOutPoint:()=>({ticks:outTicks})};
 const children=collection(registered?[source]:[]);
 const clips=collection([{nodeId:'prior',start:{ticks:occupied?'0':request.end_ticks},end:{ticks:'2540160000000'}}]);
 const track={id:'v2',isLocked:()=>false,isMuted:()=>false,transitions:{numItems:0},clips,overwriteClip:()=>{overwrites++;if(corrupt)protectedValue='changed';const item={nodeId:'new',projectItem:source,start:{ticks:'0'},end:{ticks:outTicks},inPoint:{ticks:String(nativeOrigin)},outPoint:{ticks:String(nativeOrigin+Number(outTicks))},getSpeed:()=>1,isSpeedReversed:()=>false,disabled:false};let end=item.end;Object.defineProperty(item,'end',{get:()=>end,set:v=>{end=v;item.outPoint={ticks:String(nativeOrigin+Number(v.ticks))};}});clips.unshift(item);}};
 const seq={sequenceID:'seq',timebase:request.frame_duration_ticks,end:'2540160000000',getSettings:()=>({videoFrameWidth:wrongCanvas?1920:1080,videoFrameHeight:1920}),videoTracks:Object.assign([{clips:collection([])},track],{numTracks:2}),audioTracks:{numTracks:0}};
 const snapshot=()=>({protectedValue,tracks:[{kind:0,index:1,clips:clips.map(c=>({id:c.nodeId,start:c.start.ticks,end:c.end.ticks}))}]});
 if(consumed)clips[0].projectItem=source;
 const script=graphicAssetScript({...request,...(explicit?{source_item_id:'asset'}:{})}).replace(SNAPSHOT_FUNCTION,'function __labSnapshot(){return snapshot();}');
 const context={snapshot,app:{project:{path:'/project.prproj',activeSequence:seq,sequences:Object.assign([seq],{numSequences:1}),rootItem:{nodeId:'root',name:'root',type:2,children},importFiles:()=>{imports++;children.push(source);}}},Time:function(){this.ticks='0';Object.defineProperty(this,'seconds',{get:()=>Number(this.ticks)/254016000000});},__result:data=>({success:true,data}),__error:error=>({success:false,error})};
 return {run:()=>vm.runInNewContext(script,context),state:()=>({imports,overwrites,protectedValue,items:clips.length})};
}
test('places only one new graphic and preserves following caption',()=>{const h=host();assert.equal(h.run().success,true);assert.deepEqual(h.state(),{imports:1,overwrites:1,protectedValue:'original',items:2});});
test('occupied range and changed canvas refuse before import',()=>{for(const options of [{occupied:true},{wrongCanvas:true}]){const h=host(options);assert.equal(h.run().success,false);assert.equal(h.state().imports,0);}});
test('registered asset refuses duplicate submission',()=>{const h=host({registered:true});assert.match(h.run().error,/ALREADY_REGISTERED/);assert.equal(h.state().imports,0);});
test('source time mismatch leaves import for reconciliation without placement',()=>{const h=host({wrongMarks:true});assert.match(h.run().error,/SOURCE_MARK_READBACK/);assert.equal(h.state().overwrites,0);assert.equal(h.state().imports,1);});
test('protected change after placement never reports success',()=>{const h=host({corrupt:true});assert.match(h.run().error,/PROTECTED_STATE_CHANGED_AFTER_GRAPHIC/);assert.equal(h.state().overwrites,1);});
test('rejects non-frame times, unsupported files and unsafe numeric clocks',()=>{for(const changes of [{end_ticks:'1'},{media_path:'/asset.mp4'},{end_ticks:'9223372036854775807'},{track_index:-1}])assert.throws(()=>validateGraphicAsset({...request,...changes}));});

test('quantized still marks extend only the new native timeline item',()=>{const h=host({quantized:true});const r=h.run();assert.equal(r.success,true);assert.equal(r.data.native_item_out_ticks,request.end_ticks);});
test('explicit retained unused source avoids a second import',()=>{const h=host({registered:true,explicit:true,quantized:true});assert.equal(h.run().success,true);assert.equal(h.state().imports,0);});
test('an existing source with consumers cannot have its marks changed',()=>{const h=host({registered:true,explicit:true,consumed:true});assert.match(h.run().error,/HAS_CONSUMERS/);assert.equal(h.state().overwrites,0);});

test('still-image native source origin is preserved rather than forced to zero',()=>{const h=host({quantized:true,nativeOrigin:914449132800000});const r=h.run();assert.equal(r.success,true);assert.equal(r.data.native_item_in_ticks,'914449132800000');assert.equal(Number(r.data.native_item_out_ticks)-Number(r.data.native_item_in_ticks),Number(request.end_ticks));});
