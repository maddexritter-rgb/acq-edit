import {test} from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {ASSEMBLY_LINK_SNAPSHOT, validNativeResponse} from '../integrations/premiere-agent/dist/lab/assembly-links.js';
function fixture(){
 const collection=(items,key)=>Object.assign(items,{[key]:items.length});
 const source={nodeId:'source',getMediaPath:()=>'/source.mov',isOffline:()=>false};
 const item=id=>({nodeId:id,projectItem:source,getSpeed:()=>1,isSpeedReversed:()=>false,disabled:false,start:{ticks:'0'},end:{ticks:'100'},inPoint:{ticks:'500'},outPoint:{ticks:'600'}});
 const v=item('video'),a=item('audio'),g=item('graphic');g.projectItem=null;g.getLinkedItems=()=>null;
 v.getLinkedItems=()=>collection([v,a],'numItems');a.getLinkedItems=()=>collection([v,a],'numItems');
 const track=items=>({clips:collection(items,'numItems')});
 const sequence={sequenceID:'seq',timebase:'100',videoTracks:collection([track([v]),track([g])],'numTracks'),audioTracks:collection([track([a])],'numTracks')};
 const ctx=vm.createContext({app:{project:{path:'/p.prproj',sequences:collection([sequence],'numSequences')}}});vm.runInContext(ASSEMBLY_LINK_SNAPSHOT,ctx);
 return {ctx,v,a,g};
}
test('explicit primary scope verifies native links without probing Graphics',()=>{const {ctx}=fixture();const result=vm.runInContext('__labAssemblyLinks("/p.prproj","seq",true)',ctx);assert.equal(result.items.length,2);assert.equal(result.scope,'primary_av_tracks');assert.ok(validNativeResponse(result,{project_path:'/p.prproj',sequence_id:'seq'}));});
test('default full scope still refuses unavailable Graphics links',()=>{const {ctx}=fixture();assert.throws(()=>vm.runInContext('__labAssemblyLinks("/p.prproj","seq",false)',ctx),/NATIVE_LINK_COLLECTION_UNAVAILABLE/);});
test('primary audio-video link failure is never skipped',()=>{const {ctx,v}=fixture();v.getLinkedItems=()=>null;assert.throws(()=>vm.runInContext('__labAssemblyLinks("/p.prproj","seq",true)',ctx),/NATIVE_LINK_COLLECTION_UNAVAILABLE/);});
test('nonreciprocal primary links remain rejected',()=>{const {ctx,a}=fixture();a.getLinkedItems=()=>({numItems:0});assert.throws(()=>vm.runInContext('__labAssemblyLinks("/p.prproj","seq",true)',ctx),/NATIVE_LINK_GROUP_INCONSISTENT/);});
