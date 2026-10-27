#!/usr/bin/env node
// Protocol simulator only. Never an editorial or native editing proof.
import {createInterface} from 'node:readline';
import {writeFileSync} from 'node:fs';
if(process.argv.includes('--version')){console.log('2.1.312 fixture');process.exit(0)}
const scenario=process.env.SCENARIO;
const emit=x=>process.stdout.write(JSON.stringify(x)+'\n');
if(process.env.PID_FILE)writeFileSync(process.env.PID_FILE,String(process.pid));
if(scenario==='hang'){process.on('SIGTERM',()=>{});setInterval(()=>{},1000)}
else if(scenario?.startsWith('claude')){
 emit({type:'system',session_id:'claude-session'});
 if(['claude-background','claude-late-error'].includes(scenario)){
  emit({type:'result',subtype:'success',is_error:false,session_id:'claude-session',result:'Rendering'});
  setTimeout(()=>{emit({type:'background-finished'});emit({type:'result',subtype:'success',is_error:scenario==='claude-late-error',session_id:'claude-session',result:scenario==='claude-late-error'?'late failure':'Done'})},80);
 }
 if(scenario==='claude-success')emit({type:'result',subtype:'success',is_error:false,session_id:'claude-session',result:'Done'});
 if(scenario==='claude-credit')emit({type:'result',subtype:'success',is_error:true,session_id:'claude-session',result:'Credit balance is too low'});
 if(scenario==='claude-error')emit({type:'result',subtype:'error_during_execution',is_error:true,session_id:'claude-session',errors:['Fixture failure']});
 if(scenario==='claude-log-failure'){emit({type:'result',subtype:'success',session_id:'claude-session'});setInterval(()=>{},1000)}
 if(scenario==='claude-malformed')console.log('not JSON');
}else{
 createInterface({input:process.stdin}).on('line',line=>{
  const m=JSON.parse(line),reply=result=>emit({id:m.id,result});
  if(m.method==='initialize')reply({});
  if(m.method==='thread/start'||m.method==='thread/resume')reply({thread:{id:scenario==='wrong-session'?'unexpected':(m.params.threadId||'thread-fixture')}});
  if(m.method==='turn/start'){
   const event=(id,status='completed')=>emit({method:'turn/completed',params:{threadId:m.params.threadId,turn:{id,status}}});
   if(scenario==='disconnect'){process.exit(0)}
   if(scenario==='approval'){emit({id:100,method:'item/commandExecution/requestApproval',params:{}});return}
   if(scenario==='early'){event('turn-fixture');reply({turn:{id:'turn-fixture'}});return}
   reply({turn:{id:'turn-fixture'}});
   if(scenario==='wrong-turn'){event('older-turn');return}
   event('turn-fixture',scenario==='turn-failed'?'failed':'completed');
  }
 });
}
