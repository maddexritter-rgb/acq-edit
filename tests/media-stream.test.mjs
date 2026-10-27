import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {mkdtemp,mkdir,writeFile,rm,realpath} from 'node:fs/promises';
import {Readable} from 'node:stream';
import {syncBuiltinESMExports} from 'node:module';
import os from 'node:os';
import path from 'node:path';
import {Store} from '../dist/store.js';
import {serve} from '../dist/server.js';

async function fixture(t){
 const root=await mkdtemp(path.join(os.tmpdir(),'acq-stream-'));await mkdir(path.join(root,'10_WORK'));const store=new Store(path.join(root,'db'));
 store.addProject({id:'p',title:'Fixture',root,backend:'filmcraft',agent:'codex',createdAt:''});store.addClip({id:'c',projectId:'p',number:1,title:'Clip',currentVersionId:null});
 const media=path.join(root,'clip.mp4');await writeFile(media,'0123456789');store.publish({id:'v',clipId:'c',number:1,parentId:null,media,createdAt:''});
 const room=serve(store,{},false);await new Promise(resolve=>room.server.listen(0,'127.0.0.1',resolve));
 t.after(async()=>{await room.stop();store.close();await rm(root,{recursive:true,force:true})});
 const base=`http://127.0.0.1:${room.server.address().port}`,login=await fetch(base+'/session?token='+room.token,{redirect:'manual'}),cookie=login.headers.get('set-cookie').split(';')[0];
 return {base,media:await realpath(media),cookie};
}
for(const range of [undefined,'bytes=1-5'])test(`media read failure closes only the request (${range||'full'})`,async t=>{
 const f=await fixture(t),original=fs.createReadStream;let failed;
 const mock=t.mock.method(fs,'createReadStream',(file,options)=>file===f.media?(failed=new Readable({read(){this.destroy(Object.assign(Error('disk disconnected'),{code:'EIO'}))}})):original(file,options));syncBuiltinESMExports();
 t.after(()=>{mock.mock.restore();syncBuiltinESMExports()});
 await assert.rejects(async()=>{const r=await fetch(f.base+'/media/v',{headers:{cookie:f.cookie,...(range?{Range:range}:{})}});await r.arrayBuffer()});
 assert.equal(failed.destroyed,true);
 const projects=await fetch(f.base+'/api/projects',{headers:{cookie:f.cookie}});assert.equal(projects.status,200);
 const saved=await fetch(f.base+'/api/feedback/v',{method:'PUT',headers:{cookie:f.cookie,Origin:f.base,'Content-Type':'application/json'},body:JSON.stringify({expectedRevision:0,feedback:{decision:null,notes:'Still saving after disk failure',comments:[]}})});assert.equal(saved.status,200);
 mock.mock.restore();syncBuiltinESMExports();const good=await fetch(f.base+'/media/v',{headers:{cookie:f.cookie}});assert.equal(await good.text(),'0123456789');
});

test('abandoning playback destroys its source stream without stopping the room',async t=>{
 const f=await fixture(t),original=fs.createReadStream;let stream,closed;const finished=new Promise(resolve=>{closed=resolve});
 const mock=t.mock.method(fs,'createReadStream',(file,options)=>{
  if(file!==f.media)return original(file,options);
  stream=new Readable({read(){if(!this.sent){this.sent=true;this.push('0')}},destroy(error,done){closed();done(error)}});return stream;
 });syncBuiltinESMExports();t.after(()=>{mock.mock.restore();syncBuiltinESMExports()});
 const controller=new AbortController(),response=await fetch(f.base+'/media/v',{headers:{cookie:f.cookie},signal:controller.signal});
 const reader=response.body.getReader();await reader.read();controller.abort();await finished;assert.equal(stream.destroyed,true);
 assert.equal((await fetch(f.base+'/api/projects',{headers:{cookie:f.cookie}})).status,200);
});
