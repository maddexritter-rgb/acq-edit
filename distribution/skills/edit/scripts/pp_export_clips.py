#!/usr/bin/env python3
"""Prepare exact native export scripts and verify the rendered files.

No connector, app launch, implicit activation, timeline trimming, or upload here.
Dispatch generated bodies once through the explicitly selected supported bridge,
retaining the original operation receipt. See references/native-export.md.
"""
from __future__ import annotations
import argparse, hashlib, json, subprocess, time, uuid
from fractions import Fraction
from pathlib import Path

def es(script_body: str, timeout: float = 30.0):
    """Retired raw-script entry; the production connector only accepts typed operations."""
    raise RuntimeError('Raw mailbox scripts are retired. Run edit/scripts/premiere_agent.py doctor, then use the owning stage driver or a typed operation from premiere_agent.py schema. Never start the old bridge or replay this body.')


TICKS=254016000000
SNAPSHOT=r'''
function exportState(s){var tracks=[];
 for(var k=0;k<2;k++){var ts=k?s.audioTracks:s.videoTracks;
  for(var t=0;t<ts.numTracks;t++){var tr=ts[t],items=[];
   for(var c=0;c<tr.clips.numItems;c++){var x=tr.clips[c];items.push({id:String(x.nodeId),name:x.name,start:String(x.start.ticks),end:String(x.end.ticks),sourceIn:String(x.inPoint.ticks),sourceOut:String(x.outPoint.ticks),disabled:!!x.disabled,path:x.projectItem?x.projectItem.getMediaPath():null});}
   tracks.push({kind:k,index:t,muted:tr.isMuted(),clips:items});}}
 return {tracks:tracks,settings:s.getSettings()};}
'''

def exact(value):
    if not isinstance(value,str) or not value.isdecimal():raise ValueError('Nonnegative decimal tick string required')
    return int(value)

def identity(project,uid):
    if not Path(project).is_absolute() or not uid:raise ValueError('Absolute project path and exact sequence UID required')
    return 'if(app.project.path!=='+json.dumps(project)+'||!app.project.activeSequence||String(app.project.activeSequence.sequenceID)!=='+json.dumps(uid)+')throw Error("TARGET_CHANGED");var s=app.project.activeSequence;'

def inspection_script(project,uid):
    return identity(project,uid)+SNAPSHOT+'return {project:app.project.path,sequence:String(s.sequenceID),state:exportState(s),in_ticks:String(s.getInPointAsTime().ticks),out_ticks:String(s.getOutPointAsTime().ticks)};'

