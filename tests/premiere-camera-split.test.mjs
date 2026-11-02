import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {validateCameraSplit,cameraSplitScript,getCameraSplitTools,CAMERA_SOURCE_ROWS} from '../integrations/premiere-agent/dist/lab/camera-split.js';
test('native Graphics without a project item do not hide original camera source evidence',()=>{
 const clips=Object.assign([{nodeId:'graphic',projectItem:null,isSpeedReversed:()=>false},{nodeId:'camera',isSpeedReversed:()=>false,projectItem:{nodeId:'source',getMediaPath:()=>'/original.mov',isOffline:()=>false,isSequence:()=>false}}],{numItems:2});
 const s={videoTracks:Object.assign([{clips}],{numTracks:1})};const rows=vm.runInNewContext(CAMERA_SOURCE_ROWS+'read()',{s});
 assert.equal(rows[0].item.media_path,null);assert.equal(rows[0].item.offline,null);assert.equal(rows[1].item.media_path,'/original.mov');assert.equal(rows[1].item.is_sequence,false);
});
const frame=10594584000;
function request(){return {name:'Split_01',start_ticks:'0',end_ticks:String(frame*2),frame_ticks:String(frame),tracks:[1,2,3],panels:[0,1].map(i=>({source_id:'camera-'+i,media_path:'/project/source-'+i+'.mov',source_in_ticks:String(frame*10),source_out_ticks:String(frame*12),scale:90,anchor_keys:[[0.5,0.5],[0.51,0.5]]}))};}
test('accepts rational 23.976 native frame clocks with independent source panels',()=>{assert.doesNotThrow(()=>validateCameraSplit(request()));});
test('rejects sparse keys, changed clocks and overlapping overlay roles before dispatch',()=>{
 for(const mutate of [r=>r.panels[0].anchor_keys.pop(),r=>r.panels[0].source_out_ticks=String(frame*13),r=>r.start_ticks='1',r=>r.tracks=[1,1,2],r=>r.panels[1].anchor_keys[0][0]=NaN,r=>r.panels[0].scale=Infinity,r=>r.panels[0].source_id='',r=>r.panels[0].media_path='relative.mov',r=>r.panels.pop()]){const r=request();mutate(r);assert.throws(()=>validateCameraSplit(r));}
});
test('refuses scripts and names that could escape bounded native construction',()=>{const r=request();r.name='bad";app.project.closeDocument()';assert.throws(()=>cameraSplitScript(r));});
test('tool refuses execution without an exclusive Lab guard',async()=>{const result=await getCameraSplitTools({}).lab_place_camera_split.handler(request());assert.equal(result.success,false);assert.match(result.error,/LAB_GUARD_REQUIRED/);});
test('generated native contract preserves dialogue and shares the top nest with its shadow',()=>{
 const s=cameraSplitScript(request());
 for(const requirement of ['PANEL_DUPLICATED_AUDIO','PANEL_SOURCE_CLOCK_READBACK','PANEL_KEY_READBACK','OVERLAY_OCCUPIED','PROTECTED_MASTER_CHANGED','UNRELATED_SEQUENCE_CHANGED','SPLIT_ALREADY_EXISTS_RECONCILE','SHADOW_PARAMETER_READBACK'])assert.ok(s.includes(requirement));
 assert.ok(s.includes('panel:0,y:0.25,scale:115'));assert.ok(s.includes('panel:0,y:0.25,scale:100'));
 assert.ok(!s.includes('exportAsMediaDirect'));assert.ok(!s.includes('app.project.save()'));
});
