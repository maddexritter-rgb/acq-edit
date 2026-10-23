import {sendCommand,type BridgeOptions} from '../bridge/file-bridge.js';
import {buildToolScript} from '../bridge/script-builder.js';
import {labContext} from './context.js';
import {capability} from './reframe.js';
export function getReframeFrameTools(options:BridgeOptions){return {
 lab_export_reframe_frames:{
  description:'Export up to 96 explicitly selected timeline frames through Premiere for native crop QA. Output directory is guard-checked; refuses existing files. Does not alter timeline content. Returned files prove rendered pixels, not human review.',
  parameters:{type:'object',additionalProperties:false,required:['output_dir','ticks'],properties:{output_dir:{type:'string'},ticks:{type:'array',minItems:1,maxItems:96,items:{type:'string',pattern:'^[0-9]{1,18}$'}}}},
  operationalCapability:{...capability,backends:['cep','extendscript','qe']},
  handler:async(args:{output_dir:string,ticks:string[]})=>{
   if(!labContext.getStore())return {success:false,error:'LAB_GUARD_REQUIRED'};
   if(!args.output_dir.startsWith('/')||!Array.isArray(args.ticks)||!args.ticks.length||args.ticks.length>96||args.ticks.some(x=>!/^\d{1,18}$/.test(x)))return {success:false,error:'INVALID_FRAMES'};
   const literal=JSON.stringify(args).replace(/\u2028/g,'\\u2028').replace(/\u2029/g,'\\u2029');
   return sendCommand(buildToolScript(`var r=${literal},s=app.project.activeSequence,dir=new Folder(r.output_dir),out=[];if(!dir.exists)throw new Error('OUTPUT_DIRECTORY_REQUIRED');
    for(var i=0;i<r.ticks.length;i++){if(Number(r.ticks[i])>=Number(s.end)||Number(r.ticks[i])%Number(s.timebase)!==0)throw new Error('INVALID_FRAME_GRID');if(new File(dir.fsName+'/frame_'+i+'.png').exists)throw new Error('FRAME_ALREADY_EXISTS');}
    for(var i=0;i<r.ticks.length;i++){var f=__exportStillFrame(dir.fsName+'/frame_'+i+'.png',r.ticks[i]);if(!f.ok)throw new Error('NATIVE_FRAME_EXPORT_FAILED '+f.error);out.push({ticks:r.ticks[i],path:f.path});}return __result({frames:out,rendered:true,visually_reviewed:false});`),{...options,timeoutMs:Math.max(60000,args.ticks.length*30000)});
  }
 }
};}
