"""Read native project state before a first timeline exists; never switch hosts."""
from common import require


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
