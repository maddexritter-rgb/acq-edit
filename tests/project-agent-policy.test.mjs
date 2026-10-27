import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,readdir,readlink,rm} from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import {createProject} from '../dist/projects.js';

test('new editing projects expose six skills and pin the ACQ Edit Agent transport',async t=>{
 const root=await mkdtemp(path.join(os.tmpdir(),'acq-project-policy-'));
 t.after(()=>rm(root,{recursive:true,force:true}));
 const project=await createProject({addProject(){}},root,'Test','premiere','codex');
 for(const agent of ['.agents','.claude']){
  const folder=path.join(project.root,agent,'skills');
  assert.deepEqual((await readdir(folder)).sort(),['edit','assembly-design','horizontal-to-vertical','caption-clips','music','monday'].sort());
  assert((await readlink(path.join(folder,'edit'))).endsWith('/.local/skills/edit'));
 }
 const instructions=await readFile(path.join(project.root,'AGENTS.md'),'utf8');
 assert(instructions.includes('only ACQ Edit Agent MCP'));
 assert(instructions.includes('Never use ambient mcp__premiere_pro'));
 assert(instructions.includes('no fallback'));
});
