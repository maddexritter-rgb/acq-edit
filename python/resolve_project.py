"""Read native project state before a first timeline exists; never switch hosts."""
from common import require,fingerprint


def inspect_without_timeline(project):
    require(project.GetTimelineCount()==0 and not project.GetCurrentTimeline(),
            'Native timelines exist but none is selected; select the intended timeline before inspection')
    seen=set()
    def folder_state(folder,depth=0):
        require(folder and depth<32,'Cannot inspect native media pool folder hierarchy')
        identity=folder.GetUniqueId()
        require(identity and identity not in seen,'Native media pool folder identity is repeated')
        seen.add(identity)
        return {'id':identity,'name':folder.GetName(),'stale':folder.GetIsFolderStale(),
                'clips':[{'id':clip.GetUniqueId(),'name':clip.GetName(),'properties':clip.GetClipProperty()} for clip in folder.GetClipList() or []],
                'folders':[folder_state(child,depth+1) for child in folder.GetSubFolderList() or []]}
    state={'kind':'resolve-project-without-timelines','project':project.GetName(),
           'projectId':project.GetUniqueId(),'timeline':None,'timelineCount':0,
           'settings':project.GetSettings(),'mediaPool':folder_state(project.GetMediaPool().GetRootFolder()),
           'rendering':project.IsRenderingInProgress(),'renderJobs':project.GetRenderJobList()}
    require(project.GetTimelineCount()==0 and not project.GetCurrentTimeline(),
            'Native timeline state changed during project inspection; inspect again')
    return state


def inspection_result(resolve,project,state):
    digest=fingerprint(state)
    return {'state':state,'fingerprint':digest,'version':resolve.GetVersionString(),
            'reopen':{'nativeProjectId':project.GetUniqueId(),
                      'database':resolve.GetProjectManager().GetCurrentDatabase(),
                      'timelineId':state['timeline'],'expectedFingerprint':digest}}


def empty_workspace(resolve):
    """Identify Resolve's empty startup/close placeholder without authorizing a switch."""
    pm=resolve.GetProjectManager();p=pm.GetCurrentProject()
    if not p or p.GetName()!='Untitled Project' or p.GetTimelineCount()!=0:return None
    state=inspect_without_timeline(p)
    if state['rendering'] or state['renderJobs'] or state['mediaPool']['clips'] or state['mediaPool']['folders']:return None
    return {'nativeProjectId':p.GetUniqueId(),'database':pm.GetCurrentDatabase(),
            'fingerprint':fingerprint(state)}


def reopen(resolve,project,packet,snapshot):
    """Select an inspected native version, never import/rebuild or close another project."""
    import re
    require(isinstance(packet.get('nativeProjectId'),str) and packet['nativeProjectId'],
            'Reopen requires the native project identity from a prior inspection')
    require(isinstance(packet.get('database'),dict) and packet['database'],
            'Reopen requires the native database identity from a prior inspection')
    require('timelineId' in packet and (packet['timelineId'] is None or
            isinstance(packet['timelineId'],str) and packet['timelineId']),
            'Reopen requires the inspected timeline identity or explicit null')
    require(isinstance(packet.get('expectedFingerprint'),str) and
            re.fullmatch('[0-9a-f]{64}',packet['expectedFingerprint']),
            'Reopen requires the prior inspected fingerprint')
    pm=resolve.GetProjectManager();name='ACQ_'+project['id']
    require(pm.GetCurrentDatabase()==packet['database'],
            'Resolve database changed; select the original database before reopening')
    current=pm.GetCurrentProject()
    if current and current.GetName()!=name:
        observed=empty_workspace(resolve)
        require(observed and packet.get('emptyWorkspace')==observed,
                'Another Resolve project is open; preserve and close it, or explicitly pin the empty workspace from doctor')
        current=None
    loaded=current or pm.LoadProject(name)
    require(loaded and loaded.GetName()==name,'Saved native project unavailable; no replacement was created')
    def verify_host():
        live=pm.GetCurrentProject()
        require(live and live.GetName()==name and live.GetUniqueId()==packet['nativeProjectId'] and
                loaded.GetUniqueId()==packet['nativeProjectId'] and pm.GetCurrentDatabase()==packet['database'],
                'Native project or database identity differs; preserve state and reconcile')
        require(not loaded.IsRenderingInProgress(),'Native render is active; wait before selecting a timeline')
    verify_host()
    target=None
    if packet['timelineId'] is None:
        state=inspect_without_timeline(loaded)
    else:
        matches=[t for i in range(1,loaded.GetTimelineCount()+1)
                 if (t:=loaded.GetTimelineByIndex(i)) and t.GetUniqueId()==packet['timelineId']]
        require(len(matches)==1,'Saved native timeline unavailable or ambiguous; no replacement was created')
        target=matches[0]
    verify_host()
    previous=loaded.GetCurrentTimeline();previous_state=None;switched=False
    if target:
        require(previous,'No current timeline to preserve; select a timeline explicitly before reopening')
        if previous.GetUniqueId()!=target.GetUniqueId():previous_state=snapshot(loaded)
    try:
        if target:
            if previous_state is not None:
                # Inactive timelines return incomplete native track/audio state.
                # Select for inspection; never normalize those missing values away.
                verify_host();active=loaded.GetCurrentTimeline()
                require(active and active.GetUniqueId()==previous.GetUniqueId(),
                        'Timeline selection changed concurrently; preserve it and reconcile')
                switched=True
                require(loaded.SetCurrentTimeline(target),'Native timeline selection failed; inspect before retrying')
            active=loaded.GetCurrentTimeline()
            require(active and active.GetUniqueId()==packet['timelineId'],'Native timeline selection readback differs')
            state=snapshot(loaded)
        else:state=inspect_without_timeline(loaded)
        verify_host()
        require(fingerprint(state)==packet['expectedFingerprint'],
                'Native state changed since inspection; preserve user edits and reconcile')
    except Exception:
        if switched:
            verify_host();active=loaded.GetCurrentTimeline()
            require(active and active.GetUniqueId() in [target.GetUniqueId(),previous.GetUniqueId()],
                    'Timeline selection changed concurrently; preserve it and reconcile')
            if active.GetUniqueId()==target.GetUniqueId():
                require(loaded.SetCurrentTimeline(previous),'Could not restore prior selection; reconcile')
            require(loaded.GetCurrentTimeline().GetUniqueId()==previous.GetUniqueId() and
                    fingerprint(snapshot(loaded))==fingerprint(previous_state),
                    'Previous timeline differs after selection restoration; preserve and reconcile')
        raise
    return inspection_result(resolve,loaded,state)
