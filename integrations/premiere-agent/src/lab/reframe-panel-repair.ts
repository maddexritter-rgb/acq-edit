import {sendCommand,type BridgeOptions} from '../bridge/file-bridge.js';
import {buildToolScript} from '../bridge/script-builder.js';
import {SNAPSHOT_FUNCTION,labContext} from './context.js';
import {capability,motionHelpers} from './reframe.js';
export function getPanelGeometryTools(options:BridgeOptions){return {lab_update_static_panel_geometry:{
 description:'Update only static Motion and left/right Crop on existing native panel items. Exact guarded baseline, preflight all items, direct parameter readback and protected-state comparison. No source or audio edits.',
 parameters:{type:'object',additionalProperties:false,required:['items'],properties:{items:{type:'array',minItems:1,maxItems:80,items:{type:'object',additionalProperties:false,required:['node_id','anchor','position','scale','left','right'],properties:{node_id:{type:'string'},anchor:{type:'array',minItems:2,maxItems:2,items:{type:'number'}},position:{type:'array',minItems:2,maxItems:2,items:{type:'number'}},scale:{type:'number',minimum:1,maximum:500},left:{type:'number',minimum:0,maximum:99},right:{type:'number',minimum:0,maximum:99}}}}}},operationalCapability:capability,
 handler:async(args:{items:{node_id:string,anchor:number[],position:number[],scale:number,left:number,right:number}[]})=>{
 if(!labContext.getStore())return {success:false,error:'LAB_GUARD_REQUIRED'};
 const ids=new Set();if(!Array.isArray(args.items)||!args.items.length||args.items.length>80)return {success:false,error:'INVALID_ITEMS'};
 for(const r of args.items){if(!r.node_id||ids.has(r.node_id)||![r.anchor,r.position].every(a=>a.length===2&&a.every(x=>Number.isFinite(x)&&x>=0&&x<=1))||!Number.isFinite(r.scale)||r.scale<1||r.scale>500||![r.left,r.right].every(x=>Number.isFinite(x)&&x>=0&&x<100)||r.left+r.right>=100)return {success:false,error:'INVALID_GEOMETRY'};ids.add(r.node_id);}
 const literal=JSON.stringify(args.items).replace(/\u2028/g,'\\u2028').replace(/\u2029/g,'\\u2029');
 return sendCommand(buildToolScript(`${SNAPSHOT_FUNCTION}${motionHelpers}
 var requests=${literal},before=__labSnapshot(),s=app.project.activeSequence,checked=[];
 function prop(c,fxName,name){var p=null;for(var f=0;f<c.components.numItems;f++)if(c.components[f].displayName===fxName)for(var j=0;j<c.components[f].properties.numItems;j++)if(c.components[f].properties[j].displayName===name){if(p)throw new Error('AMBIGUOUS_PROPERTY');p=c.components[f].properties[j];}if(!p||p.isTimeVarying())throw new Error('STATIC_PROPERTY_REQUIRED');return p;}
 for(var i=0;i<requests.length;i++){var r=requests[i],f=__findClip(r.node_id);if(!f||f.trackType!=='video'||s.videoTracks[f.trackIndex].isLocked())throw new Error('TARGET_MISSING_OR_LOCKED');var c=f.clip;checked.push({r:r,properties:[prop(c,'Motion','Anchor Point'),prop(c,'Motion','Position'),prop(c,'Motion','Scale'),prop(c,'Crop','Left'),prop(c,'Crop','Right')],values:[r.anchor,r.position,r.scale,r.left,r.right]});}
 for(var i=0;i<checked.length;i++)for(var k=0;k<5;k++){var x=checked[i],v=x.values[k],p=x.properties[k];p.setValue(v,false);var actual=p.getValue();if(k<2?!pair(actual,v):Math.abs(actual-v)>0.00002)throw new Error('PANEL_GEOMETRY_READBACK_FAILED');}
 var after=__labSnapshot();
 for(var t=0;t<before.tracks.length;t++)if(before.tracks[t].kind===0)for(var c=0;c<before.tracks[t].clips.length;c++){var old=before.tracks[t].clips[c],cur=after.tracks[t].clips[c],target=false;for(var i=0;i<requests.length;i++)if(old.id===requests[i].node_id)target=true;if(!target)continue;for(var f=0;f<old.components.length;f++){var fx=old.components[f];for(var p=0;p<fx.properties.length;p++){var name=fx.properties[p].name;if((fx.name==='Motion'&&(name==='Anchor Point'||name==='Position'||name==='Scale'))||(fx.name==='Crop'&&(name==='Left'||name==='Right')))cur.components[f].properties[p]=fx.properties[p];}}}
 if(JSON.stringify(before)!==JSON.stringify(after))throw new Error('PROTECTED_STATE_CHANGED');return __result({updated:checked.length,verification:'static_panel_geometry_and_protected_state'});`),options);
 }
}};}
