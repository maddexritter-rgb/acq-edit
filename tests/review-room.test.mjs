import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
import {sessionRequest,jobPresentation} from '../web/activity.js';

// Execute the real browser entrypoint and its event handlers with a small DOM/network fixture.
// No extracted copies of save/project-switch logic: regressions in app.js run here directly.
class Element {
 constructor(){this.value='';this.textContent='';this.hidden=false;this.disabled=false;this.children=[];this.dataset={};this.classList={toggle(){}};this.previousElementSibling={};this.currentTime=0;this.paused=true}
 append(...nodes){this.children.push(...nodes)}
 replaceChildren(...nodes){this.children=[...nodes]}
 setAttribute(name,value){this[name]=value}
 focus(){}
 select(){this.selected=true}
 removeAttribute(name){delete this[name]}
 pause(){this.paused=true}
 load(){this.loaded=true}
 addEventListener(){}
}
async function room(revisionProcessing=true){
 const elements=new Map(),get=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id)};
 get('filter').value='all';
 const decisions=['yes','revise','no'].map(decision=>Object.assign(new Element(),{dataset:{decision}}));
 const initial={versionId:'v',revision:0,decision:null,notes:'',comments:[],updatedAt:''};
 const full={project:{id:'full',title:'Full',backend:'filmcraft'},clips:[{id:'c',number:1,title:'Clip',currentVersionId:'v',versions:[{id:'v',number:1,createdAt:'2026-10-27',feedback:initial}],pendingFeedback:[]}],jobs:[]};
 const empty={project:{id:'empty',title:'Empty',backend:'premiere'},clips:[],jobs:[]};
 const waiting={project:{id:'waiting',title:'Waiting',backend:'filmcraft'},clips:[{id:'waiting-clip',number:1,title:'Rendering',currentVersionId:null,versions:[]}],jobs:[]};
 const snapshots={full,empty,waiting},requests=[];let fault,reference;
 const fetch=async(url,options={})=>{
  requests.push({url,...options});
  if(url==='/api/capabilities')return response({revisionProcessing:!!revisionProcessing,mode:revisionProcessing==='session'?'session':revisionProcessing?'editing':'review-only'});
  if(url==='/api/projects')return response(Object.values(snapshots).map(s=>s.project));
  if(url.startsWith('/api/projects/')&&!url.endsWith('/revisions'))return response(snapshots[url.split('/').at(-1)]);
  if(url==='/api/feedback/v'){
   const {feedback,expectedRevision}=JSON.parse(options.body),current=full.clips[0].versions[0].feedback;
   const behavior=fault;fault=undefined;
   if(behavior)await behavior('before');
   if(expectedRevision!==current.revision)return response({error:'Feedback changed in another window'},false);
   full.clips[0].versions[0].feedback={...feedback,versionId:'v',revision:current.revision+1};
   if(behavior)await behavior('after');
   return response(full.clips[0].versions[0].feedback);
  }
  if(url.endsWith('/revisions')){const j={id:'job',state:'queued',execution:revisionProcessing==='session'?'session':'background',kind:'revision',snapshot:[],updatedAt:new Date().toISOString()};full.jobs=[j];return response(j)};
  return response({error:'Not found'},false);
 };
 function response(data,ok=true){return {ok,json:async()=>structuredClone(data)}}
 const context=vm.createContext({structuredClone,URL,Promise,console,fetch,crypto:globalThis.crypto,setInterval(){},location:{href:'http://127.0.0.1/?project=full'},history:{replaceState(){}},localStorage:{getItem(){},setItem(){}},window:{addEventListener(){}},document:{getElementById:get,createElement:()=>new Element(),querySelectorAll:()=>decisions},projectActivity:()=>({reserved:false,reservations:[]}),jobPresentation,sessionRequest,referenceView:()=>({reset:v=>{reference=v},close(){}})});
 const source=(await readFile(new URL('../web/app.js',import.meta.url),'utf8')).replace(/^import .*\n/gm,'');
 const app=await vm.runInContext(`(async()=>{${source}\nreturn {settled:()=>pending,state:()=>({projectId,versionId,dirty,draft})}})()`,context);
 return {get,app,decisions,requests,snapshots,reference:()=>reference,feedback:()=>full.clips[0].versions[0].feedback,fail:f=>{fault=f},type:note=>{get('notes').value=note;get('notes').oninput()},switch:async id=>{get('projects').value=id;await get('projects').onchange()}};
}