def export_script(baseline,clip,preset,output,sample_rate,frame_ticks):
    start,end=exact(clip['start_ticks']),exact(clip['end_ticks'])
    if type(sample_rate)is not int or sample_rate<=0 or TICKS%sample_rate:raise ValueError('Unsupported sample grid')
    if type(frame_ticks)is not int or frame_ticks<=0:raise ValueError('Exact frame tick duration required')
    if end<=start or start%frame_ticks or end%frame_ticks:raise ValueError('Frame-aligned nonempty export range required')
    sample=TICKS//sample_rate
    if start%sample or end%sample:raise ValueError('Export boundaries must be on supported audio sample grid')
    for name in ['in_ticks','out_ticks']:
        if exact(baseline[name])%sample:raise ValueError('Original marks cannot be restored on this sample grid')
    if not Path(preset).is_absolute() or not Path(output).is_absolute():raise ValueError('Absolute preset/output required')
    # Compare bounded live state in host before mutation; no stale source plan replay.
    q=json.dumps
    return identity(baseline['project'],baseline['sequence'])+SNAPSHOT+'''
var expected='''+q(baseline['state'])+''';
if(JSON.stringify(exportState(s))!==JSON.stringify(expected))throw Error('TIMELINE_CHANGED');
var oldIn=String(s.getInPointAsTime().ticks),oldOut=String(s.getOutPointAsTime().ticks);
if(oldIn!=='''+q(baseline['in_ticks'])+'''||oldOut!=='''+q(baseline['out_ticks'])+''')throw Error('MARKS_CHANGED');
if(new File('''+q(output)+''').exists)throw Error('OUTPUT_EXISTS_RECONCILE');
if(!new File('''+q(preset)+''').exists)throw Error('PRESET_MISSING');
function setExact(which,ticks){
 var seconds=Number(ticks)/254016000000;
 if(!isFinite(seconds)||seconds<0)throw Error('UNSUPPORTED_MARK');
 function set(v){if(which==='in')s.setInPoint(v);else s.setOutPoint(v);}
 function read(){return String(which==='in'?s.getInPointAsTime().ticks:s.getOutPointAsTime().ticks);}
 set(seconds);
 if(read()!==ticks)set(seconds+1/('''+str(sample_rate)+'''*256));
 if(read()!==ticks)throw Error('RANGE_SET_MISMATCH_'+which);
}
var result=null,problem=null,restoreErrors=[];
try{
 setExact('in','''+q(str(start))+''');setExact('out','''+q(str(end))+''');
 result=s.exportAsMediaDirect('''+q(output)+','+q(preset)+''',app.encoder.ENCODE_IN_TO_OUT);
}catch(e){problem=String(e);}finally{
 try{setExact('in',oldIn);}catch(e){restoreErrors.push(String(e));}
 try{setExact('out',oldOut);}catch(e){restoreErrors.push(String(e));}
}
if(restoreErrors.length)throw Error('MARK_RESTORE_FAILED '+restoreErrors.join('; ')+' original='+problem);
if(JSON.stringify(exportState(s))!==JSON.stringify(expected))throw Error('TIMELINE_CHANGED_AFTER_EXPORT');
if(problem)throw Error(problem);
return {export_result:result,path:'''+q(output)+''',start_ticks:'''+q(str(start))+''',end_ticks:'''+q(str(end))+''',expected_frames:'''+str((end-start)//frame_ticks)+''',restored_in:oldIn,restored_out:oldOut,preserved_bounded_state:true,render_qa:'required'};
'''

def verify_export(path,*,frames,width,height,fps,channels=2):
    if frames<1:raise ValueError('Positive expected frame count required')
    path=Path(path)
    cmd=['ffprobe','-v','error','-count_frames','-show_streams','-of','json',str(path)]
    data=json.loads(subprocess.check_output(cmd));video=[s for s in data['streams'] if s['codec_type']=='video'];audio=[s for s in data['streams'] if s['codec_type']=='audio']
    if len(video)!=1 or len(audio)!=1:raise ValueError('Exactly one video and audio stream required')
    v,a=video[0],audio[0]
    if (v['codec_name'],v['width'],v['height'],Fraction(v['r_frame_rate']),int(v['nb_read_frames']))!=('h264',width,height,Fraction(fps),frames):raise ValueError('Export codec/canvas/rate/frame count mismatch')
    if a['codec_name']!='aac' or a['channels']!=channels:raise ValueError('Export audio format mismatch')
    run=subprocess.run(['ffmpeg','-hide_banner','-i',str(path),'-vf','blackdetect=d=0:pix_th=0.10:pic_th=0.98','-an','-f','null','-'],capture_output=True,text=True,check=True)
    if 'black_start:' in run.stderr:raise ValueError('Black frames detected; preserve range and repair cause, never auto-trim')
    indices=sorted(set([*range(min(3,frames)),*range(max(0,frames-3),frames)]))
    select='+'.join(f'eq(n\\,{n})' for n in indices)
    raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-vf',f'select={select}','-fps_mode','passthrough','-an','-pix_fmt','gray','-f','rawvideo','-'])
    size=width*height
    if len(raw)!=size*len(indices):raise ValueError('Boundary frame decoding failed')
    fractions=[sum(p<16 for p in raw[i*size:(i+1)*size])/size for i in range(len(indices))]
    if any(f>=.98 for f in fractions):raise ValueError('Black boundary frame detected')
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return {'status':'RENDER_QA_PASS','path':str(path.resolve()),'sha256':h.hexdigest(),'frames':frames,'boundary_indices':indices,'boundary_black_fraction':fractions,'full_file_black_intervals':[], 'audio_listening':'not_performed'}

def main():
    p=argparse.ArgumentParser(description=__doc__);subs=p.add_subparsers(dest='command',required=True)
    i=subs.add_parser('inspect-script');i.add_argument('--project',required=True);i.add_argument('--sequence-uid',required=True);i.add_argument('--output',type=Path,required=True)
    b=subs.add_parser('prepare');b.add_argument('--baseline',type=Path,required=True);b.add_argument('--spec',type=Path,required=True);b.add_argument('--preset',required=True);b.add_argument('--out-dir',type=Path,required=True);b.add_argument('--sample-rate',type=int,required=True);b.add_argument('--frame-ticks',type=int,required=True)
    v=subs.add_parser('verify');v.add_argument('path');v.add_argument('--frames',type=int,required=True);v.add_argument('--width',type=int,required=True);v.add_argument('--height',type=int,required=True);v.add_argument('--fps',required=True);v.add_argument('--channels',type=int,default=2)
    args=p.parse_args()
    if args.command=='inspect-script':
        with args.output.open('x') as f:f.write(inspection_script(args.project,args.sequence_uid))
    elif args.command=='prepare':
        baseline=json.loads(args.baseline.read_text());spec=json.loads(args.spec.read_text());scripts=[]
        if not spec:raise ValueError('Empty batch')
        names=[r['name'] for r in spec]
        if len(set(names))!=len(names) or any(Path(n).name!=n or not n.endswith('.mp4') for n in names):raise ValueError('Unique final filenames required; names/dates are not inferred')
        for row in spec:
            scripts.append(export_script(baseline,row,args.preset,str((args.out_dir/row['name']).resolve()),args.sample_rate,args.frame_ticks))
        args.out_dir.mkdir(parents=True,exist_ok=False)
        for n,(row,script) in enumerate(zip(spec,scripts),1):
            (args.out_dir/f'{n:03d}.jsx').write_text(script)
        (args.out_dir/'plan.json').write_text(json.dumps({'baseline':baseline,'clips':spec,'preset':args.preset,'sample_rate':args.sample_rate,'frame_ticks':str(args.frame_ticks),'status':'PREPARED_NOT_DISPATCHED'},indent=2))
    else:print(json.dumps(verify_export(args.path,frames=args.frames,width=args.width,height=args.height,fps=args.fps,channels=args.channels),indent=2))
if __name__=='__main__':main()
