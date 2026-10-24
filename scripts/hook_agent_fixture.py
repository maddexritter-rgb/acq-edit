"""Opt-in synthetic hook replacement through the actual agent and review room."""
import copy,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from common import read,save,sha,require
from hook_plan import validate,verify_native


def prepare(seed,directory,font):
    spec=read(seed);work=Path(seed).parent;require(Path(font).is_file(),'Supply an installed fixture font')
    transcript=work/'hook-fixture-transcript.txt'
    with transcript.open('x') as out:out.write('Keep the meaning. Make clean cuts.\nSynthetic copy fixture, not a speech transcript.\n')
    save(work/'hook-recipe-seed.json',{'schema':'text-hook/v1','clip_id':spec['clipId'],'source':'FILL_FROM_NATIVE_BASE_RENDER','source_sha256':'FILL_FROM_NATIVE_BASE_RENDER','transcript':str(transcript),'transcript_sha256':sha(transcript),'transcript_revision':'synthetic-fixture','selected_text':'Keep the meaning','display_lines':['Keep the meaning'],'font_path':str(Path(font).resolve()),'existing_hook':'none','delivery_platform':'custom','caption_bottom_px':305,'safe_rect':[38,24,564,310],'protected_rects':[],'geometry_evidence':'Frozen synthetic caption region; inspect actual rendered base before preparation.','supporting_passages':[{'quote':'Keep the meaning. Make clean cuts.','location':'Synthetic copy fixture'}],'placement_intervals':[{'start_seconds':0,'end_seconds':5.04,'caption_bounds':[120,270,400,35],'protected_rects':[],'evidence':'Synthetic lower caption region'}]})
    save(Path(directory)/'revision-request.json',{'notes':'Replace the existing opening text hook with Make clean cuts, on one line, and change only the body caption wording to UPDATED BODY CAPTION. Preserve every cut, source/audio range, caption timing/style/position, framing, music and other graphics. Follow NATIVE_HOOKS.md: inspect the current native parent; remove only the owned hook on a new checkpoint with a pinned previous plan; revise the body caption through caption-clips; render the hook-free intermediate; inspect its current layout and prepare a fresh text-hook recipe from that actual render/receipt; add the replacement native hook and render again. Keep the same font, safe region, protected caption region and five-second inclusive hook boundary from the original recipe. Publish ONLY the final replacement against this submitted V1. Do not reuse a stale hookContract or publish intermediates. This is the same explicit synthetic fixture with ACQ_EDIT_TEST_FIXTURE=1; no real speech, transcription, new editorial design or brain fetch is claimed.','comment':'Keep source cuts and caption timing unchanged; replace the headline and body caption wording only.','lateComment':'Added while the hook replacement is running: retain this for the next submission, bound to the original version.'})


def compare_plans(first,second,seed):
    originals=[copy.deepcopy(first),copy.deepcopy(second)]
    for spec in originals:require(spec.pop('hookContract',None),'Published hook contract absent')
    require(originals[0]==seed,'Initial hook build changed the frozen base plan')
    require(originals[1]['captions'][0]['text']=='UPDATED BODY CAPTION','Requested body caption absent')
    originals[1]['captions'][0]['text']=seed['captions'][0]['text']
    require(originals[1]==seed,'Hook revision changed protected plan data')
    require(first['hookContract']['sha256']!=second['hookContract']['sha256'] and first['hookContract']['baseReceiptSha256']!=second['hookContract']['baseReceiptSha256'],'Replacement reused stale hook geometry or base receipt')


def protected_native(first,second):
    require(first['view']['active_sequence']==second['view']['active_sequence'],'Revision changed active sequence')
    key=str(first['view']['active_sequence']);a=copy.deepcopy(first['project']['items'][key]['kind']['Sequence']);b=copy.deepcopy(second['project']['items'][key]['kind']['Sequence'])
    a['video_tracks'].pop();b['video_tracks'].pop()
    changed=0
    for track in b['video_tracks']:
        for item in track['items']:
            for effect in item['effects']:
                if effect['effect']=='graphic_text' and effect['params']['text']['value']=={'Text':'UPDATED BODY CAPTION'}:
                    effect['params']['text']['value']={'Text':'NATIVE AGENT LOOP'};changed+=1
    require(changed==1,'Native caption replacement coverage differs')
    require(a==b,'Hook replacement changed protected native tracks')
    for item_id,item in first['project']['items'].items():
        if item_id!=key:require(second['project']['items'].get(item_id)==item,'Existing native bin asset changed')


def protected_regions(old,new):
    """Remeasure caption ink, but retain every original protected region."""
    def contains(outer,inner):
        x,y,w,h=outer;u,v,a,b=inner
        return x<=u and y<=v and x+w>=u+a and y+h>=v+b
    require(len(old['placement_intervals'])==len(new['placement_intervals'])==1,'Fixture placement interval coverage changed')
    before=old['placement_intervals'][0];after=new['placement_intervals'][0]
    require((before['start_seconds'],before['end_seconds'])==(after['start_seconds'],after['end_seconds']),'Fixture placement clocks changed')
    required=old['protected_rects']+before['protected_rects']+[before['caption_bounds']]
    preserved=new['protected_rects']+after['protected_rects']+[after['caption_bounds']]
    require(all(any(contains(region,original) for region in preserved) for original in required),'Original protected caption/subject region was lost')


def check(fixture,versions):
    f=read(fixture);plans=[read(v['planPath']) for v in versions];compare_plans(*plans,read(f['planPath']));prepared=[]
    for index,(spec,version) in enumerate(zip(plans,versions)):
        require(sha(version['nativeProject'])==version['nativeFingerprint'],'Original working native checkpoint changed')
        contract=validate(f['project'],spec);prepared.append(contract);m=contract['recipe']
        text=['Keep the meaning','Make clean cuts'][index]
        require(m['selected_text']==text and m['display_lines']==[text],'Published hook copy differs')
        require(contract['intervals'][-1]['endFrame']==126,'Hook cutoff differs')
        receipt=read(spec['hookContract']['baseReceipt']);require(receipt['jobId']==version['jobId'],'Hook was prepared from another job')
        if f['project']['backend']=='filmcraft':verify_native(read(version['nativeCheckpoint']),spec,contract,254016000000//25)
    old,new=prepared[0]['recipe'],prepared[1]['recipe']
    for key in ['font_path','safe_rect','transcript','transcript_sha256']:
        require(old[key]==new[key],'Protected hook recipe field changed: '+key)
    protected_regions(old,new)
    if f['project']['backend']=='filmcraft':
        protected_native(*[read(v['nativeCheckpoint']) for v in versions]);native='requested native hook and caption; protected native tracks preserved'
    else:native='pinned native render receipts and recipes; full Fusion appearance requires separate inspection'
    return {'nativeGraph':native,'freshHookContext':True,'hookEndFrameExclusive':126,'originalWorkingCheckpointsPreserved':True,'humanApproved':False}


if __name__=='__main__':
    if sys.argv[1]=='prepare':prepare(*sys.argv[2:])
    elif sys.argv[1]=='check':print(json.dumps(check(sys.argv[2],json.loads(sys.argv[3]))))
    else:raise SystemExit('Expected prepare or check')
