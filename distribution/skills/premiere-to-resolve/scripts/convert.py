#!/usr/bin/env python3
"""Create a new native Resolve project from prepared XML; verify and export DRP."""
import argparse, copy, json, pathlib, xml.etree.ElementTree as ET
from fractions import Fraction
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from prepare import sha, motion, validate_manifest
from audit_prproj import AUDIT_SCHEMA

def near(a,b):
    if isinstance(a,dict) and isinstance(b,dict):return a.keys()==b.keys() and all(near(a[k],b[k]) for k in a)
    if isinstance(a,(list,tuple)) and isinstance(b,(list,tuple)):return len(a)==len(b) and all(near(x,y) for x,y in zip(a,b))
    if isinstance(a,(int,float)) and isinstance(b,(int,float)):return abs(a-b)<0.0001
    return a==b

def snapshot(project,manifest,resolve,work,export_xml=True):
    validate_manifest(manifest)
    errors=[];rows=[]
    timelines={project.GetTimelineByIndex(i).GetName():project.GetTimelineByIndex(i) for i in range(1,project.GetTimelineCount()+1)}
    if len(timelines)!=project.GetTimelineCount() or set(timelines)!=set(s['name'] for s in manifest['sequences']):errors.append('Timeline inventory differs')
    for expected in manifest['sequences']:
        name=expected['name'];t=timelines.get(name)
        if not t:continue
        assert project.SetCurrentTimeline(t)
        start=t.GetStartFrame();row={'name':name,'start':start,'end':t.GetEndFrame(),'settings':t.GetSetting(),'markers':t.GetMarkers(),'tracks':{},'track_settings':{}}
        for key,want in [('timelineResolutionWidth',expected['width']),('timelineResolutionHeight',expected['height'])]:
            if int(t.GetSetting(key))!=want:errors.append(f'{name}: {key}')
        if abs(float(t.GetSetting('timelineFrameRate'))-float(Fraction(expected['rate'])))>.0001:errors.append(name+': frame rate')
        if t.GetEndFrame()-start!=expected['duration']:errors.append(name+': duration')
        if str(t.GetSetting('useCustomSettings')).lower() not in ('1','true'):errors.append(name+': custom timeline settings disabled')
        if t.GetSetting('timelineInputResMismatchBehavior')!='centerCrop':errors.append(name+': input scaling')
        actual_markers=t.GetMarkers() or {}
        if len(actual_markers)!=len(expected['markers']):errors.append(name+': marker count')
        for m in expected['markers']:
            a=actual_markers.get(m['frame'])
            if not a or a.get('name')!=m['name'] or (a.get('note') or '')!=m['note']:errors.append(name+': marker '+str(m['frame']))
        for kind,tracks in expected['tracks'].items():
            row['tracks'][kind]=[]
            row['track_settings'][kind]=[]
            if t.GetTrackCount(kind)<len(tracks):errors.append(f'{name}: missing {kind} tracks')
            for j,clips in enumerate(tracks,1):
                meta=expected['track_settings'][kind][j-1]
                actual_meta={'enabled':t.GetIsTrackEnabled(kind,j),'name':t.GetTrackName(kind,j)}
                row['track_settings'][kind].append(actual_meta)
                if actual_meta['enabled']!=meta['enabled']:errors.append(f'{name}: {kind}{j} track enabled state')
                if meta['name'] is not None and actual_meta['name']!=meta['name']:errors.append(f'{name}: {kind}{j} track name')
                items=t.GetItemListInTrack(kind,j) or [];track=[];row['tracks'][kind].append(track)
                if len(items)!=len(clips):errors.append(f'{name}: {kind}{j} count');continue
                for index,(c,e) in enumerate(zip(items,clips)):
                    media=c.GetMediaPoolItem();linked=c.GetLinkedItems() or []
                    a={'name':c.GetName(),'start':c.GetStart(True)-start,'end':c.GetEnd(True)-start,'in':c.GetLeftOffset(True),'path':media.GetClipProperty('File Path') if media else None,'online':media.GetClipProperty('Online Status') if media else None,'enabled':c.GetClipEnabled(),'properties':c.GetProperty(),'links':[{'name':l.GetName(),'start':l.GetStart(True)-start,'end':l.GetEnd(True)-start} for l in linked]};track.append(a)
                    for key in ('name','start','end','in','path','enabled'):
                        if not near(a[key],e[key]):errors.append(f'{name}: {kind}{j}[{index}] {key}: {a[key]} != {e[key]}')
                    if a['online']!='Online':errors.append(f'{name}: offline {kind}{j}[{index}]')
                    wanted_links=set(e['links'])-{e['id']}
                    if len(linked)!=len(wanted_links):errors.append(f'{name}: {kind}{j}[{index}] link count')
            for j in range(len(tracks)+1,t.GetTrackCount(kind)+1):
                if t.GetItemListInTrack(kind,j):errors.append(f'{name}: unexpected populated {kind}{j}')
        if export_xml:
            dest=work/(expected['xml']+'.readback.xml')
            assert t.Export(str(dest),resolve.EXPORT_FCP_7_XML,0), 'Resolve XML readback failed'
            seq=ET.parse(dest).find('.//sequence')
            for kind,tracks in expected['tracks'].items():
                for j,clips in enumerate(tracks):
                    rt=seq.findall('media/'+kind+'/track')
                    if j>=len(rt) and clips:errors.append(name+': missing XML track');continue
                    if j>=len(rt):continue
                    items=rt[j].findall('clipitem')
                    if len(items)!=len(clips):errors.append(name+': XML clip count');continue
                    for n,(c,e) in enumerate(zip(items,clips)):
                        for key in ('start','end','in','out'):
                            if int(c.findtext(key))!=e[key]:errors.append(f'{name}: XML {kind}{j+1}[{n}] {key}')
                        # Compare transported motion and audio gain, including source-clock keyframes.
                        got=motion(c)
                        for effect,params in e['effects'].items():
                            for param,val in params.items():
                                if effect=='basic' and param in ('antiflicker','leftcrop','topcrop','rightcrop','bottomcrop') and not val['keys'] and val['value']==0:continue
                                if not near(got.get(effect,{}).get(param),val):errors.append(f'{name}: XML {kind}{j+1}[{n}] {effect}.{param}')
        rows.append(row)
    return {'passed':not errors,'errors':errors,'timelines':rows,'limits':['XML agreement is not pixel or listening proof','Premiere export may quantize subframe audio; inspect original native timing before accepting sample-precise assemblies','Human acceptance remains pending']}

