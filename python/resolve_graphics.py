"""Native take replacement on an inspected duplicate, preserving other layers."""
import copy
import tempfile
from pathlib import Path
from common import require,fingerprint,sha
from panel_revision import duplicate_snapshot


def items(timeline,spec,targets=()):
    result=[]
    for index,asset in enumerate(spec.get('graphics',[])):
        clips=timeline.GetItemListInTrack('video',index+2) or []
        require(len(clips)==1,'Native graphic track coverage changed')
        item=clips[0];media=item.GetMediaPoolItem()
        require(media and Path(media.GetClipProperty('File Path')).resolve()==Path(asset['path']).resolve(),'Native graphic source differs from pinned plan')
        require((item.GetStart(True),item.GetDuration(True),item.GetLeftOffset(True))==(asset['startFrame'],asset['frames'],0),'Native graphic placement changed')
        if index in targets:
            require(not timeline.GetIsTrackLocked('video',index+2) and not item.GetLinkedItems(),'Graphic target is locked or linked')
            require(item.GetTakesCount()==0 and item.GetSelectedTakeIndex()==0,'Existing take selectors require separate reconciliation')
            require(item.GetFusionCompCount()==0,'Graphic replacement with a Fusion composition requires a dedicated source-binding revision')
            require(item.GetSourceStartFrame()==0 and item.GetSourceEndFrame()==asset['frames']-1,'Retimed graphic source extent differs from placement')
        result.append(item)
    return result


def inspect(adapter,p,duplicate=False,source_slots=(),omit_last_video_track=False):
    state=adapter.snapshot(p);timeline=p.GetCurrentTimeline();extra={};graphs={}
    if omit_last_video_track:
        require(len(state['tracks']['video'])>1,'Cannot omit the only picture track')
        state['tracks']['video'].pop();state['trackState']['video'].pop()
    with tempfile.TemporaryDirectory(prefix='graphic-inspect-',dir=adapter.project_root/'10_WORK') as folder:
        for kind,tracks in state['tracks'].items():
            for track,clips in enumerate(tracks):
                native=timeline.GetItemListInTrack(kind,track+1) or []
                require(len(native)==len(clips),'Timeline changed during graphic inspection')
                for index,(saved,item) in enumerate(zip(clips,native)):
                    extra[f'{kind}:{track}:{index}']={'markers':item.GetMarkers(),'flags':sorted(item.GetFlagList()),'color':item.GetClipColor(),'takes':item.GetTakesCount(),'selectedTake':item.GetSelectedTakeIndex(),'sourceStart':item.GetSourceStartFrame(),'sourceEnd':item.GetSourceEndFrame(),'version':item.GetCurrentVersion()}
                    if duplicate:
                        for comp in range(len(saved['fusion'])):
                            path=Path(folder)/f'{kind}-{track}-{index}-{comp}.comp'
                            require(item.ExportFusionComp(str(path),comp+1),'Cannot inspect duplicate Fusion graph')
                            graphs[(kind,track,index,comp)]=path.read_text(encoding='utf-8')
    for kind,track,index in source_slots:
        item=state['tracks'][kind][track][index]
        item['source']=item['sourcePath']='<verified replacement source>'
    return {'state':duplicate_snapshot(state,graphs) if duplicate else state,'extra':extra}


def protected(state,indices):
    result=copy.deepcopy(state)
    for index in indices:
        clips=result['state']['tracks']['video'][index+1]
        require(len(clips)==1,'Graphic target coverage changed')
        for key in ['source','sourcePath']:clips[0].pop(key)
    return fingerprint(result)


def replace(item,media,asset):
    require(sha(asset['path'])==asset['sha256'],'Replacement graphic changed')
    name,color,flags=item.GetName(),item.GetClipColor(),item.GetFlagList()
    require(not media.GetFlagList(),'New replacement media unexpectedly has flags')
    # Resolve 21.1.1 takes use inclusive source end frames and require Edit page.
    require(item.AddTake(media,0,asset['frames']-1),'Native take creation failed; retain the duplicate for reconciliation')
    require(item.GetTakesCount()==2,'Unexpected native take count')
    take=item.GetTakeByIndex(2)
    require(take and take['mediaPoolItem'].GetUniqueId()==media.GetUniqueId() and take['startFrame']==0 and take['endFrame']==asset['frames']-1,'Native take binding or extent differs')
    require(item.SelectTakeByIndex(2) and item.GetSelectedTakeIndex()==2,'Cannot select replacement take')
    require(item.FinalizeTake() and item.GetTakesCount()==0 and item.GetSelectedTakeIndex()==0,'Cannot finalize native take replacement')
    require(item.SetName(name),'Cannot restore graphic clip name')
    require(item.SetClipColor(color) if color else item.ClearClipColor(),'Cannot restore graphic clip color')
    for flag in flags:require(item.AddFlag(flag),'Cannot restore graphic flag')
    require(sorted(item.GetFlagList())==sorted(flags),'Graphic flags differ after replacement')
    require(item.GetMediaPoolItem().GetUniqueId()==media.GetUniqueId(),'Replacement did not retain selected source')


def fresh_media(pool,spec,indices):
    """Flags belong to media: never rewrite metadata on an already-used asset."""
    wanted=[str(Path(spec['graphics'][i]['path']).resolve()) for i in indices]
    fresh_paths(pool,wanted)


def fresh_paths(pool,paths):
    wanted=[str(Path(path).resolve()) for path in paths]
    require(len(wanted)==len(set(wanted)),'Resolve replacements require a distinct new media path per target')
    pending=[pool.GetRootFolder()];known=set()
    while pending:
        folder=pending.pop();require(folder,'Cannot inspect Media Pool folders')
        for media in folder.GetClipList() or []:
            path=media.GetClipProperty('File Path')
            if path:known.add(str(Path(path).resolve()))
        pending.extend(folder.GetSubFolderList() or [])
    require(not set(wanted)&known,'Replacement media is already registered; use a fresh asset copy to preserve other clips and metadata')
