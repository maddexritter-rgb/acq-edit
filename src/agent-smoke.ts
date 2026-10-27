/** Explicit onboarding probe: no footage, provider keys, editor or permissions changes. */
import path from 'node:path';
import {randomUUID} from 'node:crypto';
import {mkdir,readFile} from 'node:fs/promises';
import {type Config,ROOT,agentExecutable} from './config.js';
import {type Project,invariant} from './contracts.js';
import {atomicJson} from './files.js';
import {requireAgentReady} from './agent-readiness.js';
import {runAgentTransport} from './agent-transport.js';
export async function smokeAgent(c:Config,p:Project,transport=runAgentTransport,checkReady=requireAgentReady){
 invariant(p.agent==='claude','This project trust probe currently supports Claude; use documented Codex setup checks.');
 const readiness=await checkReady(c,p.agent,p.root);
 const directory=path.join(p.root,'10_WORK','agent-checks',randomUUID());await mkdir(directory,{recursive:true});
 const marker=randomUUID(),proof=path.join(directory,'proof.txt');
 const quote=(s:string)=>"'"+s.replaceAll("'","'\\''")+"'";
 const commands=[`${quote(process.execPath)} ${quote(path.join(ROOT,'dist/cli.js'))} help`,`${quote(c.python)} ${quote(path.join(ROOT,'scripts/sample_render.py'))} --help`];
 const prompt=`ACQ Edit onboarding smoke test only. Do not edit configuration, settings, credentials, media or native projects. Read ${path.join(p.root,'AGENTS.md')}. Run exactly these two independent Bash commands: ${JSON.stringify(commands)}. Use the Write tool to create ${proof} containing exactly ${marker}. If any action is denied, stop and explain it. Do not request or change permissions, use alternate commands, or run an editor. Then finish.`;
 const env:NodeJS.ProcessEnv={...process.env,PATH:path.dirname(process.execPath)+path.delimiter+(process.env.PATH||'')};
 for(const key of ['ASSEMBLYAI_API_KEY','GEMINI_API_KEY','EDITORIAL_BRAIN_READ_KEY'])delete env[key];
 const calls=new Map<string,string>(),passed=new Set<string>();let denied=false;
 try{
  await transport({agent:'claude',command:agentExecutable(c,'claude'),args:['-p',prompt,'--output-format','stream-json','--verbose','--permission-mode','acceptEdits','--tools','Bash,Read,Write','--add-dir',ROOT],cwd:p.root,env,prompt,writableRoots:[directory],onSession:()=>{},timeoutMs:180000,
   onLine:async line=>{const row=JSON.parse(line);if(row.type==='system'&&row.subtype==='permission_denied')denied=true;if(row.permission_denials?.length)denied=true;
    const blocks=row.message?.content;if(!Array.isArray(blocks))return;
    for(const block of blocks){if(block.type==='tool_use'&&block.name==='Bash')calls.set(block.id,block.input?.command);
     if(block.type==='tool_result'&&calls.has(block.tool_use_id)){if(block.is_error)denied=true;else passed.add(calls.get(block.tool_use_id)!);}}
   }});
  invariant(!denied&&commands.every(x=>passed.has(x))&&(await readFile(proof,'utf8')).trim()===marker,'Project smoke failed: command permission or file access was not demonstrated');
  const report={ready:true,projectId:p.id,projectRoot:p.root,readiness,commands,checkedAt:new Date().toISOString(),qualification:'Observed basic commands and project writes only; not all editing permissions, provider credit or native qualification.'};
  await atomicJson(path.join(directory,'result.json'),report);return report;
 }catch{
  const report={ready:false,projectId:p.id,projectRoot:p.root,checkedAt:new Date().toISOString(),repair:'Open Claude interactively in this exact project folder, accept its trust prompt and review the command permissions in docs/CLAUDE_SETUP.md. Then rerun this check. No permissions were changed by ACQ Edit.'};
  await atomicJson(path.join(directory,'result.json'),report);return report;
 }
}