def require(value, message):
    if not value:
        raise RuntimeError(message)


def apply_track_settings(project, timeline, expected):
    """Restore independent track flags and labels with the timeline active."""
    require(project.SetCurrentTimeline(timeline), 'Cannot activate imported timeline')
    changes = []
    for kind, settings in expected['track_settings'].items():
        require(timeline.GetTrackCount(kind) >= len(settings), 'Imported track inventory differs')
        for index, meta in enumerate(settings, 1):
            before = {'enabled': timeline.GetIsTrackEnabled(kind, index),
                      'name': timeline.GetTrackName(kind, index)}
            if before['enabled'] != meta['enabled']:
                require(timeline.SetTrackEnable(kind, index, meta['enabled']), 'Could not preserve track enabled state')
            if meta['name'] is not None and before['name'] != meta['name']:
                require(timeline.SetTrackName(kind, index, meta['name']), 'Could not preserve track name')
            require(timeline.GetIsTrackEnabled(kind, index) == meta['enabled'], 'Track visibility readback failed')
            require(meta['name'] is None or timeline.GetTrackName(kind, index) == meta['name'], 'Track name readback failed')
            if before['enabled'] != meta['enabled'] or (meta['name'] is not None and before['name'] != meta['name']):
                changes.append({'kind': kind, 'index': index, 'before': before, 'target': meta})
    return changes


