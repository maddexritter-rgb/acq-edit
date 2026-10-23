// Build ALL_L3_REVIEW as a FLAT (non-nested) timeline so the editor trims in place.
// V1 = every clip contiguous, V2 = all card PNGs, V3 = all supers. Reads review_flat_plan.json. Set WORK.
var WORK="/ABS/PATH/TO/10_WORK";
function rj(p){var f=new File(p);f.open("r");var t=f.read();f.close();return eval("("+t+")");}
function imp(p){var n=p.split("/").pop();var e=__findProjectItem(n);if(e)return e;app.project.importFiles([p],true,app.project.rootItem,false);return __findProjectItem(n);}
var fp=rj(WORK+"/review_flat_plan.json"),clips=fp.clips,CARDS=WORK+"/_cards2",SUPD=WORK+"/_supers/";
for(var i=app.project.sequences.numSequences-1;i>=0;i--){if(app.project.sequences[i].name==="ALL_L3_REVIEW")app.project.deleteSequence(app.project.sequences[i]);}
var sm={};for(var c=0;c<clips.length;c++)sm[clips[c].source]=1;for(var s in sm)sm[s]=imp(s);
var s0=clips[0];sm[s0.source].setInPoint(s0.src_in,4);sm[s0.source].setOutPoint(s0.src_out,4);
app.project.createNewSequenceFromClips("ALL_L3_REVIEW",[sm[s0.source]]);
var sq=app.project.activeSequence,v=sq.videoTracks[0];
for(var k=1;k<clips.length;k++){var cl=clips[k],it=sm[cl.source];it.setInPoint(cl.src_in,4);it.setOutPoint(cl.src_out,4);var t=new Time();t.seconds=cl.tl;v.overwriteClip(it,t);}
var v2=sq.videoTracks[1],v3=sq.videoTracks[2];
for(var i2=0;i2<fp.cards.length;i2++){var cd=fp.cards[i2],it2=imp(CARDS+"/"+cd.card_png);if(it2){var t2=new Time();t2.seconds=cd.tl;v2.overwriteClip(it2,t2);for(var q=0;q<v2.clips.numItems;q++){if(Math.abs(__ticksToSeconds(v2.clips[q].start.ticks)-cd.tl)<0.08){var te=new Time();te.seconds=cd.tl+cd.dur;v2.clips[q].end=te;break;}}}}
for(var s3=0;s3<fp.supers.length;s3++){var su=fp.supers[s3],it3=imp(SUPD+su.seq+".png");if(it3){var t3=new Time();t3.seconds=su.tl;v3.overwriteClip(it3,t3);for(var q2=0;q2<v3.clips.numItems;q2++){if(Math.abs(__ticksToSeconds(v3.clips[q2].start.ticks)-su.tl)<0.08){var te2=new Time();te2.seconds=su.tl+su.dur;v3.clips[q2].end=te2;break;}}}}
app.project.save();return __result({v1:v.clips.numItems,v2:v2.clips.numItems,v3:v3.clips.numItems});
