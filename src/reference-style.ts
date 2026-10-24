import path from 'node:path';
import {isDeepStrictEqual} from 'node:util';
import {type EditPlan,type Project,invariant} from './contracts.js';
import {containedFile,readJson,sha256} from './files.js';

/** Bind publication to the frozen watch record, not a newer working recipe. */
export async function verifyReferenceReceipt(project:Project,plan:EditPlan,evidence:unknown):Promise<void>{
 const contract=plan.referenceStyle;
 if(contract===undefined){invariant(evidence===undefined,'Reference evidence has no bound plan contract');return}
 invariant(contract&&typeof contract.path==='string'&&/^[a-f0-9]{64}$/.test(contract.sha256),'Invalid reference-style contract');
 const file=await containedFile(path.join(project.root,'10_WORK'),contract.path);
 invariant(await sha256(file)===contract.sha256,'Pinned reference-style snapshot changed');
 const snapshot=await readJson<any>(file),reported=evidence as any;
 invariant(reported&&isDeepStrictEqual(reported.contract,contract)&&isDeepStrictEqual(reported.snapshot,snapshot),'Render reference evidence differs from the pinned style snapshot');
 invariant(snapshot.schema==='acq-edit/reference-style-v1'&&snapshot.owner==='watch'&&snapshot.projectId===project.id&&snapshot.backend===project.backend&&snapshot.humanApproved===false&&snapshot.coverageStatus==='reported-by-watch-owner','Reference snapshot identity or approval status differs');
 const check=async(value:any,folder:string)=>{
  invariant(value&&typeof value.path==='string'&&/^[a-f0-9]{64}$/.test(value.sha256),'Reference file path/hash required');
  const source=await containedFile(path.join(project.root,folder),value.path);
  invariant(await sha256(source)===value.sha256,'Pinned reference source or inspection evidence changed');
 };
 await check(snapshot.source,'00_SOURCE');
 invariant(Array.isArray(snapshot.evidenceFiles)&&snapshot.evidenceFiles.length>0,'Pinned reference inspection evidence required');
 for(const item of snapshot.evidenceFiles)await check(item,'10_WORK');
}
