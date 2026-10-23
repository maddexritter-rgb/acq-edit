// Add Gaussian Blur to every card beat across all sequences. real[] = QE items with valid name
// (skips the 0.5s leader + gap items => aligns 1:1 with DOM clips). Set WORK.
var WORK="/ABS/PATH/TO/10_WORK";
function rj(p){var f=new File(p);f.open("r");var t=f.read();f.close();return eval("("+t+")");}
var man=rj(WORK+"/_batch_manifest.json");app.enableQE();var added=0;
for(var m=0;m<man.length;m++){var sq=__findSequence(man[m].seq);if(!sq)continue;app.project.activeSequence=sq;
 var seg=rj(man[m].workdir+"/premiere_plan.json").segments,cardpos=[];for(var j=0;j<seg.length;j++){if(seg[j].kind==="card")cardpos.push(seg[j].pos);}
 var v=sq.videoTracks[0],qt=qe.project.getActiveSequence().getVideoTrackAt(0),real=[];
 for(var i=0;i<qt.numItems;i++){var it=qt.getItemAt(i),ok=false;try{if(it&&it.name&&it.name.length>3)ok=true;}catch(e){}if(ok)real.push(i);}
 var fx=qe.project.getVideoEffectByName("Gaussian Blur");
 for(var d=0;d<v.clips.numItems&&d<real.length;d++){var st=__ticksToSeconds(v.clips[d].start.ticks),isC=false;for(var c=0;c<cardpos.length;c++){if(Math.abs(st-cardpos[c])<0.15){isC=true;break;}}if(!isC)continue;
  var has=false;for(var k=0;k<v.clips[d].components.numItems;k++){if(v.clips[d].components[k].displayName==="Gaussian Blur"){has=true;break;}}
  if(!has){var qit=qt.getItemAt(real[d]);if(qit&&fx){qit.addVideoEffect(fx);added++;}}}}
app.project.save();return __result({added:added});
