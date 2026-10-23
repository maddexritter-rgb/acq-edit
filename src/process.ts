import { spawn } from 'node:child_process';
export interface RunOptions {cwd?:string;env?:NodeJS.ProcessEnv;timeout?:number;signal?:AbortSignal;outputLimit?:number;shutdownGraceMs?:number;onSpawn?:(pid:number)=>void}
/** Do not release a native-operation caller while its owned process is still running. */
export async function run(command:string,args:string[],options:RunOptions={}):Promise<string>{
 options.signal?.throwIfAborted();
 return new Promise((resolve,reject)=>{
  const p=spawn(command,args,{cwd:options.cwd,env:options.env||process.env,detached:process.platform!=='win32',stdio:['ignore','pipe','pipe']});
  let out='',err='',failure:Error|undefined,stopping=false,killTimer:NodeJS.Timeout|undefined;
  const signal=(s:NodeJS.Signals)=>{if(!p.pid)return;try{if(process.platform==='win32')p.kill(s);else process.kill(-p.pid,s)}catch(e:any){if(e.code!=='ESRCH')failure||=e}};
  const stop=(e:Error)=>{failure||=e;if(stopping)return;stopping=true;signal('SIGTERM');killTimer=setTimeout(()=>signal('SIGKILL'),options.shutdownGraceMs??5000)};
  const abort=()=>stop(new Error('Process interrupted; reconcile before retrying native operations'));
  const timer=setTimeout(()=>stop(new Error('Process timed out; reconcile before retrying native operations')),options.timeout??120000);
  options.signal?.addEventListener('abort',abort,{once:true});
  p.stdout.on('data',b=>{if(stopping)return;out+=b;if(Buffer.byteLength(out)>(options.outputLimit??32_000_000))stop(new Error('Process output limit exceeded'))});
  p.stderr.on('data',b=>{err=(err+b).slice(-16000)});
  p.on('error',stop);
  p.on('spawn',()=>{try{if(p.pid)options.onSpawn?.(p.pid)}catch(e){stop(e as Error)}});
  p.on('close',code=>{clearTimeout(timer);if(killTimer)clearTimeout(killTimer);options.signal?.removeEventListener('abort',abort);
   if(failure)reject(failure);else if(code===0)resolve(out);else reject(new Error(`${command} exited ${code}: ${err}`));
  });
  if(options.signal?.aborted)abort();
 });
}
