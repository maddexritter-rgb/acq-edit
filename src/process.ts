import { spawn } from 'node:child_process';
export async function run(command:string,args:string[],options:{cwd?:string;env?:NodeJS.ProcessEnv;timeout?:number}={}):Promise<string>{return new Promise((resolve,reject)=>{
 const p=spawn(command,args,{cwd:options.cwd,env:options.env||process.env,stdio:['ignore','pipe','pipe']});let out='',err='';let settled=false;
 const timer=setTimeout(()=>{p.kill('SIGTERM');reject(new Error('Process timed out; reconcile before retrying native operations'))},options.timeout??120000);
 p.stdout.on('data',b=>{out+=b;if(out.length>32_000_000){p.kill();reject(new Error('Process output limit exceeded'))}});p.stderr.on('data',b=>{err=(err+b).slice(-16000)});
 p.on('error',e=>{clearTimeout(timer);settled=true;reject(e)});p.on('close',code=>{clearTimeout(timer);if(settled)return;code===0?resolve(out):reject(new Error(`${command} exited ${code}: ${err}`))});
})}