test('failed save keeps notes, blocks submission/navigation, and explicit retry persists them',async()=>{
 const r=await room();r.fail(()=>{throw Error('offline')});r.type('Keep my notes');await r.app.settled();
 assert.equal(r.app.state().dirty,1);assert.equal(r.get('retry-save').hidden,false);
 await r.get('apply').onclick();await r.switch('empty');
 assert.equal(r.requests.filter(x=>x.url.endsWith('/revisions')).length,0);assert.equal(r.app.state().projectId,'full');assert.equal(r.get('projects').value,'full');
 await r.get('retry-save').onclick();
 assert.equal(r.feedback().notes,'Keep my notes');assert.equal(r.app.state().dirty,0);assert.equal(r.get('retry-save').hidden,true);
 await r.get('apply').onclick();assert.equal(r.requests.filter(x=>x.url.endsWith('/revisions')).length,1);
});

test('edits queued during a failed request continue and save the latest complete draft',async()=>{
 const r=await room();let release;const blocked=new Promise(resolve=>{release=resolve});
 r.fail(async phase=>{if(phase==='before'){await blocked;throw Error('temporary failure')}});
 r.type('First');await Promise.resolve();r.type('Second');r.type('Final');release();await r.app.settled();
 assert.equal(r.feedback().notes,'Final');assert.equal(r.app.state().dirty,0);assert.equal(r.get('save-state').textContent,'All changes saved');
 assert.equal(r.requests.filter(x=>x.url==='/api/feedback/v').length,3);
});

test('retry reconciles a committed write whose response was lost',async()=>{
 const r=await room();r.fail(phase=>{if(phase==='after')throw Error('response lost')});r.type('Committed but unacknowledged');await r.app.settled();
 assert.equal(r.feedback().revision,1);assert.equal(r.app.state().dirty,1);
 r.type('Latest note after reconnect');await r.app.settled();
 assert.equal(r.feedback().notes,'Latest note after reconnect');assert.equal(r.feedback().revision,2);assert.equal(r.app.state().dirty,0);
});

test('retry preserves both the local draft and a conflicting edit from another window',async()=>{
 const r=await room();r.fail(()=>{throw Error('offline')});r.type('My local note');await r.app.settled();
 Object.assign(r.feedback(),{revision:1,notes:'Another reviewer note'});await r.get('retry-save').onclick();
 assert.equal(r.feedback().notes,'Another reviewer note');assert.equal(r.get('notes').value,'My local note');assert(r.app.state().dirty>0);
 assert.equal(r.requests.filter(x=>x.url==='/api/feedback/v').length,1);assert.match(r.get('error').textContent,/another window/);
});

for(const target of ['empty','waiting'])test(`switching to ${target} clears media, feedback, and controls; switching back restores them`,async()=>{
 const r=await room();r.get('player').paused=false;r.get('comparison').src='/media/old';r.get('comparison').paused=false;r.get('comment').value='unfinished';
 await r.switch(target);
 assert.equal(r.app.state().draft,undefined);assert.equal(r.get('player').src,undefined);assert.equal(r.get('comparison').src,undefined);assert.equal(r.get('player').paused,true);assert.equal(r.get('comparison').paused,true);
 assert.equal(r.get('player').hidden,true);assert.equal(r.get('empty').hidden,false);assert.equal(r.get('notes').value,'');assert.equal(r.get('comment').value,'');assert.equal(r.get('download').href,undefined);assert.equal(r.reference(),undefined);
 for(const id of ['notes','apply','apply-selected','compare','versions','add-comment','timestamp'])assert.equal(r.get(id).disabled,true,id);
 assert(r.decisions.every(d=>d.disabled));r.type('Cannot save on empty project');await r.app.settled();assert.equal(r.requests.filter(x=>x.url.startsWith('/api/feedback')).length,0);
 await r.switch('full');assert.equal(r.get('player').src,'/media/v');assert.equal(r.get('notes').disabled,false);assert.equal(r.get('apply').disabled,false);assert(r.decisions.every(d=>!d.disabled));
});

test('review-only room labels the mode, saves feedback and disables revision actions',async()=>{
 const r=await room(false);assert.match(r.get('room-mode').textContent,/Review only/);assert.equal(r.get('room-mode').hidden,false);
 assert.equal(r.get('apply').disabled,true);assert.equal(r.get('apply-selected').disabled,true);assert.equal(r.get('notes').disabled,false);
 r.type('Keep this for later');await r.app.settled();assert.equal(r.feedback().notes,'Keep this for later');
 await r.get('apply').onclick();assert.equal(r.requests.filter(x=>x.url.endsWith('/revisions')).length,0);
});

test('current-chat room shows a usable revision handoff even when clipboard access fails',async()=>{
 const r=await room('session');assert.match(r.get('room-mode').textContent,/Edit in your chat/);assert.equal(r.get('apply').disabled,false);
 r.type('Please restyle these captions');await r.app.settled();await r.get('apply').onclick();
 const row=r.get('jobs').children[0],text=row.children[1],copy=text.children.find(n=>n.textContent==='Copy request for your chat');assert(copy);
 await copy.onclick();const details=text.children.find(n=>n.open===true);assert(details);assert.match(details.children[1].value,/session-start job/);assert.equal(details.children[1].selected,true);
});
