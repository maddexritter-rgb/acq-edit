// Deliberately separate from the effect/keyframe editing guard. A media repair
// guards the entire project's media identities and structural timeline state.
// It does not inspect or authorize effect edits.
export const MEDIA_REPAIR_SNAPSHOT = `function __labSnapshot(){
 var p=app.project;if(!p||!p.sequences)throw Error('MEDIA_PROJECT_UNAVAILABLE');
 var r={snapshotMode:'media_repair',projectPath:String(p.path),sequenceId:p.activeSequence?String(p.activeSequence.sequenceID):null,tracks:[],sequences:[],media:[]},count=0;
 if(p.sequences.numSequences>50)throw Error('MEDIA_SEQUENCE_LIMIT');
 for(var i=0;i<p.sequences.numSequences;i++){
  var s=p.sequences[i],row={id:String(s.sequenceID),name:String(s.name),settings:s.getSettings(),markers:[],tracks:[]};
  var marker=s.markers.getFirstMarker(),mc=0;while(marker){if(++mc>2000)throw Error('MEDIA_MARKER_LIMIT');row.markers.push({name:String(marker.name),comments:String(marker.comments),start:String(marker.start.ticks),end:String(marker.end.ticks)});marker=s.markers.getNextMarker(marker);}
  for(var kind=0;kind<2;kind++){var ts=kind?s.audioTracks:s.videoTracks;
   for(var t=0;t<ts.numTracks;t++){var tr=ts[t],out={kind:kind,index:t,name:String(tr.name),locked:typeof tr.isLocked==='function'?tr.isLocked():null,muted:typeof tr.isMuted==='function'?tr.isMuted():null,clips:[]};
    for(var c=0;c<tr.clips.numItems;c++){if(++count>10000)throw Error('MEDIA_CLIP_LIMIT');var clip=tr.clips[c];out.clips.push({id:String(clip.nodeId),name:String(clip.name),sourceId:clip.projectItem?String(clip.projectItem.nodeId):null,sourceName:clip.projectItem?String(clip.projectItem.name):null,start:String(clip.start.ticks),end:String(clip.end.ticks),inPoint:String(clip.inPoint.ticks),outPoint:String(clip.outPoint.ticks),speed:clip.getSpeed(),disabled:!!clip.disabled});}row.tracks.push(out);
   }
  }r.sequences.push(row);
 }
 var seen={},items=0;
 function walk(bin,depth){if(depth>30)throw Error('MEDIA_TREE_DEPTH_LIMIT');for(var n=0;n<bin.children.numItems;n++){if(++items>5000)throw Error('MEDIA_TREE_LIMIT');var item=bin.children[n],id=String(item.nodeId);if(seen['id:'+id])throw Error('MEDIA_ID_AMBIGUOUS');seen['id:'+id]=true;
  if(item.type===2){walk(item,depth+1);continue;}
  var mediaPath=item.getMediaPath();if(mediaPath)r.media.push({id:id,name:String(item.name),path:String(mediaPath),offline:!!item.isOffline()});
 }}walk(p.rootItem,0);
 if(r.sequenceId){var owned=false;for(var j=0;j<r.sequences.length;j++)if(r.sequences[j].id===r.sequenceId)owned=true;if(!owned)throw Error('MEDIA_FOREIGN_SEQUENCE');}
 if(JSON.stringify(r).length>1500000)throw Error('MEDIA_REPAIR_SNAPSHOT_LIMIT');return r;
}`;
