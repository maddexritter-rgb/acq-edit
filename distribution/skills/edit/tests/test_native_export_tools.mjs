import test from 'node:test';
import assert from 'node:assert/strict';
import {exportTools} from '../scripts/native_export_tools.mjs';
test('export tools expose data schemas without raw-script inputs',()=>{
 const tools=exportTools({},{});
 assert.equal(tools.lab_export_exact_range.parameters.additionalProperties,false);
 assert.equal('script' in tools.lab_export_exact_range.parameters.properties,false);
 assert.equal('code' in tools.lab_inspect_export_state.parameters.properties,false);
});
test('inspection generates a target-bound script with escaped identities',async()=>{
 let sent;
 const tools=exportTools({buildToolScript:x=>x,sendCommand:async x=>{sent=x;return {success:true,data:{}};}},{});
 await tools.lab_inspect_export_state.handler({project_path:'/a";throw.prproj',sequence_id:'seq'});
 assert.match(sent,/TARGET_CHANGED/);assert.ok(sent.includes('a\\";throw.prproj'));
});
test('invalid export frame grid fails before dispatch',async()=>{
 let calls=0;
 const tools=exportTools({buildToolScript:x=>x,sendCommand:async()=>{calls++;}},{});
 await assert.rejects(()=>tools.lab_export_exact_range.handler({baseline:{},start_ticks:'1',end_ticks:'10',preset_path:'/p.epr',output_path:'/o.mp4',sample_rate:48000,frame_ticks:10}));
 assert.equal(calls,0);
});
