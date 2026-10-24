import test from 'node:test';import assert from 'node:assert/strict';import {mkdtempSync,rmSync,writeFileSync} from 'node:fs';import os from 'node:os';import path from 'node:path';import {Store} from '../dist/store.js';import {serve} from '../dist/server.js';
test('loopback session, CSRF protection and media ranges',async t=>{const root=mkdtempSync(path.join(os.tmpdir(),'acq-http-'));const s=new Store(path.join(root,'db'));const room=serve(s,{},false);await new Promise(r=>room.server.listen(0,'127.0.0.1',r));t.after(async()=>{await new Promise(r=>room.server.close(r));s.close();rmSync(root,{recursive:true,force:true})});const base=`http://127.0.0.1:${room.server.address().port}`;assert.equal((await fetch(base+'/api/projects')).status,400);const login=await fetch(base+'/session?token='+room.token,{redirect:'manual'});assert.equal(login.status,303);const cookie=login.headers.get('set-cookie').split(';')[0];assert.equal((await fetch(base+'/api/projects',{headers:{cookie}})).status,200);
 const activity=await fetch(base+'/activity.js',{headers:{cookie}});assert.equal(activity.status,200);assert.match(activity.headers.get('content-type'),/javascript/);assert.match(await activity.text(),/export function projectActivity/);
 s.addProject({id:'p',title:'Fixture',root,backend:'resolve',agent:'codex',createdAt:''});s.addClip({id:'c',projectId:'p',number:1,title:'Clip',currentVersionId:null});writeFileSync(path.join(root,'media.mp4'),'0123456789');s.publish({id:'v',clipId:'c',number:1,parentId:null,media:path.join(root,'media.mp4'),createdAt:''});
 const range=await fetch(base+'/media/v',{headers:{cookie,Range:'bytes=2-4'}});assert.equal(range.status,206);assert.equal(await range.text(),'234');const suffix=await fetch(base+'/media/v',{headers:{cookie,Range:'bytes=-3'}});assert.equal(await suffix.text(),'789');
 assert.equal((await fetch(base+'/api/feedback/v',{method:'PUT',headers:{cookie,'Content-Type':'application/json',Origin:'https://evil.invalid'},body:'{}'})).status,400);
 const saved=await fetch(base+'/api/feedback/v',{method:'PUT',headers:{cookie,'Content-Type':'application/json',Origin:base},body:JSON.stringify({expectedRevision:0,feedback:{decision:'revise',notes:'Caption only',comments:[]}})});assert.equal(saved.status,200);
 const submitted=await fetch(base+'/api/projects/p/revisions',{method:'POST',headers:{cookie,'Content-Type':'application/json',Origin:base},body:JSON.stringify({versionIds:['v']})});assert.equal(submitted.status,202);assert.equal(s.jobs('p')[0].state,'queued');
});

test('HTTP duplicate submissions survive routing upgrades and a full room/database restart',async t=>{
 const {hash}=await import('../dist/contracts.js');
 const root=mkdtempSync(path.join(os.tmpdir(),'acq-routing-restart-')),database=path.join(root,'state.sqlite');let s=new Store(database),room,base,cookie;
 t.after(async()=>{if(room)await room.stop();if(s)s.close();rmSync(root,{recursive:true,force:true})});
 const start=async()=>{room=serve(s,{},false);await new Promise(r=>room.server.listen(0,'127.0.0.1',r));base=`http://127.0.0.1:${room.server.address().port}`;const login=await fetch(base+'/session?token='+room.token,{redirect:'manual'});cookie=login.headers.get('set-cookie').split(';')[0]};
 const request=async(url,method,body)=>{const response=await fetch(base+url,{method,headers:{cookie,Origin:base,'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await response.json();assert(response.ok,JSON.stringify(data));return data};
 s.addProject({id:'p',title:'Synthetic routing restart',root,backend:'resolve',agent:'codex',createdAt:''});s.addClip({id:'c',projectId:'p',number:1,title:'Fixture',currentVersionId:null});s.publish({id:'v1',clipId:'c',number:1,parentId:null,media:path.join(root,'synthetic.mp4'),createdAt:''});await start();
 const feedback={decision:'revise',notes:'Remove the captions and match this reference',comments:[{id:'a',seconds:1.25,text:'Match the animation here'}]};
 await request('/api/feedback/v1','PUT',{expectedRevision:0,feedback});
 const [first,duplicate]=await Promise.all([request('/api/projects/p/revisions','POST',{versionIds:['v1']}),request('/api/projects/p/revisions','POST',{versionIds:['v1']})]);
 assert.equal(first.id,duplicate.id);assert(first.snapshot[0].owners.includes('watch'));assert(!first.snapshot[0].owners.includes('assembly-design'));
 // Seed the prior release's hash format, preserving the exact submitted input.
 const legacy={...first,snapshot:first.snapshot.map(item=>({...item,owners:['edit','caption-clips']}))};legacy.dedupe=hash({projectId:'p',snapshot:legacy.snapshot});
 s.db.prepare('UPDATE jobs SET dedupe=?,data=? WHERE id=?').run(legacy.dedupe,JSON.stringify(legacy),first.id);
 await room.stop();room=null;s.close();s=null;s=new Store(database);await start();
 const resumed=await request('/api/projects/p/revisions','POST',{versionIds:['v1']});assert.deepEqual(resumed,legacy);assert.equal(s.jobs('p').length,1);
 await request('/api/feedback/v1','PUT',{expectedRevision:1,feedback:{...feedback,notes:feedback.notes+'; remove the first sentence'}});
 const next=await request('/api/projects/p/revisions','POST',{versionIds:['v1']});assert.notEqual(next.id,first.id);assert(next.snapshot[0].owners.includes('watch'));assert(next.snapshot[0].owners.includes('assembly-design'));
 assert.deepEqual(s.job(first.id),legacy);assert.equal(next.snapshot[0].feedback.comments[0].seconds,1.25);assert.equal(next.snapshot[0].version.id,'v1');assert.equal(s.jobs('p').length,2);
});
