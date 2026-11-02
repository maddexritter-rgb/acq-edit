"""Native-only completion: read the reopened project; never export or open a room."""
import importlib.util
import math
import os
import sys
from fractions import Fraction
from common import SKILLS, inside, plan, read, require, sha, save
from premiere_plan import verify_source_cuts


def owner(name, relative):
    folder=SKILLS/relative
    sys.path.insert(0,str(folder.parent))
    spec=importlib.util.spec_from_file_location(name,folder)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def close(actual,expected):
    if isinstance(expected,list):return isinstance(actual,list) and len(actual)==len(expected) and all(close(a,b) for a,b in zip(actual,expected))
    return type(actual) in (int,float) and type(expected) in (int,float) and math.isfinite(actual) and abs(actual-expected)<=1e-7

def verify_motion(spec,motion,inspection,owner_module):
    require((inspection['project_path'],inspection['sequence_id'])==(motion['project_path'],motion['sequence_id']),'Framing belongs to another sequence')
    require((inspection['width'],inspection['height'])==(spec['width'],spec['height']),'Framing canvas differs')
    # Panel cuts are checked against their entire nested native graph below.
    # They must not be verified as a second full-screen animation on V1.
    direct_cuts=[c for c in spec['cuts'] if spec['framing']['shots'][c['id']]['mode']!='panel-layout']
    records=motion['records'];require(len(records)==len(direct_cuts),'Direct framing coverage differs from non-panel cuts')
    fps=spec['fps']['numerator']/spec['fps']['denominator']
    for record,cut in zip(records,direct_cuts):
        shot=spec['framing']['shots'][cut['id']]
        require(shot['mode']=='tracked-crop','Unsupported native framing mode; preserve and reconcile')
        expected=[[f/fps,(x+shot['width']/2)/shot['sourceWidth'],(shot['y']+shot['height']/2)/shot['sourceHeight']] for f,x in enumerate(shot['xByFrame'])]
        require(len(expected)==cut['frames'] and close(record['anchor_keys'],expected) and close(record['position'],[.5,.5]) and close(record['scale_percent'],1920/shot['height']*100),'Framing owner curve differs from frozen plan')
    items=owner_module.fresh_operation(motion,'completion-readback')['arguments']['items'] if records else []
    rows=[c for t in inspection['video_tracks'] for c in t['clips']]
    for item in items:
        matching=[r for r in rows if r['node_id']==item['node_id']];require(len(matching)==1,'Missing framing item')
        row=matching[0];require(all(row[k]==item[k] for k in ('source_id','media_path','start_ticks','end_ticks','source_in_ticks','source_out_ticks')),'Framing source/timing differs')
        m=row['motion'];keys=m['anchor_keys']
        require(row['speed']==1 and row.get('speed_reversed') is False and m['anchor_time_varying'] and not m['position_time_varying'] and not m['scale_time_varying'],'Framing playback or animation changed')
        require(len(keys)==len(item['keys']) and all(a['ticks']==b['ticks'] and close(a['value'],b['value']) for a,b in zip(keys,item['keys'])) and close(m['position'],item['position']) and close(m['scale'],item['scale']),'Native framing keys differ')
    return {'items':len(items),'keys':sum(len(i['keys']) for i in items),'verification':'exact-frozen-curves-and-live-native-keys','interpolation':'not-read-back'}

def verify_audio_item(plan,inspection,audio_owner):
    operation=plan['operation'];args=operation['arguments'];target=operation['target']
    require((inspection['project_path'],inspection['sequence_id'])==(target['project_path'],target['sequence_id']),'Audio target differs')
    rows=[c for t in inspection['audio_tracks'] for c in t['clips'] if c['node_id']==args['node_id']]
    require(len(rows)==1,'Missing independent native audio item');row=rows[0]
    require(all(row[k]==args[k] for k in audio_owner.ITEM_FIELDS) and row['speed']==1 and row.get('speed_reversed') is False,'Audio source or clocks differ')
    level=row['level'];require(level and level['time_varying'] is True and {k:level[k] for k in audio_owner.PARAMETER_FIELDS}==args['parameter'],'Audio parameter differs')
    require(len(level['keys'])==len(args['keys']) and all(a['ticks']==b['ticks'] and close(a['value'],b['value']) for a,b in zip(level['keys'],args['keys'])),'Audio envelope differs')
    return {'nodeId':args['node_id'],'verification':'exact-native-envelope','listening':'not-run'}


