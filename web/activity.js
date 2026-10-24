// Describe persisted state without pretending a journal proves a host is alive.
export function projectActivity(data){
 const reservations=[
  ...(data.nativeOperations||[]).filter(o=>['running','reconciliation_required'].includes(o.state)).map(o=>({kind:'Editor operation',id:o.id,state:o.state,detail:o.action,error:o.error,attention:o.state==='reconciliation_required'})),
  ...(data.intakes||[]).filter(i=>!['ready','failed'].includes(i.state)).map(i=>({kind:'Source transfer',id:i.id,state:i.state,error:i.error,attention:i.state==='reconciliation_required'})),
  ...(data.driveBatches||[]).filter(b=>!['ready','abandoned'].includes(b.state)).map(b=>({kind:'Drive folder transfer',id:b.id,state:b.state,error:b.error,attention:b.state==='failed'})),
  ...data.jobs.filter(j=>['editing','rendering','reconciliation_required'].includes(j.state)).map(j=>({kind:'Editing job',id:j.id,state:j.state,error:j.error,attention:j.state==='reconciliation_required'})),
 ];
 const attention=reservations.some(r=>r.attention),reserved=reservations.length>0;
 const heading=attention?'An edit or transfer needs recovery review':reserved?'Waiting for the current work to finish':'';
 const description=attention?'Ask your agent to inspect the editor and saved work before continuing. Your existing clips and feedback remain available.':reserved?'The project is reserved by an edit or source transfer. Additional revisions will wait in the queue. You can keep reviewing and saving notes.':'';
 const request=reserved?[
  `Inspect the current ACQ Edit state for project ${data.project.id} (${data.project.title}).`,
  `Project folder: ${data.project.root}`,
  `Keep the selected backend: ${data.project.backend}.`,
  'The review room observed these reservations; reread current state before acting:',
  ...reservations.map(r=>`${r.kind} ${r.id}: ${r.state}${r.detail?' ('+r.detail+')':''}`),
  'Check the actual command processes and exact editor/project/export state. If work is still running, observe that work; do not restart it. If it stopped or failed, preserve existing media and notes, verify the outcome, and follow docs/NATIVE_RECOVERY.md or docs/INTAKE.md as appropriate before releasing its reservation. Do not clear state based only on elapsed time or this request.',
 ].join('\n'):'';
 return {reserved,attention,heading,description,request,reservations};
}
export function jobPresentation(job){
 const labels={queued:'Queued',editing:'Editing',rendering:'Rendering',ready:'Ready for review',failed:'Failed',reconciliation_required:'Needs recovery review'};
 const descriptions={queued:'Waiting for its turn. The submitted notes are saved.',editing:'Your agent is working on the submitted request.',rendering:'A render was requested. The new version will appear after verification.',ready:'The new versions are available. Review them to make your decision.',failed:'This request did not complete. Existing versions and feedback are retained.',reconciliation_required:'The outcome needs inspection before more editing can start.'};
 return {label:labels[job.state]||job.state,description:descriptions[job.state]||'Check this request with your agent.'};
}