def bind_native_audit(manifest, manifest_path, native):
    """A v1 timing-only receipt cannot authorize v2 track-state conversion."""
    validate_manifest(manifest)
    require(native.get('schema') == AUDIT_SCHEMA and native.get('passed') is True,
            'Passing v2 native audit required; re-run audit_prproj.py')
    require(native.get('manifest_sha256') == sha(manifest_path), 'Native audit is stale for this manifest')
    require(native.get('auditor_sha256') == sha(pathlib.Path(__file__).with_name('audit_prproj.py')),
            'Auditor changed; regenerate native audit')
    require(sha(native['project_path']) == native['project_sha256'], 'Premiere input changed')
    result = copy.deepcopy(manifest)
    for seq in result['sequences']:
        meta = native['track_settings'][seq['name']]
        for kind, settings in seq['track_settings'].items():
            require(len(settings) == len(meta[kind]), 'Native track inventory differs')
            for index, item in enumerate(settings):
                authoritative = meta[kind][index]
                require(item['enabled'] == authoritative['enabled'], 'Native/XML visibility disagreement')
                require(item['name'] is None or item['name'] == authoritative['name'], 'Native/XML track name disagreement')
                item['name'] = authoritative['name']
    return result


def validate_inputs(manifest_path, audit_path, output, work):
    require(not output.exists(), 'Output already exists; choose a new path')
    require(not work.exists(), 'Work directory already exists; inspect its checkpoint before retrying')
    original = json.loads(manifest_path.read_text())
    native = json.loads(audit_path.read_text())
    manifest = bind_native_audit(original, manifest_path, native)
    require(not manifest['warnings'], 'Unverified effects require a separate conversion plan')
    require(sha(manifest['source_xml']) == manifest['source_sha256'], 'Source XML changed after preparation')
    for seq in manifest['sequences']:
        require(sha(manifest_path.parent / seq['xml']) == seq['sha256'], 'Prepared XML changed')
    for path, info in manifest['media'].items():
        require(pathlib.Path(path).is_file() and pathlib.Path(path).stat().st_size == info['bytes'],
                'Media missing or changed: ' + path)
    return manifest


