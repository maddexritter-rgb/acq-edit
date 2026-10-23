// Build one native sequence per clip: cuts (V1) + card PNGs (V2) + super (V3). NO blur/audio here
// (those are passes 2+3 — inline blur/mute is unreliable). Reads _batch_manifest.json + each
// premiere_plan.json. Set WORK to the job's 10_WORK. Run via execute_extendscript.
var WORK="/ABS/PATH/TO/10_WORK";
function rj(p){var f=new File(p);f.open("r");var t=f.read();f.close();return eval("("+t+")");}
function imp(p){var n=p.split("/").pop();var e=__findProjectItem(n);if(e)return e;app.project.importFiles([p],true,app.project.rootItem,false);return __findProjectItem(n);}
var man=rj(WORK+"/_batch_manifest.json"),CARDS=WORK+"/_cards2",SUPD=WORK+"/_supers/";app.enableQE();var out=[];
for(var m=0;m<man.length;m++){var SEQ=man[m].seq,WD=man[m].workdir,plan=rj(WD+"/premiere_plan.json"),seg=plan.segments;
 for(var i=app.project.sequences.numSequences-1;i>=0;i--){if(app.project.sequences[i].name===SEQ)app.project.deleteSequence(app.project.sequences[i]);}
 var src=imp(plan.source);imp(SUPD+SEQ+".png");for(var c=0;c<seg.length;c++){if(seg[c].kind==="card")imp(CARDS+"/"+seg[c].card_png);}
 src.setInPoint(seg[0].src_in,4);src.setOutPoint(seg[0].src_out,4);app.project.createNewSequenceFromClips(SEQ,[src]);
 var sq=app.project.activeSequence,v=sq.videoTracks[0],cursor=0.5;
 for(var i2=0;i2<seg.length;i2++){src.setInPoint(seg[i2].src_in,4);src.setOutPoint(seg[i2].src_out,4);var t=new Time();t.seconds=cursor;v.overwriteClip(src,t);cursor=Math.round((cursor+(seg[i2].src_out-seg[i2].src_in))*24000/1001)*1001/24000;}
 var qv0=qe.project.getActiveSequence().getVideoTrackAt(0),toRm=[];
 for(var s=0;s<v.clips.numItems;s++){var cl=v.clips[s];if(__ticksToSeconds(cl.duration.ticks)<0.12||__ticksToSeconds(cl.start.ticks)<0.49)toRm.push(s);}
 for(var r=toRm.length-1;r>=0;r--){var qc=qv0.getItemAt(toRm[r]);if(qc&&typeof qc.remove==="function"){try{qc.remove(false,false);}catch(e){}}}
 var v2=sq.videoTracks[1],v3=sq.videoTracks[2];
 for(var j=0;j<seg.length;j++){if(seg[j].kind!=="card")continue;var it=__findProjectItem(seg[j].card_png);if(it){var tt=new Time();tt.seconds=seg[j].pos;v2.overwriteClip(it,tt);for(var q=0;q<v2.clips.numItems;q++){if(Math.abs(__ticksToSeconds(v2.clips[q].start.ticks)-seg[j].pos)<0.1){var te=new Time();te.seconds=seg[j].pos+seg[j].dur;v2.clips[q].end=te;break;}}}}
 var sup=__findProjectItem(SEQ+".png");if(sup){var t2=new Time();t2.seconds=0.5;v3.overwriteClip(sup,t2);for(var q3=0;q3<v3.clips.numItems;q3++){if(Math.abs(__ticksToSeconds(v3.clips[q3].start.ticks)-0.5)<0.1){var ts=new Time();ts.seconds=12;v3.clips[q3].end=ts;break;}}}
 out.push(SEQ+":"+v.clips.numItems);}
app.project.save();return __result({built:out});
