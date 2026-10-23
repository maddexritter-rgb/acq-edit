import { open,readFile,unlink } from 'node:fs/promises';
import path from 'node:path';
export async function serviceLock(home:string){const file=path.join(home,'service.lock');
 for(let attempt=0;attempt<2;attempt++){
  try{const f=await open(file,'wx',0o600);await f.writeFile(JSON.stringify({pid:process.pid}));await f.close();return async()=>{try{const prior=JSON.parse(await readFile(file,'utf8'));if(prior.pid===process.pid)await unlink(file)}catch{}}}
  catch(e:any){if(e.code!=='EEXIST')throw e;const prior=JSON.parse(await readFile(file,'utf8'));if(!Number.isInteger(prior.pid)||prior.pid<=0)throw new Error('Invalid service lock; inspect it before restarting');try{process.kill(prior.pid,0);throw new Error('ACQ Edit service is already running')}catch(probe:any){if(probe.code!=='ESRCH')throw probe;await unlink(file)}}
 }throw new Error('Could not acquire service lock');
}