def run(manifest_path, audit_path, project_name, expected_current_project, output, work):
    """One guarded production run. No retries, global preference changes or cleanup."""
    manifest_path, audit_path, output, work = map(lambda p: pathlib.Path(p).resolve(),
                                                 (manifest_path, audit_path, output, work))
    m = validate_inputs(manifest_path, audit_path, output, work)
    import DaVinciResolveScript as d
    r = d.scriptapp('Resolve')
    require(r, 'Resolve scripting unavailable; start Resolve with local scripting')
    pm = r.GetProjectManager()
    prior = pm.GetCurrentProject()
    require(prior and prior.GetName() == expected_current_project, 'Current project changed')
    require(prior.GetName() != 'Untitled Project', 'Save/name the current Resolve project before running; avoid a blocking Save dialog')
    check_name = project_name + '__REOPEN_CHECK'
    existing = pm.GetProjectListInCurrentFolder() or []
    if isinstance(existing, dict):
        existing = list(existing.values())
    require(project_name not in existing and check_name not in existing, 'Conversion or reopen project exists; inspect the prior run')
    work.mkdir(parents=True, exist_ok=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    state = {'project': project_name, 'previous_project': prior.GetName(), 'resolve_version': r.GetVersionString(),
             'manifest': str(manifest_path), 'manifest_sha256': sha(manifest_path), 'native_audit': str(audit_path),
             'phase': 'saving_previous', 'imported': [], 'track_adjustments': {}}
    def record():
        temp = work / 'state.json.tmp'
        temp.write_text(json.dumps(state, indent=2))
        temp.replace(work / 'state.json')
    try:
        record()
        require(pm.SaveProject(), 'Could not save previous project')
        require(pm.GetCurrentProject().GetName() == expected_current_project, 'Project changed before creation')
        state['phase'] = 'creating'; record()
        p = pm.CreateProject(project_name)
        require(p, 'CreateProject failed')
        first = m['sequences'][0]
        for key, value in [('timelineFrameRate', str(float(Fraction(first['rate'])))),
                           ('timelineResolutionWidth', str(first['width'])),
                           ('timelineResolutionHeight', str(first['height'])),
                           ('timelineInputResMismatchBehavior', 'centerCrop')]:
            require(p.SetSetting(key, value), 'Project setting failed: ' + key)
        pool = p.GetMediaPool()
        folders = {(): pool.GetRootFolder()}
        for seq in m['sequences']:
            require(pm.GetCurrentProject().GetName() == project_name, 'Project changed during conversion')
            state.update(phase='importing', pending_sequence=seq['name']); record()
            path = ()
            for binname in seq['bins']:
                new = path + (binname,)
                if new not in folders:
                    folders[new] = pool.AddSubFolder(folders[path], binname)
                    require(folders[new], 'Bin creation failed')
                path = new
            require(pool.SetCurrentFolder(folders[path]), 'Cannot select destination bin')
            t = pool.ImportTimelineFromFile(str(manifest_path.parent / seq['xml']),
                                            {'importSourceClips': True, 'timelineName': seq['name']})
            require(t, 'Import failed; inspect this project and checkpoint before retrying')
            require(p.SetCurrentTimeline(t), 'Cannot select imported timeline')
            for key, value in [('useCustomSettings', '1'),
                               ('timelineResolutionWidth', str(seq['width'])),
                               ('timelineResolutionHeight', str(seq['height'])),
                               ('timelineInputResMismatchBehavior', 'centerCrop')]:
                require(t.SetSetting(key, value), 'Timeline setting failed: ' + key)
            state['track_adjustments'][seq['name']] = apply_track_settings(p, t, seq)
            for kind, tracks in seq['tracks'].items():
                for j, clips in enumerate(tracks, 1):
                    items = t.GetItemListInTrack(kind, j) or []
                    require(len(items) == len(clips), 'Imported item count differs')
                    for item, expected in zip(items, clips):
                        require(item.SetName(expected['name']), 'Could not preserve clip name')
                        # Do not repair clip flags or framing silently: snapshot must prove import fidelity.
            require(pm.SaveProject(), 'Save failed')
            state['imported'].append(seq['name']); state['pending_sequence'] = None; record()
            print('Imported ' + seq['name'], flush=True)
        state['phase'] = 'verifying'; record()
        report = snapshot(p, m, r, work)
        (work / 'verification.json').write_text(json.dumps(report, indent=2))
        require(report['passed'], json.dumps(report['errors'][:20]))
        require(p.SetCurrentTimeline(p.GetTimelineByIndex(1)), 'Cannot select first timeline')
        p.GetCurrentTimeline().SetCurrentTimecode(p.GetCurrentTimeline().GetStartTimecode())
        require(pm.SaveProject(), 'Save failed')
        state['phase'] = 'exporting'; record()
        require(pm.ExportProject(project_name, str(output), True), 'DRP export failed')
        require(output.is_file() and output.stat().st_size > 0, 'DRP missing or empty')
        state.update(phase='exported', drp=str(output), drp_sha256=sha(output)); record()
        require(check_name not in (pm.GetProjectListInCurrentFolder() or []), 'Reopen project name became occupied')
        state['phase'] = 'reopening'; record()
        require(pm.ImportProject(str(output), check_name), 'DRP import failed')
        p2 = pm.LoadProject(check_name)
        require(p2, 'Reopen project failed')
        reopen_work = work / 'reopen_xml'; reopen_work.mkdir()
        reopened = snapshot(p2, m, r, reopen_work)
        (work / 'reopened.json').write_text(json.dumps(reopened, indent=2))
        require(reopened['passed'], json.dumps(reopened['errors'][:20]))
        p = pm.LoadProject(project_name)
        require(p, 'Could not restore conversion project')
        require(p.SetCurrentTimeline(p.GetTimelineByIndex(1)), 'Cannot select first timeline')
        p.GetCurrentTimeline().SetCurrentTimecode(p.GetCurrentTimeline().GetStartTimecode())
        r.OpenPage('edit')
        require(pm.SaveProject(), 'Final save failed')
        state.update(phase='ready_for_human_review', reopened_project=check_name); record()
        result = {'output': str(output), 'timelines': len(m['sequences']), 'state': state['phase']}
        print(json.dumps(result))
        return result
    except Exception as exc:
        state.update(failed_phase=state['phase'], phase='failed', error=str(exc))
        record()
        raise


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('manifest'); ap.add_argument('--native-audit', required=True)
    ap.add_argument('--project-name', required=True); ap.add_argument('--expected-current-project', required=True)
    ap.add_argument('--output', required=True); ap.add_argument('--work', required=True)
    a = ap.parse_args()
    run(a.manifest, a.native_audit, a.project_name, a.expected_current_project, a.output, a.work)


if __name__ == '__main__':
    main()
