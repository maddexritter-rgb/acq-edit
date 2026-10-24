"""Pin watch-owned reference observations; never infer style or grant approval."""
import copy,math,re,subprocess,json
from pathlib import Path
from common import inside,read,save,sha,require,plan

CATEGORIES={'cuts','pacing','captions','framing','motion','graphics','color','music','sound-effects'}

def nonempty(value):return isinstance(value,str) and bool(value.strip())
def number(value):return type(value) in (int,float) and math.isfinite(value)

def file_pin(project,value,folder):
    require(isinstance(value,dict) and nonempty(value.get('path')) and isinstance(value.get('sha256'),str) and re.fullmatch(r'[a-f0-9]{64}',value['sha256']),'Reference file path/hash required')
    path=inside(Path(project['root'])/folder,value['path'])
    require(path.is_file() and sha(path)==value['sha256'],'Pinned reference file changed or missing')
    return {'path':str(path),'sha256':value['sha256']}

def validate_snapshot(project,snapshot):
    require(isinstance(snapshot,dict) and snapshot.get('schema')=='acq-edit/reference-style-v1' and snapshot.get('owner')=='watch','Unsupported reference-style snapshot')
    require(snapshot.get('projectId')==project['id'] and snapshot.get('backend')==project['backend'],'Reference-style project/backend differs')
    require(snapshot.get('humanApproved') is False and snapshot.get('coverageStatus')=='reported-by-watch-owner','Reference preparation cannot grant approval or certify viewing')
    source=file_pin(project,snapshot.get('source'),'00_SOURCE');recipe=snapshot.get('recipe')
    require(isinstance(recipe,dict) and recipe.get('sourceSha256')==source['sha256'],'Recipe describes a different reference source')
    duration=recipe.get('durationSeconds');require(number(duration) and duration>0,'Reference recipe duration must be positive and finite')
    files=snapshot.get('evidenceFiles');require(isinstance(files,list) and files,'Pinned reference inspection evidence required');ids=set()
    for evidence in files:
        require(isinstance(evidence,dict) and nonempty(evidence.get('id')) and evidence['id'] not in ids,'Unique reference evidence IDs required')
        file_pin(project,evidence,'10_WORK');ids.add(evidence['id'])
    def citations(value):require(isinstance(value,list) and value and all(isinstance(x,str) and x in ids for x in value),'Reference observation must cite pinned evidence IDs')
    def interval(value):require(isinstance(value,dict) and number(value.get('start')) and number(value.get('end')) and 0<=value['start']<value['end']<=duration,'Reference observation outside its declared duration')
    coverage=recipe.get('coverage');require(isinstance(coverage,dict) and coverage.get('fullVideoViewed') is True,'Complete reference viewing must be reported by its owner')
    require(type(snapshot.get('hasAudio')) is bool,'Reference source audio presence required')
    if snapshot['hasAudio']:require(coverage.get('audioListened') is True and coverage.get('audioAbsent') is not True,'Complete reference audio listening must be reported')
    else:require(coverage.get('audioAbsent') is True and coverage.get('audioListened') is False,'Silent reference must explicitly report absent source audio')
    citations(coverage.get('evidence'))
    require(isinstance(coverage.get('denseIntervals'),list),'Explicit dense inspection intervals required')
    for window in coverage['denseIntervals']:interval(window);citations(window.get('evidence'))
    segments=recipe.get('segments');require(isinstance(segments,list) and segments,'Timestamped style observations required');seen=set()
    for segment in segments:
        interval(segment);category=segment.get('category');require(isinstance(category,str) and category in CATEGORIES,'Unknown reference style category');seen.add(category)
        require(segment.get('basis') in ['observed','inferred'] and nonempty(segment.get('observation')),'Distinguish reference observation from inference');citations(segment.get('evidence'))
    require(seen==CATEGORIES,'Reference recipe must cover all nine style categories, including explicitly absent features')
    unsupported=recipe.get('unsupportedEffects');require(isinstance(unsupported,list) and all(nonempty(x) for x in unsupported),'Explicit unsupported-effects list required')
    origin=snapshot.get('recipeOrigin');require(isinstance(origin,dict) and nonempty(origin.get('path')) and isinstance(origin.get('sha256'),str) and re.fullmatch(r'[a-f0-9]{64}',origin['sha256']),'Original recipe provenance required')
    # The working recipe may evolve. Its frozen copy and original hash are kept;
    # do not reread or silently substitute the newer working document here.
    return snapshot

def validate(project,spec):
    contract=spec.get('referenceStyle');require(isinstance(contract,dict) and set(contract)=={'path','sha256'},'Pinned reference-style contract required')
    pinned=file_pin(project,contract,'10_WORK');return validate_snapshot(project,read(pinned['path']))

def prepare_plan(project,packet):
    spec=plan(project,packet)
    recipe_pin=file_pin(project,{'path':packet['recipe'],'sha256':packet['recipeSha256']},'10_WORK')
    source=file_pin(project,packet['source'],'00_SOURCE')
    output=inside(Path(project['root'])/'10_WORK',packet['output']);snapshot_path=inside(Path(project['root'])/'10_WORK',packet['snapshot'])
    require(output!=snapshot_path and not output.exists() and not snapshot_path.exists(),'Reference preparation outputs must be distinct new files')
    probe=json.loads(subprocess.run(['ffprobe','-v','error','-show_streams','-of','json',source['path']],check=True,capture_output=True,text=True).stdout)
    require(len([s for s in probe['streams'] if s.get('codec_type')=='video' and not s.get('disposition',{}).get('attached_pic')])==1,'One reference picture stream required')
    audio=[s for s in probe['streams'] if s.get('codec_type')=='audio'];require(len(audio)<=1,'Select an explicit reference audio mix before studying it')
    snapshot={'schema':'acq-edit/reference-style-v1','owner':'watch','projectId':project['id'],'backend':project['backend'],'source':source,'hasAudio':bool(audio),'recipeOrigin':recipe_pin,'recipe':read(recipe_pin['path']),'evidenceFiles':copy.deepcopy(packet['evidenceFiles']),'coverageStatus':'reported-by-watch-owner','humanApproved':False}
    validate_snapshot(project,snapshot)
    require(sha(recipe_pin['path'])==recipe_pin['sha256'],'Working reference recipe changed during preparation')
    save(snapshot_path,snapshot);result=copy.deepcopy(spec);result['referenceStyle']={'path':str(snapshot_path),'sha256':sha(snapshot_path)}
    save(output,result)
    return {'plan':str(output),'referenceStyle':result['referenceStyle'],'coverageStatus':snapshot['coverageStatus'],'humanApproved':False}
