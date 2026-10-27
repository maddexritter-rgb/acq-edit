import {type Config,agentExecutable,ROOT} from './config.js';
import {run} from './process.js';
export class AgentSetupError extends Error {}
export const MIN_CLAUDE=[2,1,251] as const; // Observed model refusal below this baseline; not all-model qualification.
export async function agentReadiness(c:Config,agent=c.agent,execute:typeof run=run,env:NodeJS.ProcessEnv=process.env,cwd=ROOT){
 const command=agentExecutable(c,agent),problems:string[]=[];
 let version='unknown',authenticated:boolean|null=null;
 try{const output=await execute(command,['--version'],{env,cwd,timeout:15000,outputLimit:64000});
  const match=output.match(/\b(\d+)\.(\d+)\.(\d+)\b/);if(!match)throw Error('version');version=match[0];
  if(agent==='claude'){
   const parts=match.slice(1).map(Number);const index=parts.findIndex((v,i)=>v!==MIN_CLAUDE[i]);
   if(index>=0&&parts[index]!<MIN_CLAUDE[index]!)problems.push('Update the configured Claude CLI to 2.1.251 or newer; this version was rejected by the teammate model. Use its supported update route.');
  }
 }catch{problems.push('The configured agent CLI cannot report a version. Repair that executable before starting a job.');}
 if(agent==='claude'){
  try{const status=JSON.parse(await execute(command,['auth','status'],{env,cwd,timeout:15000,outputLimit:64000}));
   authenticated=status.loggedIn===true||(['claude.ai','oauth_token','api_key','api_key_helper','third_party'].includes(status.authMethod)&&status.loggedIn!==false);
   if(!authenticated)problems.push('Sign in using the configured Claude CLI: claude auth login. Desktop login alone does not prove CLI login.');
  }catch{authenticated=false;problems.push('Claude CLI authentication could not be verified. Run claude auth status, then claude auth login if needed.');}
 }
 return {ready:problems.length===0,agent,version,authenticated,problems,
  unverified:['Project trust and command permissions: run agent-check PROJECT_ID --smoke after interactive project setup','Selected model availability and generation credit'],
  qualification:'CLI prerequisites only; no model generation or editing performed.'};
}
export async function requireAgentReady(c:Config,agent=c.agent,cwd=ROOT){
 const report=await agentReadiness(c,agent,run,process.env,cwd);
 if(!report.ready)throw new AgentSetupError(report.problems.join(' '));
 return report;
}
