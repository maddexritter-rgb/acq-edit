/** Optional reference comparison. Its clock never changes the clip's comment clock. */
export function referenceView({button,video,panel,fetchReference,onOpen}){
 let version=null,generation=0,active=false,request=null;
 const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n};
 const stamp=s=>`${String(Math.floor(s/60)).padStart(2,'0')}:${(s%60).toFixed(2).padStart(5,'0')}`;
 function close(){generation++;active=false;button.setAttribute('aria-expanded','false');panel.hidden=true;video.pause();video.hidden=true}
 function reset(v){version=v;request=null;close();button.disabled=!v;panel.replaceChildren();video.removeAttribute('src');video.load()}
 function render(info){
  panel.replaceChildren();
  if(!info){panel.append(node('p','No verified reference is attached to this version.','muted'));return}
  panel.append(node('h2',`Reference for V${info.versionNumber} · ${info.sourceName}`),node('p',info.media.available?'Clip on the left · Reference on the right. Each has its own timeline; comments use the clip playhead.':'These observations use the reference timeline. Comments still use the clip playhead.','muted'));
  const status=node('p','','reference-media-status');status.setAttribute('role','status');panel.append(status);
  if(info.media.available){video.src=info.media.url;video.hidden=false;video.onerror=()=>{if(!active)return;status.textContent='The reference could not play. Its file may be unavailable or its format unsupported by this browser.'}}
  else status.textContent='Reference playback unavailable: '+info.media.error;
  if(info.recipe.unsupportedEffects.length){const missing=node('div',undefined,'reference-limitations');missing.append(node('strong','Effects not supported'));const list=node('ul');for(const effect of info.recipe.unsupportedEffects)list.append(node('li',effect));missing.append(list);panel.append(missing)}
  const observations=node('details');observations.open=true;observations.append(node('summary','Recorded style observations'));
  const list=node('div',undefined,'reference-observations'),renderGeneration=generation;
  for(const observation of info.recipe.segments){const row=node('div',undefined,'reference-observation'),jump=node('button',`${stamp(observation.start)}–${stamp(observation.end)}`);jump.disabled=!info.media.available;jump.setAttribute('aria-label',`Reference at ${stamp(observation.start)}: ${observation.category}`);jump.onclick=()=>{video.pause();const seek=()=>{if(renderGeneration!==generation||!active)return;video.currentTime=Math.min(observation.start,Number.isFinite(video.duration)?video.duration:observation.start)};if(video.readyState>=1)seek();else video.addEventListener('loadedmetadata',seek,{once:true})};row.append(jump,node('strong',observation.category.replaceAll('-',' ')),node('span',observation.basis==='observed'?'Observed':'Inferred','reference-basis'),node('p',observation.observation));list.append(row)}
  observations.append(list);panel.append(observations);
  const details=node('details',undefined,'reference-provenance');details.append(node('summary','About these reference notes'),node('p','These notes record the analysis used for this version. Reported viewing and listening are not human approval or proof that every effect was reproduced.'));
  details.append(node('p',`Snapshot SHA-256: ${info.snapshotSha256}`),node('p',`Source SHA-256: ${info.sourceSha256}`));panel.append(details);
 }
 button.onclick=async()=>{
  if(active){close();return}if(!version)return;
  active=true;onOpen();button.setAttribute('aria-expanded','true');panel.hidden=false;panel.replaceChildren(node('p','Loading this version’s reference…','muted'));
  const expected=generation;
  try{request??=fetchReference(version.id);const info=await request;if(expected!==generation||!active)return;render(info)}
  catch(e){if(expected!==generation||!active)return;request=null;panel.replaceChildren(node('p','Reference unavailable: '+e.message,'reference-media-status'))}
 };
 return {reset,close};
}
