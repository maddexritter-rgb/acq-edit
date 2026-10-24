"""Revise only verified caption-clips Merge visibility on a new Resolve timeline."""
import tempfile
from pathlib import Path
from common import require,fingerprint
from resolve_captions import card_nodes
from fusion_state import canonical_fusion,field,remove_field


def changes(timeline,previous,current,prepared):
    require(not timeline.GetIsTrackLocked('video',1),'Caption picture track is locked; preserve manual state')
    items=timeline.GetItemListInTrack('video',1)
    require(len(items)==len(current['cuts']),'Caption picture coverage changed')
    result=[]
    for index,(item,cut) in enumerate(zip(items,current['cuts'])):
        if not any(c['start_frame']<cut['recordFrame']+cut['frames'] and c['end_frame']>cut['recordFrame'] for c in prepared['cards']):continue
        comp=item.GetFusionCompByIndex(1);require(comp,'Owned caption comp absent')
        start=comp.GetAttrs()['COMPN_RenderStart']
        old,new=(card_nodes(spec,prepared,cut,start) for spec in [previous,current])
        require(len(old)==len(new),'Visibility cannot change caption node coverage')
        for a,b in zip(old,new):
            require(a['mergeName']==b['mergeName'],'Caption target identity changed')
            if a['blend']!=b['blend']:
                tool=comp.FindTool(a['mergeName'])
                require(tool and tool.Blend.GetExpression()==a['blend'],'Caption visibility changed before revision')
                result.append({'itemIndex':index,'node':a['mergeName'],'before':a['blend'],'after':b['blend']})
    require(result,'Hidden ranges do not affect any owned captions')
    return result


def apply(timeline,targets):
    items=timeline.GetItemListInTrack('video',1)
    for row in targets:
        tool=items[row['itemIndex']].GetFusionCompByIndex(1).FindTool(row['node'])
        require(tool and tool.Blend.GetExpression()==row['before'],'Caption visibility target changed')
        tool.Blend.SetExpression(row['after'])
        require(tool.Blend.GetExpression()==row['after'],'Native caption visibility expression readback differs')


def protected_graph(text,names):
    graph=canonical_fusion(text);tools=field(graph['composition'],'Tools')
    for name in names:
        tool=field(tools,name);require(tool and tool.get('constructor')=='Merge','Caption visibility node is not a Merge')
        slot=field(field(tool,'Inputs'),'Blend');expression=field(slot,'Expression')
        require(slot and slot.get('constructor')=='Input' and expression and expression.get('tag')=='string','Owned caption visibility expression absent')
        # Exact old/new expressions are verified separately. Keep every other
        # graph field and connection, including unexpected Blend modifiers.
        remove_field(slot,'Expression')
    return fingerprint(graph)


def protected_snapshot(adapter,project,targets):
    from resolve_graphics import inspect
    detail=inspect(adapter,project);items=project.GetCurrentTimeline().GetItemListInTrack('video',1)
    grouped={}
    for row in targets:grouped.setdefault(row['itemIndex'],[]).append(row['node'])
    with tempfile.TemporaryDirectory(prefix='caption-visibility-inspect-',dir=adapter.project_root/'10_WORK') as folder:
        for index,names in grouped.items():
            item=items[index];require(item.GetFusionCompCount()==1,'Owned caption composition count changed')
            path=Path(folder)/f'{index}.comp';require(item.ExportFusionComp(str(path),1),'Cannot inspect protected caption graph')
            detail['state']['tracks']['video'][0][index]['fusion']=[protected_graph(path.read_text(encoding='utf-8'),names)]
    return fingerprint(detail)
