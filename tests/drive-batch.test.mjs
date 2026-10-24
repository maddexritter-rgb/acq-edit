import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,readFile,rm} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import os from 'node:os';
import path from 'node:path';
import {Store} from '../dist/store.js';
import {importDriveFolder,resumeDriveBatch,abandonDriveBatch} from '../dist/drive-batch.js';
import {importLocal,recoverIntake} from '../dist/intake.js';
const md5=b=>createHash('md5').update(b).digest('hex');
async function fixture(t){
 const root=await mkdtemp(path.join(os.tmpdir(),'acq-drive-batch-'));for(const dir of ['00_SOURCE','10_WORK','20_DELIVER'])await mkdir(path.join(root,dir));
 const store=new Store(path.join(root,'state.sqlite'));store.addProject({id:'p',root,title:'Drive fixture',backend:'resolve',agent:'codex',createdAt:''});t.after(async()=>{store.close();await rm(root,{recursive:true,force:true})});
 const data={a:Buffer.from('camera A fixture'),b:Buffer.from('camera B fixture')};
 const rows=[{id:'sub',name:'Camera B',mimeType:'application/vnd.google-apps.folder',parents:['folder']},{id:'note',name:'notes.txt',mimeType:'text/plain',parents:['folder']},...['a','b'].map(id=>({id,name:'same.mp4',mimeType:'video/mp4',parents:[id==='a'?'folder':'sub'],size:String(data[id].length),md5Checksum:md5(data[id])}))];
 const calls=[],tools={freeBytes:async()=>10*1024**3,execute:async(command,args)=>{
  calls.push({command,args});if(command==='ffprobe')return JSON.stringify({streams:[{codec_type:'video'}]});assert.equal(command,'rclone');
  if(args[1]==='copyid'){const id=args[3];await writeFile(path.join(args[4],rows.find(r=>r.id===id).name),data[id]);return ''}
  const parent=args[3].match(/^'([^']+)' in parents/);return JSON.stringify(parent?rows.filter(r=>r.parents.includes(parent[1])):rows.filter(r=>r.name==='same.mp4'));
 }};
 return {root,store,rows,data,calls,tools,url:'https://drive.google.com/drive/folders/folder',copies(){return calls.filter(c=>c.args[1]==='copyid')}};
}
test('nested Drive batch binds duplicate names to IDs and preserves exclusions and manifest hashes',async t=>{
 const f=await fixture(t),b=await importDriveFolder(f.store,'p',f.url,'remote',f.tools);assert.equal(b.state,'ready');assert.equal(f.store.sources('p').length,2);assert.equal(f.copies().length,2);
 const m=JSON.parse(await readFile(b.manifestPath,'utf8'));assert.deepEqual(m.files.map(x=>[x.id,x.parentId,x.folders]),[['a','folder',[]],['b','sub',['Camera B']]]);assert.equal(m.excluded[0].id,'note');
 for(const s of f.store.sources('p')){const receipt=JSON.parse(await readFile(s.verificationPath,'utf8'));assert.equal(receipt.batchId,b.id);assert.equal(receipt.remote.md5,receipt.folderManifestEntry.md5)}
 await resumeDriveBatch(f.store,b.id,f.tools);assert.equal(f.copies().length,2);assert.equal(f.store.sources('p').length,2);
});
test('changed frozen file fails and blocks editing until explicit failed-file retry',async t=>{
 const f=await fixture(t),execute=f.tools.execute;let fail=true;
 f.tools.execute=async(command,args,opts)=>{if(args[1]==='copyid'&&args[3]==='b'&&fail){await writeFile(path.join(args[4],'same.mp4'),'partial');throw Error('network interrupted')}return execute(command,args,opts)};
 await assert.rejects(importDriveFolder(f.store,'p',f.url,'remote',f.tools),/network interrupted/);const b=f.store.driveBatches('p')[0];assert.equal(b.state,'failed');assert.equal(f.store.sources('p').length,1);
 f.store.enqueueBuild('p','Wait for all cameras');assert.equal(f.store.claim(),undefined);await assert.rejects(importLocal(f.store,'p','/missing.mp4','local',f.tools),/batch owns/);
 await assert.rejects(resumeDriveBatch(f.store,b.id,f.tools),/size differs/);assert.equal(f.copies().length,1);fail=false;
 await resumeDriveBatch(f.store,b.id,f.tools,true);assert.equal(f.store.sources('p').length,2);assert.equal(f.copies().length,2);assert.equal(f.store.intakes('p').length,3);assert.equal(f.store.claim().state,'editing');
});
test('metadata changed after enumeration cannot replace the frozen file',async t=>{
 const f=await fixture(t),execute=f.tools.execute;
 f.tools.execute=async(command,args,opts)=>{if(args[1]==='copyid'){const id=args[3];f.data[id]=Buffer.from('changed remote file');const row=f.rows.find(r=>r.id===id);row.size=String(f.data[id].length);row.md5Checksum=md5(f.data[id])}return execute(command,args,opts)};
 await assert.rejects(importDriveFolder(f.store,'p',f.url,'remote',f.tools),/frozen folder manifest/);assert.equal(f.store.sources('p').length,0);
});
test('recovery after source commit reuses registered bytes and never duplicates a source',async t=>{
 const f=await fixture(t),finish=f.store.finishIntake.bind(f.store);let stop=true;
 f.store.finishIntake=(...args)=>{const result=finish(...args);if(stop){stop=false;throw Error('stopped after commit')}return result};
 await assert.rejects(importDriveFolder(f.store,'p',f.url,'remote',f.tools),/stopped after commit/);const b=f.store.driveBatches('p')[0];assert.equal(f.store.sources('p').length,1);
 await resumeDriveBatch(f.store,b.id,f.tools);assert.equal(f.store.sources('p').length,2);assert.equal(f.copies().length,2);assert.equal(f.store.driveBatch(b.id).state,'ready');
});
test('unknown or live process outcomes block resume and require inspected abandonment',async t=>{
 const f=await fixture(t);f.tools.execute=async()=>{throw Error('query unavailable')};await assert.rejects(importDriveFolder(f.store,'p',f.url,'remote',f.tools));const b=f.store.driveBatches('p')[0];
 f.store.updateDriveBatch(b.id,{ownerPid:process.pid});await assert.rejects(resumeDriveBatch(f.store,b.id,f.tools),/still live/);
 f.store.updateDriveBatch(b.id,{ownerPid:null,childPending:true});await assert.rejects(resumeDriveBatch(f.store,b.id,f.tools),/outcome is unknown/);
 const evidence=path.join(f.root,'10_WORK/evidence.json');await writeFile(evidence,JSON.stringify({batchId:b.id,noActiveWriter:true,processInspection:'Controlled fixture has no live downloader or query'}));
 f.store.updateDriveBatch(b.id,{childPid:process.pid});await assert.rejects(abandonDriveBatch(f.store,b.id,evidence),/still live/);f.store.updateDriveBatch(b.id,{childPid:null});assert.equal((await abandonDriveBatch(f.store,b.id,evidence)).state,'abandoned');
});
test('manifest changes and folder shortcuts cannot silently change scope',async t=>{
 const f=await fixture(t);const b=await importDriveFolder(f.store,'p',f.url,'remote',f.tools);await writeFile(b.manifestPath,'{}');await assert.rejects(resumeDriveBatch(f.store,b.id,f.tools),/manifest changed/);
 f.rows.push({id:'shortcut',name:'Other footage',mimeType:'application/vnd.google-apps.shortcut',parents:['folder']});const copies=f.copies().length;await assert.rejects(importDriveFolder(f.store,'p',f.url,'remote',f.tools),/shortcuts/);assert.equal(f.copies().length,copies);
});
test('batch ownership prevents file recovery and worker dispatch during enumeration',async t=>{
 const f=await fixture(t),execute=f.tools.execute;let release;const gate=new Promise(r=>release=r);let once=true;
 f.tools.execute=async(...args)=>{if(once){once=false;await gate}return execute(...args)};const pending=importDriveFolder(f.store,'p',f.url,'remote',f.tools);
 for(let n=0;n<100&&!f.store.driveBatches('p').length;n++)await new Promise(r=>setTimeout(r,5));
 const b=f.store.driveBatches('p')[0];await assert.rejects(resumeDriveBatch(f.store,b.id,f.tools),/still live/);f.store.enqueueBuild('p','queued');assert.equal(f.store.claim(),undefined);release();await pending;assert.equal(f.store.claim().state,'editing');
});
