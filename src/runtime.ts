import path from 'node:path';
import {type Config,ROOT} from './config.js';
import {run} from './process.js';
import {invariant} from './contracts.js';

/** Read-only installation check. Never replace a stale or edited runtime. */
export async function verifyRuntime(config:Config,execute:typeof run=run){
 try{
  const result=JSON.parse(await execute(config.python,[path.join(ROOT,'scripts','materialize.py'),'--verify']));
  invariant(result?.ready===true&&Number.isInteger(result.verifiedFiles)&&result.verifiedFiles>0&&Number.isInteger(result.routedEntrypoints)&&result.routedEntrypoints>0,'Runtime verifier did not confirm installed skill files and routes');
  return result;
 }catch(error){throw new Error(`Skill runtime preflight failed before agent/editor launch. Preserve this checkout and install the current distribution in a fresh checkout: ${(error as Error).message}`)}
}
