/** Typed binding to the existing exact export generator; no arbitrary script input. */
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const generator=fileURLToPath(new URL('./native_export_body.py',import.meta.url));
export function exportTools({sendCommand,buildToolScript},options){
 const text={type:'string',minLength:1};
 const base={type:'object',required:['project','sequence','state','in_ticks','out_ticks'],additionalProperties:false,properties:{project:text,sequence:text,state:{type:'object'},in_ticks:text,out_ticks:text}};
 const definitions={
 lab_inspect_export_state:{kind:'inspect',description:'Read exact active project/sequence export marks and bounded timeline state without editing. Does not prove rendered output.',parameters:{type:'object',additionalProperties:false,required:['project_path','sequence_id'],properties:{project_path:text,sequence_id:text}}},
 lab_export_exact_range:{kind:'export',description:'Export one exact tick range from the current timeline; reject stale baseline or existing output, restore and read back original marks even on failure. No content trimming, overwrite, blind retries or automatic approval. Verify decoded frames/audio after completion.',parameters:{type:'object',additionalProperties:false,required:['baseline','start_ticks','end_ticks','preset_path','output_path','sample_rate','frame_ticks'],properties:{baseline:base,start_ticks:text,end_ticks:text,preset_path:text,output_path:text,sample_rate:{type:'integer',minimum:1},frame_ticks:{type:'integer',minimum:1}}}}
 };
 return Object.fromEntries(Object.entries(definitions).map(([name,d])=>[name,{
 description:d.description,parameters:d.parameters,
 operationalCapability:{backend:'CEP/ExtendScript',backends:['cep','extendscript'],status:'experimental',minimumPremiereVersion:'26.3.0',hostVerificationRequired:true,notes:['Typed integration of the existing exact export generator; generator has bounded 25fps/48kHz evidence. This new wrapper needs per-run host/output verification.']},
 handler:async args=>{
  // Generation is pure Python validation; host dispatch is journaled by LabRuntime.
  const body=execFileSync('python3',[generator],{input:JSON.stringify({kind:d.kind,arguments:args}),encoding:'utf8',timeout:10000,maxBuffer:4*1024*1024});
  return sendCommand(buildToolScript('return __result((function(){'+body+'})());'),
   d.kind==='export'?{...options,timeoutMs:12*60*60*1000}:options);
 }
 }]));
}
