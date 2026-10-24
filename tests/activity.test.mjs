import test from 'node:test';
import assert from 'node:assert/strict';
import {projectActivity,jobPresentation} from '../web/activity.js';
const fixture=()=>({project:{id:'project-1',title:'Review fixture',root:'/isolated/project',backend:'resolve'},jobs:[],nativeOperations:[],intakes:[],driveBatches:[]});
test('standalone editor operation is visible without jobs and requests inspection rather than replay',()=>{
 const data=fixture();data.nativeOperations.push({id:'operation-1',state:'running',action:'render'});
 const result=projectActivity(data);assert.equal(result.reserved,true);assert.equal(result.attention,false);assert.match(result.heading,/Waiting/);assert.match(result.request,/operation-1/);assert.match(result.request,/backend: resolve/);assert.match(result.request,/reread current state/);assert.match(result.request,/do not restart/);
});
test('uncertain operations and failed folder batches retain a visible recovery reservation',()=>{
 const data=fixture();data.nativeOperations.push({id:'operation-1',state:'reconciliation_required',action:'render',error:'Disconnected'});data.driveBatches.push({id:'folder-1',state:'failed'});data.jobs.push({id:'queued-1',state:'queued'});
 const result=projectActivity(data);assert.equal(result.attention,true);assert.equal(result.reservations.length,2);assert.match(result.request,/folder-1: failed/);assert.match(result.description,/existing clips and feedback/);
});
test('terminal editor/intake outcomes do not falsely reserve the project while unresolved jobs do',()=>{
 const data=fixture();data.nativeOperations.push({id:'a',state:'reconciled'},{id:'b',state:'succeeded'});data.intakes.push({id:'c',state:'failed'},{id:'d',state:'ready'});data.driveBatches.push({id:'e',state:'abandoned'},{id:'f',state:'ready'});data.jobs.push({id:'g',state:'failed'},{id:'h',state:'ready'});
 assert.equal(projectActivity(data).reserved,false);assert.equal(projectActivity(data).request,'');data.jobs.push({id:'i',state:'reconciliation_required'});assert.equal(projectActivity(data).attention,true);
});
test('job labels distinguish rendered readiness from approval and uncertain outcomes from failure',()=>{
 assert.equal(jobPresentation({state:'ready'}).label,'Ready for review');assert.equal(jobPresentation({state:'reconciliation_required'}).label,'Needs recovery review');assert.match(jobPresentation({state:'queued'}).description,/submitted notes are saved/);assert.match(jobPresentation({state:'rendering'}).description,/after verification/);
});
