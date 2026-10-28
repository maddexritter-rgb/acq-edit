import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,rm,stat} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {driveLinkKind,driveStatus,driveRemote,connectDrive,loginDrive} from '../dist/drive-access.js';
async function fixture(t,listing=''){
 const home=await mkdtemp(path.join(os.tmpdir(),'acq-drive-access-')),calls=[];t.after(()=>rm(home,{recursive:true,force:true}));
 const tools={home,execute:async(command,args)=>{assert.equal(command,'rclone');calls.push(args);
  if(args[0]==='version')return 'rclone v1.75.2\n';
  if(args[0]==='listremotes')return listing;
  if(args[0]==='about')return '{"used":123}';
  if(args[0]==='config'){listing+='acq-edit-drive: drive\n';return ''}
  throw Error('Unexpected command');
 }};return {tools,home,calls};
}
test('pasted file/folder URLs route correctly and ambiguous or hostile links fail',()=>{
 for(const link of ['https://drive.google.com/file/d/abc_123/view?usp=sharing','https://drive.google.com/open?id=abc','https://drive.google.com/uc?id=abc&export=download'])assert.equal(driveLinkKind(link),'file');
 for(const link of ['https://drive.google.com/drive/folders/abc?usp=drive_link','https://drive.google.com/drive/u/0/folders/abc'])assert.equal(driveLinkKind(link),'folder');
 for(const link of ['https://evil.invalid/drive/folders/abc','https://user:pass@drive.google.com/file/d/a/view','https://drive.google.com/drive/my-drive','https://drive.google.com/open?id=a&id=b'])assert.throws(()=>driveLinkKind(link));
});
test('single connection works without a remote argument; multiple accounts are never guessed',async t=>{
 const f=await fixture(t,'work: drive\nbackup: s3\n');assert.equal(await driveRemote(undefined,f.tools),'work');
 const multiple=await fixture(t,'personal: drive\nwork: drive\n');await assert.rejects(driveRemote(undefined,multiple.tools),/Choose\/connect/);
 await connectDrive('work',multiple.tools);assert.equal(await driveRemote(undefined,multiple.tools),'work');
 assert.equal((await stat(path.join(multiple.home,'drive.json'))).mode&0o777,0o600);
 const saved=await readFile(path.join(multiple.home,'drive.json'),'utf8');assert.deepEqual(JSON.parse(saved),{schema:'acq-edit/drive-connection-v1',remote:'work'});assert(!/token|password/.test(saved));
 await assert.rejects(connectDrive('other',multiple.tools),/Choose\/connect/);
});
test('guided login opens a separate read-only remote and never emits or overwrites configuration',async t=>{
 const f=await fixture(t);assert.equal((await loginDrive(f.tools)).ready,true);
 const create=f.calls.find(x=>x[0]==='config');assert.deepEqual(create,['config','create','acq-edit-drive','drive','scope','drive.readonly','config_is_local','true','--no-output']);
 await assert.rejects(loginDrive(f.tools),/already exists/);assert.equal(f.calls.filter(x=>x[0]==='config').length,1);
 const occupied=await fixture(t,'acq-edit-drive: s3\n');await assert.rejects(loginDrive(occupied.tools),/already exists/);assert(!occupied.calls.some(x=>x[0]==='config'));
});
test('missing/old downloader and failed authentication stop before intake without leaking provider output',async t=>{
 const f=await fixture(t,'work: drive\n');const normal=f.tools.execute;
 f.tools.execute=async()=>{throw Error('secret-provider-output')};await assert.rejects(driveStatus(f.tools),/downloader is missing/);
 f.tools.execute=async(c,a)=>a[0]==='version'?'rclone v1.70.0':normal(c,a);await assert.rejects(driveStatus(f.tools),/1.74.3/);
 f.tools.execute=async(c,a)=>{if(a[0]==='about')throw Error('secret-provider-output');return normal(c,a)};
 await assert.rejects(connectDrive('work',f.tools),e=>/access could not be verified/.test(e.message)&&!e.message.includes('secret'));
 await assert.rejects(readFile(path.join(f.home,'drive.json')),{code:'ENOENT'});
});
