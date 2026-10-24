"""Verify source clocks directly before native rendering or finishing revisions.

An exported Fusion graph and a cached preview alone do not prove the live
MediaIn covers the planned picture. Never repair an unexplained shift in place.
"""
from pathlib import Path
from common import require

CLOCK_KEYS=('GlobalIn','GlobalOut','ClipTimeStart','ClipTimeEnd')


def pin_new_copy(original,duplicate,spec=None):
    """Persist already-correct static clocks on a new native timeline copy.

    Resolve 21.1.1 can omit zero-valued Timeline MediaIn controls when saving a
    duplicate, then reopen GlobalIn one frame late. Explicitly storing the same
    values prevents this. Never use this to repair an existing shifted timeline.
    Validate every source before writing any input; MediaPool panels are owned
    by their separate mapping contract.
    """
    require(original.GetUniqueId()!=duplicate.GetUniqueId(),'Source clocks may only be pinned on a new timeline copy')
    if spec:verify_timeline(original,spec);verify_timeline(duplicate,spec)
    pending=[]
    for timeline in (original,duplicate):
        clocks=[]
        for item in timeline.GetItemListInTrack('video',1) or []:
            for index in range(1,item.GetFusionCompCount()+1):
                comp=item.GetFusionCompByIndex(index);clocks.append(read_clocks(comp));attrs=comp.GetAttrs()
                for tool in comp.GetToolList(False).values():
                    if tool.GetAttrs()['TOOLS_RegID']!='MediaIn' or tool.GetInput('MediaSource')!='Timeline':continue
                    expected=dict(zip(CLOCK_KEYS,[attrs['COMPN_GlobalStart'],attrs['COMPN_GlobalEnd'],attrs['COMPN_GlobalStart'],attrs['COMPN_GlobalEnd']]))
                    for key,value in expected.items():
                        require(tool.GetInput(key)==value,'Cannot pin an unexplained Timeline MediaIn source clock: '+key)
                        port=getattr(tool,key)
                        require(not port.GetExpression() and not port.GetConnectedOutput(),'Cannot pin a driven Timeline MediaIn clock')
                    if timeline is duplicate:pending.append((tool,expected))
        if timeline is original:baseline=clocks
        else:require(clocks==baseline,'Native duplication changed source clocks; reconcile before pinning')
    for tool,values in pending:
        for key,value in values.items():
            # The native Python bridge may return None even on success.
            # Readback, not its return value, establishes the stored value.
            tool.SetInput(key,value)
            require(tool.GetInput(key)==value,'Copied Timeline MediaIn clock changed during persistence: '+key)
    observed=[read_clocks(item.GetFusionCompByIndex(i)) for item in duplicate.GetItemListInTrack('video',1) or [] for i in range(1,item.GetFusionCompCount()+1)]
    require(observed==baseline,'Persisting copied source clocks changed native timing')


def read_clocks(comp):
    """Materialize native source controls before exporting a standalone graph.

    Resolve's exported Loader representation is not the live MediaIn object.
    Read both sides of export; inspection must never alter a source clock.
    """
    attrs=comp.GetAttrs()
    clocks={'composition':{k:attrs[k] for k in ['COMPN_GlobalStart','COMPN_GlobalEnd','COMPN_RenderStart','COMPN_RenderEnd']},'sources':{}}
    for tool in comp.GetToolList(False).values():
        native=tool.GetAttrs()
        if native['TOOLS_RegID']!='MediaIn':continue
        clocks['sources'][native['TOOLS_Name']]={key:tool.GetInput(key) for key in ['MediaSource','MediaID','GlobalIn','GlobalOut','ClipTimeStart','ClipTimeEnd']}
    return clocks


def verify_timeline(timeline,spec):
    items=timeline.GetItemListInTrack('video',1) or []
    require(len(items)==len(spec['cuts']),'Native source cut coverage differs')
    for item,cut in zip(items,spec['cuts']):
        require((item.GetStart(True),item.GetLeftOffset(True),item.GetDuration(True))==(cut['recordFrame'],cut['sourceInFrame'],cut['frames']),'Native source picture timing differs')
        source=next(s for s in spec['sources'] if s['id']==cut['sourceId']);media=item.GetMediaPoolItem()
        require(media and Path(media.GetClipProperty('File Path')).resolve()==Path(source['path']).resolve(),'Native source picture binding differs')
        for index in range(1,item.GetFusionCompCount()+1):
            comp=item.GetFusionCompByIndex(index);attrs=comp.GetAttrs()
            for tool in comp.GetToolList(False).values():
                if tool.GetAttrs()['TOOLS_RegID']!='MediaIn' or tool.GetInput('MediaSource')!='Timeline':continue
                # Timeline MediaIn spans the source's native clip-local domain.
                # Panel Media Pool inputs have an explicit, separately verified
                # source/global mapping in resolve_panels and are not reset here.
                expected={'GlobalIn':attrs['COMPN_GlobalStart'],'ClipTimeStart':attrs['COMPN_GlobalStart'],
                          'GlobalOut':attrs['COMPN_GlobalEnd'],'ClipTimeEnd':attrs['COMPN_GlobalEnd']}
                for key,value in expected.items():
                    require(tool.GetInput(key)==value,'Native Timeline MediaIn source clock differs: '+key+'; preserve the timeline and reconcile before export')
                    port=getattr(tool,key)
                    require(not port.GetExpression() and not port.GetConnectedOutput(),'Native Timeline MediaIn clock is driven; reconcile before export')
                require(expected['GlobalIn']<=attrs['COMPN_RenderStart']<=attrs['COMPN_RenderEnd']<=expected['GlobalOut'],'Native Timeline MediaIn does not cover its composition render range')
