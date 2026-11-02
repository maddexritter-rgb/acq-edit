import test from 'node:test';
import assert from 'node:assert/strict';
import {validateDialogueEffect,dialogueEffectScript,getDialogueTools} from '../integrations/premiere-agent/dist/lab/dialogue.js';
const request=()=>({node_id:'audio-1',source_id:'source-1',effect_name:'Single-band Compressor',action:'append',parameters:[]});
test('dialogue requires a guarded native operation',async()=>{
  assert.match((await getDialogueTools({}).lab_apply_dialogue_effect.handler(request())).error,/LAB_GUARD_REQUIRED/);
});
test('dialogue rejects arbitrary effects, nonfinite values and duplicate parameter identities',()=>{
  for(const mutate of [r=>r.effect_name='Arbitrary Effect',r=>r.node_id='',r=>r.action='remove',r=>r.parameters=[{name:'Gain',value:2}],r=>{r.action='configure';r.parameters=[{name:'Gain',value:NaN}]},r=>{r.action='configure';r.parameters=[{name:'Gain',value:1},{name:'Gain',value:2}]}]){let r=request();mutate(r);assert.throws(()=>validateDialogueEffect(r));}
});
test('native dialogue preserves cuts and all other component values',()=>{
  const script=dialogueEffectScript(request());
  for(const token of ['DIALOGUE_TARGET_CHANGED','DIALOGUE_EFFECT_EXISTS_RECONCILE','DIALOGUE_APPEND_READBACK_FAILED','DIALOGUE_PARAMETER_READBACK_FAILED','PROTECTED_DIALOGUE_STATE_CHANGED_PARTIAL_EXECUTION','__findQeClipByDomClip'])assert.ok(script.includes(token));
  for(const token of ['exportAsMediaDirect','changeMediaPath','removeClip','saveAs'])assert.ok(!script.includes(token));
});
