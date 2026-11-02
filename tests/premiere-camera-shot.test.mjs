import test from 'node:test';
import assert from 'node:assert/strict';
import {validateCameraShot,cameraShotScript,getCameraShotTools} from '../integrations/premiere-agent/dist/lab/camera-shot.js';
const f=10594584000;
const shot=()=>({name:'Shot_01',track_index:3,start_ticks:String(f*20),end_ticks:String(f*22),frame_ticks:String(f),source_id:'camera',media_path:'/camera.mov',source_in_ticks:String(f*100),source_out_ticks:String(f*102),scale:100,anchor_keys:[[.4,.5],[.401,.5]]});
test('native camera switch retains a dense source-clock curve',()=>assert.doesNotThrow(()=>validateCameraShot(shot())));
test('camera switch rejects clock mismatch, sparse keys and invalid destinations',()=>{
 for(const change of [r=>r.source_out_ticks=String(f*103),r=>r.start_ticks='1',r=>r.frame_ticks='0',r=>r.anchor_keys.pop(),r=>r.track_index=-1,r=>r.scale=NaN,r=>r.media_path='relative.mov',r=>r.name='x";app.project.closeDocument()',r=>r.anchor_keys[0][1]=Infinity]){const r=shot();change(r);assert.throws(()=>validateCameraShot(r));}
});
test('camera switching cannot dispatch without project authorization',async()=>assert.match((await getCameraShotTools({}).lab_place_tracked_camera_shot.handler(shot())).error,/LAB_GUARD_REQUIRED/));
test('native construction verifies exact residual ranges and all protected tracks',()=>{
 const s=cameraShotScript(shot());
 for(const marker of ['SHOT_RESIDUAL_RANGE_CHANGED','SHOT_PROTECTED_STATE_CHANGED','SHOT_UNRELATED_SEQUENCE_CHANGED','SHOT_SOURCE_CLOCK_READBACK','SHOT_KEY_READBACK'])assert.ok(s.includes(marker));
 assert.ok(!s.includes('save()'));assert.ok(!s.includes('exportAsMediaDirect'));
});
