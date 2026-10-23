// Set Blurriness=220 + Repeat Edge Pixels + MUTE audio on every card beat. Separate pass from
// add (setValue won't commit in the same script as addVideoEffect). Set WORK.
var WORK="/ABS/PATH/TO/10_WORK";
function rj(p){var f=new File(p);f.open("r");var t=f.read();f.close();return eval("("+t+")");}
var man=rj(WORK+"/_batch_manifest.json");var bset=0,mut=0,bad=0;
for(var m=0;m<man.length;m++){var sq=__findSequence(man[m].seq);if(!sq)continue;
 var seg=rj(man[m].workdir+"/premiere_plan.json").segments,cardpos=[];for(var j=0;j<seg.length;j++){if(seg[j].kind==="card")cardpos.push(seg[j].pos);}
 var v=sq.videoTracks[0],a=sq.audioTracks[0];
 for(var d=0;d<v.clips.numItems;d++){var st=__ticksToSeconds(v.clips[d].start.ticks),isC=false;for(var c=0;c<cardpos.length;c++){if(Math.abs(st-cardpos[c])<0.15){isC=true;break;}}if(!isC)continue;
  var val=null;for(var k=0;k<v.clips[d].components.numItems;k++){var cp=v.clips[d].components[k];if(cp.displayName==="Gaussian Blur"){for(var p=0;p<cp.properties.numItems;p++){var pr=cp.properties[p];if(pr.displayName==="Blurriness"){pr.setValue(220,1);val=pr.getValue();bset++;}if(pr.displayName==="Repeat Edge Pixels"){try{pr.setValue(true,1);}catch(e){}}}}}
  if(val!==220)bad++;}
 for(var ai=0;ai<a.clips.numItems;ai++){var ast=__ticksToSeconds(a.clips[ai].start.ticks);for(var c2=0;c2<cardpos.length;c2++){if(Math.abs(ast-cardpos[c2])<0.15){a.clips[ai].disabled=true;mut++;break;}}}}
app.project.save();return __result({blurSet:bset,muted:mut,bad:bad});
