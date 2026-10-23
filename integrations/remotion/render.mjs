import {bundle} from '@remotion/bundler';
import {selectComposition,renderMedia} from '@remotion/renderer';
import {readFile,writeFile,lstat,mkdir,open,unlink} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createHash} from 'node:crypto';
import {resolveProps} from './props.mjs';

const [propsFile,destination]=process.argv.slice(2);
if(!propsFile||!destination)throw Error('Usage: npm run render -- props.json /project/10_WORK/graphic.mov');
const output=path.resolve(destination),receipt=output+'.json',lock=output+'.lock';
for(const file of [output,receipt,lock]){
 try{await lstat(file);throw Error('Asset, receipt or render lock exists; reconcile and choose a new path')}
 catch(e){if(e.code!=='ENOENT')throw e}
}
const inputProps=resolveProps(JSON.parse(await readFile(propsFile,'utf8')));
const root=path.dirname(fileURLToPath(import.meta.url));
const digest=bytes=>createHash('sha256').update(bytes).digest('hex');
const sourceHashes=Object.fromEntries(await Promise.all(['index.tsx','props.mjs','render.mjs','package-lock.json'].map(async file=>[file,digest(await readFile(path.join(root,file)))])));
await mkdir(path.dirname(output),{recursive:true});
const reservation=await open(lock,'wx',0o600);await reservation.writeFile(JSON.stringify({pid:process.pid,output,startedAt:new Date().toISOString()}));await reservation.close();
// Leave partial output and the reservation on failure for explicit reconciliation.
const serveUrl=await bundle({entryPoint:path.join(root,'index.tsx')});
const composition=await selectComposition({serveUrl,id:'TitleCard',inputProps});
await renderMedia({serveUrl,composition,inputProps,codec:'prores',proResProfile:'4444',pixelFormat:'yuva444p10le',imageFormat:'png',outputLocation:output});
for(const [file,hash] of Object.entries(sourceHashes))if(digest(await readFile(path.join(root,file)))!==hash)throw Error('Motion source changed during render');
const sha256=digest(await readFile(output));
await writeFile(receipt,JSON.stringify({schema:'acq-edit/motion-asset-v1',renderer:'remotion',version:'4.0.538',composition:'TitleCard',inputProps,sourceHashes,output,sha256,finalComposition:'selected-native-editor'},null,2),{flag:'wx'});
await unlink(lock);
console.log(JSON.stringify({output,sha256,receipt}));
