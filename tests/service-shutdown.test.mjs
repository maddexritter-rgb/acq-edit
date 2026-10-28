import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm,mkdir} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {Store} from '../dist/store.js';
import {serve} from '../dist/server.js';
import {startSession} from '../dist/session.js';

test('room shutdown preserves active chat reservations and historical jobs',async t=>{
 const root=await mkdtemp(path.join(os.tmpdir(),'acq-shutdown-'));
 const s=new Store(path.join(root,'state.sqlite'));
 t.after(async()=>{s.close();await rm(root,{recursive:true,force:true})});
 await mkdir(path.join(root,'10_WORK'));
 s.addProject({id:'p',title:'Shutdown fixture',root,backend:'filmcraft',agent:'claude',createdAt:''});
 const active=s.enqueueBuild('p','Current chat',undefined,'session');
 await startSession(s,active.id);
 const legacy=s.enqueueBuild('p','Historical background job');
 const before=s.jobs('p');
 const room=serve(s,{});
 await new Promise(r=>room.server.listen(0,'127.0.0.1',r));
 await room.stop();
 assert.equal(room.server.listening,false);
 assert.deepEqual(s.jobs('p'),before);
 assert.equal(s.job(active.id).state,'editing');
 assert.equal(s.job(legacy.id).state,'queued');
 const reopened=serve(s,{});await new Promise(r=>reopened.server.listen(0,'127.0.0.1',r));await reopened.stop();
 assert.deepEqual(s.jobs('p'),before);
});
