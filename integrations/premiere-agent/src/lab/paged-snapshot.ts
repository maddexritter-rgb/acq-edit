// Native comparisons keep full values; hashing happens in Node after bounded reads.
export const PAGED_COMPARE_HELPERS = `
function __labReadGuardPage(path){var f=new File(path);f.encoding='UTF-8';if(!f.exists||!f.open('r'))throw Error('LAB_GUARD_PAGE_MISSING');var text=f.read();f.close();if(text.length>1500000)throw Error('LAB_GUARD_PAGE_LIMIT');return JSON.parse(text);}
function __labCapturePages(sequence){
 var p=app.project,s=sequence||(p&&p.activeSequence),r={projectPath:p?String(p.path):'',sequenceId:null,tracks:[],nativePages:[]},offset=0,total=null;
 do{var limit=50,page;while(true){try{page=__labSnapshot(s,{offset:offset,limit:limit});break;}catch(err){if(String(err).indexOf('LAB_SNAPSHOT_PAGE_SIZE_LIMIT')<0||limit===1)throw err;limit=Math.max(1,Math.floor(limit/2));}}
 r.projectPath=page.projectPath;r.sequenceId=page.sequenceId;r.nativePages.push(page);if(!page._paging)break;if(total!==null&&total!==page._paging.total)throw Error('LAB_PAGED_COUNT_CHANGED');total=page._paging.total;offset+=limit;}while(offset<total);return r;
}
function __labVerifyPages(expected,sequence,compare){
 var p=app.project,s=sequence||(p&&p.activeSequence);if(!p||String(p.path)!==expected.projectPath||!s||String(s.sequenceID)!==expected.sequenceId)return false;
 var owned=false;for(var si=0;si<p.sequences.numSequences;si++)if(String(p.sequences[si].sequenceID)===expected.sequenceId)owned=true;if(!owned)return false;
 var pages=expected.nativePages||expected.pages,offset=0,total=null;if(!pages||!pages.length)return false;
 for(var i=0;i<pages.length;i++){if(i>0&&offset>=total)return false;var want=expected.nativePages?pages[i]:__labReadGuardPage(pages[i].path),cursor=want._paging;if(!cursor||cursor.offset!==offset||cursor.limit<1||cursor.limit>50||total!==null&&total!==cursor.total)return false;total=cursor.total;if(!compare(JSON.parse(JSON.stringify(__labSnapshot(s,{offset:cursor.offset,limit:cursor.limit}))),want))return false;offset+=cursor.limit;}
 return offset>=total;
}`;