def verify_dialogue_effect_item(spec,plan,inspection,state):
    """Prove native chain and unanimated unity Level against explicit cut intent."""
    require(plan.get('schema')=='acq-edit/premiere-dialogue-item-v1','Explicit native dialogue plan required')
    require((plan['projectPath'],plan['sequenceId'])==(inspection['project_path'],inspection['sequence_id']),'Dialogue effect target differs')
    cuts=[c for c in spec['cuts'] if c['id']==plan['cutId']];require(len(cuts)==1,'Unknown dialogue cut')
    cut=cuts[0];source=next(s for s in spec['sources'] if s['id']==cut.get('audioSourceId',cut['sourceId']))
    rows=[c for t in inspection['audio_tracks'] for c in t['clips'] if c['node_id']==plan['nodeId']];require(len(rows)==1,'Missing dialogue item')
    row=rows[0];tick=254016000000//spec['sampleRate']
    require(row['media_path']==source['path'] and row['speed']==1 and row['speed_reversed'] is False and (int(row['start_ticks']),int(row['end_ticks'])-int(row['start_ticks']),int(row['source_offset_ticks'])+int(row['source_in_ticks']))==(cut['audioRecordSample']*tick,cut['audioSamples']*tick,cut['audioInSample']*tick),'Dialogue source clocks differ')
    level=row['level'];require(level and not level['keys'] and close(level['value'],0.1778279410038923) and spec['audio'].get('gainDb',0)==0,'Dialogue Level differs from native unity')
    native=[c for t in state['tracks'] if t['kind']==1 for c in t['clips'] if c['id']==plan['nodeId']];require(len(native)==1,'Dialogue effect item ambiguous')
    expected=spec['audio']['dialogueEffects']['cuts'][cut['id']]
    actual=native[0]['components'];require(len(actual)==1+len(expected) and actual[0]['matchName'] in ['Internal Volume Mono','Internal Volume Stereo','audioVolume'],'Unexpected dialogue effect chain')
    for want,got in zip(expected,actual[1:]):
        require(want['name']==got['name'] and want['matchName']==got['matchName'] and len(want['properties'])==len(got['properties']),'Dialogue effect identity changed')
        for a,b in zip(want['properties'],got['properties']):
            same=type(a['value']) is bool and a['value'] is b.get('value') or type(a['value']) is not bool and close(b.get('value'),a['value'])
            require(a['name']==b['name'] and not b.get('keys') and not b.get('valueUnavailable') and same,'Dialogue effect parameter changed')
    return {'nodeId':plan['nodeId'],'verification':'source-linked-native-dialogue-effects','renderedMix':'separate-evidence','listening':'not-run'}


