import test from 'node:test';
import assert from 'node:assert/strict';
import {routeRevision} from '../dist/contracts.js';
import {jobPrompt} from '../dist/agents.js';

test('finishing removal and shortening never imply a spoken recut',()=>{
 for(const [request,owner] of [
  ['Remove the captions for the opening','caption-clips'],
  ['Remove this word from the caption','caption-clips'],
  ['Shorten the subtitles','caption-clips'],
  ['Trim the music','music'],
  ['Remove the music track','music'],
  ['Remove the headline','text-hook'],
  ['Replace the text hook','text-hook'],
  ['Remove this title card','text-hook'],
  ['Shorten the animation','promo'],
  ['Delete this graphic','promo'],
  ['Make captions larger; do not recut','caption-clips'],
  ["Don't remove this sentence. Change the font.",'caption-clips']
 ]){
  const owners=routeRevision(request);assert(owners.includes(owner),request);assert(!owners.includes('assembly-design'),request);assert(owners.includes('revision-planner'),request);
 }
});
test('explicit speech changes retain every dependent finishing owner',()=>{
 for(const request of ['Remove this sentence','Remove this word, on V1','Remove the final filler','Trim the pause','Shorten the clip','Reorder these sections','Replace the spoken hook','Fix the speech joins','Improve the cuts','Re-cut this clip','Remove this passage and make captions larger']){
  const owners=routeRevision(request);for(const owner of ['assembly-design','horizontal-to-vertical','caption-clips','text-hook','music','promo'])assert(owners.includes(owner),request+': '+owner);
 }
});
test('reference comparison routes watch without inventing a spoken recut',()=>{
 for(const request of ['Match this reference','Make this look like the linked video','Mimic this edit','Replicate the style','Match the caption style of that reel','Use this as inspiration','Recreate that look']){
  const owners=routeRevision(request);assert(owners.includes('watch'),request);assert(owners.includes('revision-planner'),request);assert(!owners.includes('assembly-design'),request);
 }
 const mixed=routeRevision('Use this reference and remove the first sentence');assert(mixed.includes('watch'));assert(mixed.includes('assembly-design'));
 assert(!routeRevision('Lower the music track volume').includes('watch'));
});
test('ambiguous requests retain the planner rather than assuming a recut',()=>{
 for(const request of ['Remove this','Make it better','Hook replacement','Change the hook'])assert(!routeRevision(request).includes('assembly-design'),request);
 assert.deepEqual(routeRevision('Make it better'),['edit','revision-planner']);
});
test('each backend and agent receives the same scope and provenance instructions',()=>{
 for(const backend of ['filmcraft','premiere','resolve'])for(const agent of ['codex','claude']){
  const prompt=jobPrompt({id:'p',root:'/project',backend,agent},{id:'j',kind:'revision'},'/project/submission.json');
  assert(prompt.includes('Backend is fixed to '+backend));assert(prompt.includes('start with revision-planner'));assert(prompt.includes('discovery hints, not permission'));assert(prompt.includes('do not by themselves authorize spoken recuts'));assert(prompt.includes('frozen reference provenance'));assert(prompt.includes('notes added later belong to the next submission'));
 }
});
