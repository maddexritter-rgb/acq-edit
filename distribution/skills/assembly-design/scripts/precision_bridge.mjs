/** Shared Premiere Agent stage launcher. Extends the existing runtime registry,
 * guard, queue and journal with stage-owned audio precision and exact export.
 * Scope comes from the selected profile; research remains disposable-only.
 */
import path from 'node:path';
import {readFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';
import {makeAudioEdgeTool,TOOL} from './native_audio_edges.mjs';
const root=process.argv[2];
if(!root||!path.isAbsolute(root))throw Error('EXPLICIT_INSTALLED_LAB_ROOT_REQUIRED');
const load=p=>import(pathToFileURL(path.join(root,p)).href);
const require=createRequire(path.join(root,'package.json'));
const {StdioServerTransport}=await import(pathToFileURL(require.resolve('@modelcontextprotocol/server/stdio')).href);
const {fromJsonSchema}=await import(pathToFileURL(require.resolve('@modelcontextprotocol/server')).href);
const {createLab}=await load('dist/lab/server.js');
const {UxpWebSocketBridge}=await load('dist/bridge/uxp-websocket-bridge.js');
const {sendCommand}=await load('dist/bridge/file-bridge.js');
const {buildToolScript}=await load('dist/bridge/script-builder.js');
const {SNAPSHOT_FUNCTION}=await load('dist/lab/context.js');
const {labToolSchema}=await load('dist/lab/runtime.js');
const {catalog}=await load('dist/lab/catalog.js');
const runtimeRoot=path.join(root,'lab/runtime');
const config=JSON.parse(readFileSync(path.join(runtimeRoot,'config.json'),'utf8'));
process.env.PREMIERE_TEMP_DIR=path.join(runtimeRoot,'mailbox');
process.env.PREMIERE_MCP_CAPABILITIES='inspect,edit,export,filesystem';
process.env.PREMIERE_MCP_TELEMETRY='off';
const uxp=new UxpWebSocketBridge({token:config.token,port:config.port,path:'/lab-uxp'});
if(process.env.PREMIERE_AGENT_UXP_LISTEN==='1')await uxp.start();
const lab=createLab(root,runtimeRoot,uxp);
// Fail closed if the installed constructor no longer exposes the shared registry.
if(!lab.runtime.tools||!lab.jobs||!lab.inventory.operations||lab.runtime.tools[TOOL])throw Error('LAB_EXTENSION_INTERFACE_CHANGED');
const options={tempDir:path.join(runtimeRoot,'mailbox'),timeoutMs:15000,pagedResponse:true,failFastOnUnreadyHeartbeat:true};
const {exportTools}=await import('../../edit/scripts/native_export_tools.mjs');
const extra={
 [TOOL]:makeAudioEdgeTool({sendCommand,buildToolScript,snapshotFunction:SNAPSHOT_FUNCTION},options),
 ...exportTools({sendCommand,buildToolScript},options)
};
for(const [name,tool] of Object.entries(extra)){
 if(lab.runtime.tools[name])throw Error('DUPLICATE_STAGE_TOOL');
 lab.runtime.tools[name]=tool;
 const entry=catalog(root,{[name]:tool}).operations.find(x=>x.name===name);
 if(!entry||!entry.authorityPermitted)throw Error('STAGE_TOOL_AUTHORITY_UNAVAILABLE');
 lab.inventory.operations.push(entry);
 lab.server.registerTool(name,{description:tool.description,inputSchema:fromJsonSchema(labToolSchema(tool.parameters))},async input=>{
  const {_lab,_lab_async,...args}=input;
  try{
   const value=_lab_async?lab.jobs.submit(name,args,_lab):await lab.runtime.call(name,args,_lab);
   return {content:[{type:'text',text:JSON.stringify(value)}],...(['failed','unknown'].includes(value?.status)||value?.success===false?{isError:true}:{})};
  }catch(e){return {isError:true,content:[{type:'text',text:JSON.stringify({status:'refused',error:String(e)})}]};}
 });
}
lab.inventory.counts.operations=lab.inventory.operations.length;
lab.inventory.counts.defaultAuthorityOperations=lab.inventory.operations.filter(x=>x.authorityPermitted).length;
await lab.server.connect(new StdioServerTransport());
const close=async()=>{await lab.server.close();await uxp.stop();process.exit(0);};
process.once('SIGTERM',close);process.once('SIGINT',close);