def complete(adapter, project, packet, client_type):
    require(os.environ.get('ACQ_EDIT_JOB_ID'),'Native editable completion requires an active toolkit job')
    spec=plan(project,packet);native=inside(project['root'],packet['nativeProject'])
    native_hash=sha(native);before=adapter.inspect(project,packet)
    require(before['fingerprint']==packet['expectedFingerprint'],'Intervening native edits; preserve and reconcile')
    artifacts=[]
    def artifact(key):
        entry=packet[key];file=inside(project['root'],entry['path'])
        require(sha(file)==entry['sha256'],key+' evidence changed')
        artifacts.append({'path':str(file),'sha256':entry['sha256']})
        return file,read(file)
    _,reopened=artifact('reopenResult')
    require(reopened.get('status')=='inspected_native_session' and reopened.get('mode')=='open',
            'A real saved-project reopen is required; an already-open inspection is insufficient')
    require(reopened['inspection']==before,'Reopen evidence is stale; verify the current saved timeline')
    lifecycle=inside(project['root'],reopened['receipt']);life=read(lifecycle)
    require(life.get('status')=='committed_unverified' and life.get('projectId')==project['id']
            and life.get('request',{}).get('mode')=='open' and life['request'].get('projectPath')==str(native)
            and life.get('nativeSha256')==native_hash,'Saved-project lifecycle evidence differs')
    artifacts.append({'path':str(lifecycle),'sha256':sha(lifecycle)})
    state=before['state'];sequence=state['sequenceId']
    caption_file,captions=artifact('captionBuild')
    caption_owner=owner('completion_captions','caption-clips/scripts/premiere_native_cards.py')
    caption_check=caption_owner.verify(native,caption_file)
    require(captions['sequence_uid']==sequence,'Editable captions belong to another sequence')
    ticks=Fraction(254016000000*spec['fps']['denominator'],spec['fps']['numerator'])
    require(ticks.denominator==1,'Unsupported noninteger native frame ticks')
    settings=state['settings']
    require(settings['videoFrameWidth']==spec['width'] and settings['videoFrameHeight']==spec['height'] and int(settings['videoFrameRate']['ticks'])==int(ticks),'Native sequence settings differ')
    require(Fraction(254016000000,int(settings['audioSampleRate']['ticks']))==spec['sampleRate'],'Native sample rate differs')
    actual=[(int(c['timing']['start_ticks']),int(c['timing']['end_ticks']),''.join(r['text'] for r in c['expected_runs'])) for c in captions['cards']]
    wanted=[(c['startFrame']*int(ticks),c['endFrame']*int(ticks),c['text']) for c in spec['captions']]
    require(actual==wanted,'Saved caption text/timing differs from the source-linked plan')
    client=client_type(adapter.profile)
    try:
        links=client.inspect('inspect_assembly_links',{'project_path':str(native),'sequence_id':sequence,'paged':True,'primary_av_only':True})
        links=links.get('data',links);cuts=verify_source_cuts(spec,state,links)
        _,motion=artifact('motionPlan')
        reframe=owner('completion_reframe','horizontal-to-vertical/scripts/premiere_reframe_bridge.py')
        require(motion.get('sharedPlanSha256')==sha(inside(project['root'],packet['plan'])),'Framing plan is not bound to this final source plan')
        framing=verify_motion(spec,motion,reframe.inspect_active(client),reframe)
        panel_cuts=[cut for cut in spec['cuts'] if spec['framing']['shots'][cut['id']]['mode']=='panel-layout']
        panel_entries=motion.get('panelSplits',[])
        require(len(panel_entries)==len(panel_cuts) and len({e['cutId'] for e in panel_entries})==len(panel_entries),'Panel construction evidence incomplete or duplicated')
        if panel_cuts:
            from premiere_panels import verify as verify_panel
            native_project=client.inspect('inspect_project_sequences',{'project_path':str(native)})['data']
            panel_checks=[]
            for cut in panel_cuts:
                entries=[e for e in panel_entries if e['cutId']==cut['id']];require(len(entries)==1,'Missing camera split evidence');entry=entries[0];panel_links={}
                for panel in entry['result']['panels']:
                    sid=panel['sequence_id'];observed=client.inspect('inspect_camera_panel_sources',{'project_path':str(native),'sequence_id':sid});panel_links[sid]=observed.get('data',observed)
                panel_checks.append(verify_panel(spec,cut,entry,native_project,panel_links))
            framing['panels']=panel_checks
        # Audio owner plans retain exact clip identity, calibrated values and keys.
        # Unsupported processing must stop here rather than be silently omitted.
        require(isinstance(packet.get('audioPlans'),list) and packet['audioPlans'],'Native dialogue/music owner plans required')
        audio_owner=owner('completion_audio','music/scripts/apply_native_music.py');audio=[]
        audio_inspection=audio_owner.inspect(client)
        require(packet.get('audioSharedPlanSha256')==sha(inside(project['root'],packet['plan'])),'Audio evidence must bind the frozen plan')
        for i,entry in enumerate(packet['audioPlans']):
            key='audioPlan'+str(i);packet={**packet,key:entry};_,audio_plan=artifact(key)
            audio.append(verify_dialogue_effect_item(spec,audio_plan,audio_inspection,state) if audio_plan.get('schema')=='acq-edit/premiere-dialogue-item-v1' else verify_audio_item(audio_plan,audio_inspection,audio_owner))
        expected_ids=[c['node_id'] for t in audio_inspection['audio_tracks'] for c in t['clips']]
        require(sorted(x['nodeId'] for x in audio)==sorted(expected_ids) and len(set(expected_ids))==len(expected_ids),'Every native dialogue/music item needs exactly one owner plan')
        after=adapter.inspect(project,packet)
        require(after==before and sha(native)==native_hash,'Native state changed during completion inspection')
    finally:client.close()
    inspection=inside(project['root'],packet['inspection']);receipt=inside(project['root'],packet['receipt'])
    require(inspection!=receipt and not inspection.exists() and not receipt.exists(),'Completion evidence already exists; reconcile instead of overwriting')
    save(inspection,{'schema':'acq-edit/editable-inspection-v1','nativeState':before,'cuts':cuts,'captions':caption_check,'framing':framing,'audio':audio,'sourceLinks':links,'approval':'not-human-reviewed'})
    artifacts.extend([{'path':str(native),'sha256':native_hash},{'path':str(inspection),'sha256':sha(inspection)}, {'path':str(inside(project['root'],packet['plan'])),'sha256':sha(inside(project['root'],packet['plan']))}])
    for source in spec['sources']:
        file=inside(project['root'],source['path']);require(sha(file)==source['sha256'],'Source media changed during native completion')
        artifacts.append({'path':str(file),'sha256':source['sha256']})
    require(read(inside(project['root'],packet['plan']))==spec,'Plan changed during completion')
    result={'schema':'acq-edit/editable-project-v1','projectId':project['id'],'jobId':os.environ['ACQ_EDIT_JOB_ID'],'clipId':spec['clipId'],'nativeProject':str(native),'sequenceId':sequence,'nativeFingerprint':before['fingerprint'],'planPath':str(inside(project['root'],packet['plan'])),'inspectionPath':str(inspection),'artifacts':artifacts,'humanApproval':False}
    save(receipt,result)
    return {**result,'receiptPath':str(receipt),'receiptSha256':sha(receipt)}
