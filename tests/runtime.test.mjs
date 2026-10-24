import test from 'node:test';
import assert from 'node:assert/strict';
import {verifyRuntime} from '../dist/runtime.js';
test('runtime preflight requires explicit installed file and route verification',async()=>{
 const result=await verifyRuntime({python:'configured-python'},async(command,args)=>{assert.equal(command,'configured-python');assert(args[0].endsWith('/scripts/materialize.py'));assert.equal(args[1],'--verify');return JSON.stringify({ready:true,verifiedFiles:683,routedEntrypoints:38})});assert.equal(result.ready,true);
 for(const output of ['{}','null','not-json','{"ready":true,"verifiedFiles":0,"routedEntrypoints":38}','{"ready":false,"verifiedFiles":683,"routedEntrypoints":38}'])await assert.rejects(verifyRuntime({python:'python'},async()=>output),/before agent\/editor launch/);
 await assert.rejects(verifyRuntime({python:'python'},async()=>{throw Error('changed runtime file')}),/fresh checkout.*changed runtime file/);
});
