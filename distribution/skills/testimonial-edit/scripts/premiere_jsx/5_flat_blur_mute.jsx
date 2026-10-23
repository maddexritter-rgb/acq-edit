// Blur+mute the flat ALL_L3_REVIEW card beats (by review_flat_plan tl). RUN TWICE:
// pass 1 adds the effect where missing; pass 2 (re-run) sets Blurriness=220 + mutes. Set WORK.
var WORK="/ABS/PATH/TO/10_WORK";
function rj(p){var f=new File(p);f.open("r");var t=f.read();f.close();return eval("("+t+")");}
var fp=rj(WORK+"/review_flat_plan.json"),tl=[];for(var i=0;i<fp.cards.length;i++)tl.push(fp.cards[i].tl);
var sq=__findSequence("ALL_L3_REVIEW");app.project.activeSequence=sq;app.enableQE();
var v=sq.videoTracks[0],a=sq.audioTracks[0],qt=qe.project.getActiveSequence().getVideoTrackAt(0),real=[];
for(var i=0;i<qt.numItems;i++){var it=qt.getItemAt(i),ok=false;try{if(it&&it.name&&it.name.length>3)ok=true;}catch(e){}if(ok)real.push(i);}
var fx=qe.project.getVideoEffectByName("Gaussian Blur"),added=0,bset=0,mut=0;
for(var d=0;d<v.clips.numItems&&d<real.length;d++){var st=__ticksToSeconds(v.clips[d].start.ticks),isC=false;for(var c=0;c<tl.length;c++){if(Math.abs(st-tl[c])<0.12){isC=true;break;}}if(!isC)continue;
 var has=false,cmp=v.clips[d].components;for(var k=0;k<cmp.numItems;k++){if(cmp[k].displayName==="Gaussian Blur"){has=true;for(var p=0;p<cmp[k].properties.numItems;p++){var pr=cmp[k].properties[p];if(pr.displayName==="Blurriness"){pr.setValue(220,1);bset++;}if(pr.displayName==="Repeat Edge Pixels"){try{pr.setValue(true,1);}catch(e){}}}}}
 if(!has){var qit=qt.getItemAt(real[d]);if(qit&&fx){qit.addVideoEffect(fx);added++;}}}
for(var ai=0;ai<a.clips.numItems;ai++){var ast=__ticksToSeconds(a.clips[ai].start.ticks);for(var c2=0;c2<tl.length;c2++){if(Math.abs(ast-tl[c2])<0.12){a.clips[ai].disabled=true;mut++;break;}}}
app.project.save();return __result({added:added,blurSet:bset,muted:mut});
