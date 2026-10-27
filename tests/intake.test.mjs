import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,readFile,copyFile,stat,rm,readdir,symlink} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import os from 'node:os';
import path from 'node:path';
import {Store} from '../dist/store.js';
import {importLocal,importUrl,recoverIntake,abandonIntake} from '../dist/intake.js';
import {sha256} from '../dist/files.js';
const md5=b=>createHash('md5').update(b).digest('hex');
async function fixture(t){
 const root=await mkdtemp(path.join(os.tmpdir(),'acq-intake-'));for(const dir of ['00_SOURCE','10_WORK','20_DELIVER'])await mkdir(path.join(root,dir));
 const file=path.join(root,'camera.MP4');await writeFile(file,Buffer.from('synthetic media bytes'));const db=path.join(root,'state.sqlite');let store=new Store(db);
 const p={id:'p',title:'Intake fixture',root,backend:'resolve',agent:'codex',createdAt:''};store.addProject(p);
 t.after(async()=>{store.close();await rm(root,{recursive:true,force:true})});
 const calls=[];const tools={freeBytes:async()=>10*1024**3,execute:async(command,args)=>{calls.push({command,args});assert.equal(command,'ffprobe');return JSON.stringify({streams:[{codec_type:'video'}]})}};
 return {root,file,store,tools,calls,reopen(){store.close();store=new Store(db);return store}};
}
test('local intake preserves originals, registers once atomically and reopens with pinned receipt',async t=>{
 const f=await fixture(t),original=await sha256(f.file);const source=await importLocal(f.store,'p',f.file,'local',f.tools);
 assert.equal(source.sha256,original);assert.equal(await sha256(f.file),original);assert.equal((await stat(source.path)).mode&0o222,0);assert.equal(path.extname(source.path),'.mp4');
 assert.equal(f.store.intakes('p')[0].state,'ready');assert.equal((await recoverIntake(f.reopen(),source.id,f.tools)).id,source.id);assert.equal(f.calls.length,1);
 const receipt=JSON.parse(await readFile(source.verificationPath,'utf8'));assert.equal(receipt.verification,'local-copy-sha256');assert.equal(receipt.remote,null);
 await writeFile(source.verificationPath,'{}');await assert.rejects(recoverIntake(f.reopen(),source.id,f.tools),/receipt changed/);
});
test('recovery handles a complete copied file after interrupted registration without another copy or download',async t=>{
 const f=await fixture(t);const finish=f.store.finishIntake.bind(f.store);f.store.finishIntake=()=>{throw Error('simulated stop before registration')};
 await assert.rejects(importLocal(f.store,'p',f.file,'local',f.tools),/before registration/);const i=f.store.intakes('p')[0];assert.equal(i.state,'failed');assert.equal(f.store.sources('p').length,0);assert.equal(await sha256(i.target),i.expectedSha256);
 f.store.finishIntake=finish;const source=await recoverIntake(f.store,i.id,f.tools);assert.equal(source.path,i.target);assert.equal(f.store.sources('p').length,1);assert.equal((await recoverIntake(f.store,i.id,f.tools)).id,source.id);
});
test('recovery repairs the journal after SQLite committed without duplicating the source',async t=>{
 const f=await fixture(t),finish=f.store.finishIntake.bind(f.store);f.store.finishIntake=(...args)=>{finish(...args);throw Error('simulated stop after SQLite commit')};
 await assert.rejects(importLocal(f.store,'p',f.file,'local',f.tools),/after SQLite commit/);const i=f.store.intakes('p')[0];assert.equal(i.state,'ready');assert.equal(f.store.sources('p').length,1);
 await recoverIntake(f.store,i.id,f.tools);assert.equal(f.store.sources('p').length,1);assert.equal(JSON.parse(await readFile(path.join(i.directory,'intake.json'),'utf8')).state,'ready');
});
test('live ownership blocks recovery and pending intake blocks unrelated editing jobs',async t=>{
 const f=await fixture(t);let release;const gate=new Promise(resolve=>release=resolve);const slow={...f.tools,execute:async()=>{await gate;return JSON.stringify({streams:[{codec_type:'video'}]})}};
 const pending=importLocal(f.store,'p',f.file,'local',slow);
 for(let n=0;n<100&&!f.store.intakes('p').length;n++)await new Promise(r=>setTimeout(r,5));
 const id=f.store.intakes('p')[0].id;await assert.rejects(recoverIntake(f.store,id,f.tools),/still live/);
 await assert.rejects(importLocal(f.store,'p',f.file,'local',f.tools),/Another intake/);f.store.enqueueBuild('p','make clips');assert.equal(f.store.claim(),undefined);
 release();await pending;assert.equal(f.store.claim().state,'editing');
 await assert.rejects(importLocal(f.store,'p',f.file,'local',f.tools),/editing job owns/);
});
test('recovery refuses a surviving downloader even if its owner is gone',async t=>{
 const f=await fixture(t);f.tools.execute=async()=>{throw Error('probe failed')};await assert.rejects(importLocal(f.store,'p',f.file,'local',f.tools));const i=f.store.intakes('p')[0];
 f.store.updateIntake(i.id,{ownerPid:null,childPid:process.pid,state:'verifying'});await assert.rejects(recoverIntake(f.store,i.id,f.tools),/still live/);assert.equal(f.store.sources('p').length,0);
});
test('changed candidates and incomplete copies remain failed with evidence intact',async t=>{
 const f=await fixture(t);f.tools.execute=async()=>{throw Error('probe failed')};await assert.rejects(importLocal(f.store,'p',f.file,'local',f.tools));const i=f.store.intakes('p')[0];const partial=i.target+'.partial';assert.equal(await sha256(partial),i.expectedSha256);
 await writeFile(partial,'truncated');await assert.rejects(recoverIntake(f.store,i.id,f.tools),/Incomplete or changed/);assert.equal(await readFile(partial,'utf8'),'truncated');assert.equal(f.store.sources('p').length,0);
 await writeFile(f.file,'new source');await assert.rejects(recoverIntake(f.store,i.id,f.tools),/candidate changed/);
});
test('a copy changed during probing is never registered',async t=>{
 const f=await fixture(t);const tools={...f.tools,execute:async(command,args)=>{await writeFile(args.at(-1),'changed during probe');return JSON.stringify({streams:[{codec_type:'video'}]})}};
 await assert.rejects(importLocal(f.store,'p',f.file,'local',tools),/changed during media verification/);assert.equal(f.store.sources('p').length,0);
});
test('Drive keeps original extension and binds remote MD5 to exact ID among duplicate names',async t=>{
 const f=await fixture(t);const bytes=await readFile(f.file),name="camera's.mp4";let queries=0;
 const tools={...f.tools,execute:async(command,args,opts)=>{
  if(command==='ffprobe')return f.tools.execute(command,args);
  assert.equal(command,'rclone');opts.onSpawn?.(process.pid);
  if(args[1]==='copyid'){assert.equal(args[3],'exact-id');assert(args[4].endsWith(path.sep));assert(args.includes('--checksum'));await writeFile(path.join(args[4],name),bytes);return ''}
  assert.equal(args[1],'query');assert.equal(args[3],"name = 'camera\\'s.mp4' and trashed = false");queries++;return JSON.stringify([{id:'other-id',name,size:String(bytes.length),md5Checksum:'0'.repeat(32)},{id:'exact-id',name,size:String(bytes.length),md5Checksum:md5(bytes)}]);
 }};
 const source=await importUrl(f.store,'p','https://drive.google.com/file/d/exact-id/view','drive','testremote',tools);assert.equal(queries,2);assert.equal(path.extname(source.path),'.mp4');assert.equal(f.store.intake(source.id).childPid,null);
 const proof=JSON.parse(await readFile(source.verificationPath,'utf8'));assert.equal(proof.remote.fileId,'exact-id');assert.equal(proof.remote.md5,md5(bytes));assert.equal(proof.verification,'remote-md5-and-local-sha256');
});
test('Drive checksum failures never register sources; existing download can be reverified without replay',async t=>{
 const f=await fixture(t);const bytes=await readFile(f.file);let copies=0,correct=false;
 const tools={...f.tools,execute:async(command,args)=>{
  if(command==='ffprobe')return f.tools.execute(command,args);
  if(args[1]==='copyid'){copies++;await writeFile(path.join(args[4],'camera.mp4'),bytes);return ''}
  return JSON.stringify([{id:'exact-id',name:'camera.mp4',size:String(bytes.length),md5Checksum:correct?md5(bytes):'0'.repeat(32)}]);
 }};
 await assert.rejects(importUrl(f.store,'p','https://drive.google.com/file/d/exact-id/view','drive','testremote',tools),/Drive MD5 differs/);assert.equal(f.store.sources('p').length,0);correct=true;
 await recoverIntake(f.store,f.store.intakes('p')[0].id,tools);assert.equal(copies,1);assert.equal(f.store.sources('p').length,1);
});
test('YouTube ignores user config and refuses a downloader path outside its staging folder',async t=>{
 const f=await fixture(t);const tools={...f.tools,execute:async(command,args)=>{
  assert.equal(command,path.resolve('.local/venv/bin/yt-dlp'));assert(args.includes('--ignore-config'));const manifest=args[args.indexOf('--print-to-file')+2];await writeFile(manifest,f.file+'\n');return '';
 }};
 await assert.rejects(importUrl(f.store,'p','https://youtu.be/HOfdboHvshg','youtube','drive',tools),/outside project/);assert.equal(f.store.sources('p').length,0);
});
async function youtubeFixture(f,{metadata={},probe}={}){
 const info={id:'HOfdboHvshg',extractor_key:'Youtube',webpage_url:'https://www.youtube.com/watch?v=HOfdboHvshg',is_live:false,live_status:'not_live',duration:52,title:'Sample',channel:'Fixture',channel_id:'channel-id',formats:[{url:'private extractor URL'}],http_headers:{authorization:'not-for-receipt'},...metadata};
 const calls=[];let infoPath;
 const tools={...f.tools,execute:async(command,args)=>{
  calls.push({command,args});
  if(command==='ffprobe'){if(probe)await probe(infoPath);return JSON.stringify({streams:[{codec_type:'video'}]})}
  assert.equal(command,path.resolve('.local/venv/bin/yt-dlp'));assert.equal(args[args.indexOf('--js-runtimes')+1],'node:'+process.execPath);assert(args.includes('--write-info-json'));assert(args.includes('--no-write-playlist-metafiles'));
  const template=args[args.indexOf('-o')+1],candidate=template.replace('%(ext)s','mkv');infoPath=path.join(path.dirname(candidate),'source.info.json');
  await copyFile(f.file,candidate);await writeFile(infoPath,JSON.stringify(info));await writeFile(args[args.indexOf('--print-to-file')+2],candidate+'\n');return '';
 }};
 return {tools,calls,info,get infoPath(){return infoPath}};
}
test('YouTube binds exact video metadata to the verified copy and reopens without downloading again',async t=>{
 const f=await fixture(t),y=await youtubeFixture(f);
 const source=await importUrl(f.store,'p','https://youtu.be/HOfdboHvshg?si=share&t=20&list=ignored','youtube','drive',y.tools);
 const receipt=JSON.parse(await readFile(source.verificationPath,'utf8'));
 assert.equal(receipt.verification,'youtube-extractor-identity-and-local-sha256');assert.equal(receipt.remote.videoId,'HOfdboHvshg');
 assert.equal(receipt.remote.metadataSha256,await sha256(y.infoPath));assert.equal(receipt.remote.metadataSha256,f.store.intake(source.id).youtubeInfoSha256);
 assert.equal(receipt.remote.webpageUrl,'https://www.youtube.com/watch?v=HOfdboHvshg');assert.equal(receipt.remote.duration,52);
 assert(!JSON.stringify(receipt).includes('private extractor URL'));assert(!JSON.stringify(receipt).includes('not-for-receipt'));
 assert.equal(y.calls[0].args.at(-1),'https://www.youtube.com/watch?v=HOfdboHvshg');
 const bytes=await readFile(source.path),receiptBytes=await readFile(source.verificationPath);
 const reopened=f.reopen();await recoverIntake(reopened,source.id,y.tools);assert.equal(y.calls.length,2);assert.equal(reopened.sources('p').length,1);
 assert.deepEqual(await readFile(source.path),bytes);assert.deepEqual(await readFile(source.verificationPath),receiptBytes);
});
test('YouTube accepts explicit short/embed/archive video URLs but refuses channel or ambiguous links before transfer',async t=>{
 const f=await fixture(t);let calls=0;const tools={execute:async()=>{calls++;throw Error('unexpected download')},freeBytes:async()=>100};
 for(const url of ['https://www.youtube.com/@channel','https://youtube.com/playlist?list=one','https://youtube.com/watch?v=HOfdboHvshg&v=anotherid00','https://youtu.be/short','https://youtube.com/redirect?q=https://youtu.be/HOfdboHvshg','https://user:pass@youtu.be/HOfdboHvshg']){
  await assert.rejects(importUrl(f.store,'p',url,'youtube','drive',tools));
 }
 assert.equal(calls,0);assert.equal(f.store.intakes('p').length,0);
 for(const prefix of ['https://www.youtube.com/shorts/','https://m.youtube.com/embed/','https://youtube.com/live/']){
  await assert.rejects(importUrl(f.store,'p',prefix+'HOfdboHvshg','youtube','drive',tools),/free space/);
  assert.equal(f.store.intakes('p').at(-1).youtubeVideoId,'HOfdboHvshg');
 }
 assert.equal(calls,0);
});
test('YouTube rejects another video, playlist, live source or invalid metadata before copying',async t=>{
 const f=await fixture(t);
 for(const metadata of [{id:'otherid0000'},{extractor_key:'Generic'},{_type:'playlist'},{webpage_url:'https://youtu.be/otherid0000'},{is_live:true,live_status:'is_live'},{live_status:'post_live'},{duration:0}]){
  const y=await youtubeFixture(f,{metadata});await assert.rejects(importUrl(f.store,'p','https://youtu.be/HOfdboHvshg','youtube','drive',y.tools),/YouTube/);
  assert.equal(y.calls.length,1);assert.equal(f.store.sources('p').length,0);
 }
 assert.deepEqual(await readdir(path.join(f.root,'00_SOURCE')),[]);
});
test('YouTube metadata changed during probing cannot register the source',async t=>{
 const f=await fixture(t),y=await youtubeFixture(f,{probe:async file=>{const info=JSON.parse(await readFile(file,'utf8'));info.title='changed after pin';await writeFile(file,JSON.stringify(info))}});
 await assert.rejects(importUrl(f.store,'p','https://youtu.be/HOfdboHvshg','youtube','drive',y.tools),/metadata changed/);
 const i=f.store.intakes('p').at(-1);assert.equal(i.state,'failed');assert.equal(f.store.sources('p').length,0);
 assert.equal(await sha256(i.target+'.partial'),i.expectedSha256);
});
test('YouTube interrupted verification recovers pinned bytes and metadata without replay',async t=>{
 const f=await fixture(t);let fail=true;const y=await youtubeFixture(f,{probe:async()=>{if(fail)throw Error('interrupted verification')}});
 await assert.rejects(importUrl(f.store,'p','https://youtu.be/HOfdboHvshg','youtube','drive',y.tools),/interrupted verification/);
 const i=f.store.intakes('p').at(-1),original=await readFile(y.infoPath);fail=false;
 await writeFile(y.infoPath,JSON.stringify({...y.info,title:'mutated'}));await assert.rejects(recoverIntake(f.store,i.id,y.tools),/metadata changed/);
 await writeFile(y.infoPath,original);const source=await recoverIntake(f.store,i.id,y.tools);
 assert.equal(y.calls.filter(c=>c.command===path.resolve('.local/venv/bin/yt-dlp')).length,1);assert.equal(f.store.sources('p').length,1);assert.equal(source.sha256,i.expectedSha256);
});
test('YouTube missing or symlinked metadata fails without registering a source',async t=>{
 const f=await fixture(t);
 for(const link of [false,true]){
  const tools={...f.tools,execute:async(command,args)=>{
   assert.equal(command,path.resolve('.local/venv/bin/yt-dlp'));const candidate=args[args.indexOf('-o')+1].replace('%(ext)s','mkv');await copyFile(f.file,candidate);
   if(link)await symlink(f.file,path.join(path.dirname(candidate),'source.info.json'));
   await writeFile(args[args.indexOf('--print-to-file')+2],candidate+'\n');return '';
  }};
  await assert.rejects(importUrl(f.store,'p','https://youtu.be/HOfdboHvshg','youtube','drive',tools),/metadata/);assert.equal(f.store.sources('p').length,0);
 }
});
test('insufficient disk and invalid remote URLs fail without a transfer',async t=>{
 const f=await fixture(t);let calls=0;const tools={execute:async()=>{calls++;throw Error('unexpected execution')},freeBytes:async()=>100};
 await assert.rejects(importUrl(f.store,'p','https://youtu.be/HOfdboHvshg','youtube','drive',tools),/free space/);assert.equal(calls,0);
 const count=f.store.intakes('p').length;
 for(const url of ['https://drive.google.com/drive/folders/folder','https://user:pass@drive.google.com/file/d/id/view','https://evil.test/file/d/id/view'])await assert.rejects(importUrl(f.store,'p',url,'drive','drive',tools));
 assert.equal(f.store.intakes('p').length,count);
});

test('unrecorded child launch requires explicit process reconciliation, retaining all bytes',async t=>{
 const f=await fixture(t);f.tools.execute=async()=>{throw Error('probe failed')};await assert.rejects(importLocal(f.store,'p',f.file,'local',f.tools));const i=f.store.intakes('p')[0];f.store.updateIntake(i.id,{childPending:true,state:'verifying'});
 await assert.rejects(recoverIntake(f.store,i.id,f.tools),/launch outcome/);const evidence=path.join(f.root,'10_WORK','process-observation.json');await writeFile(evidence,JSON.stringify({intakeId:i.id,processInspection:'Fixture has no active writer; known process fields are null',noActiveWriter:true}));
 f.store.updateIntake(i.id,{childPid:process.pid});await assert.rejects(abandonIntake(f.store,i.id,evidence),/still live/);f.store.updateIntake(i.id,{childPid:null});await abandonIntake(f.store,i.id,evidence);assert.equal(f.store.intake(i.id).state,'failed');assert.equal(f.store.intake(i.id).childPending,false);assert.equal(await sha256(i.target+'.partial'),i.expectedSha256);
});
