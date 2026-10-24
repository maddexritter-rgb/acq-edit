"""Compare owner-supplied panel revisions without changing source selections."""
import copy
from common import inside, require, sha, plan, fingerprint


def compare_plans(previous, current, targets):
    require(isinstance(targets, list) and targets, 'Select panel revision targets')
    chosen = {}
    for target in targets:
        require(isinstance(target, dict) and set(target)=={'cutId','panelIds'}, 'Exact cut and panel IDs required')
        cut_id, ids = target['cutId'], target['panelIds']
        require(isinstance(cut_id,str) and cut_id and cut_id not in chosen, 'Select each cut once')
        require(isinstance(ids,list) and ids and all(isinstance(i,str) and i for i in ids) and len(set(ids))==len(ids), 'Select unique panel IDs')
        chosen[cut_id] = ids
    require({k:v for k,v in previous.items() if k!='framing'}=={k:v for k,v in current.items() if k!='framing'}, 'Panel revision preserves cuts, sources, captions, audio, graphics and all other plan fields')
    old, new = previous.get('framing',{}), current.get('framing',{})
    require(old.get('schema')==new.get('schema')=='acq-edit/framing-v1', 'Both plans require framing handoffs')
    require(old['receiptSha256']!=new['receiptSha256'], 'Panel revision needs a fresh framing-owner receipt')
    require(set(old['shots'])==set(new['shots']) and set(chosen)<=set(old['shots']), 'Panel revision cut coverage changed')
    for cut_id, before in old['shots'].items():
        after = new['shots'][cut_id]
        if cut_id not in chosen:
            require(before==after, 'Unselected framing changed'); continue
        require(before['mode']==after['mode']=='panel-layout', 'Panel revision requires an existing native panel layout')
        require([p['id'] for p in before['panels']]==[p['id'] for p in after['panels']], 'Panel identities/order/count are preserved; adding or replacing cameras requires another operation')
        require(set(chosen[cut_id])<={p['id'] for p in before['panels']}, 'Unknown panel target')
        layout_changed = False
        for a,b in zip(before['panels'], after['panels']):
            if a['id'] not in chosen[cut_id]:
                require(a==b, 'Unselected panel changed'); continue
            require(a['sourceRange']==b['sourceRange'], 'Panel revision cannot alter camera identity, sync or source range')
            require(a['crop']['mode']==b['crop']['mode'], 'Changing fixed/tracked modes requires another native operation')
            immutable = lambda crop:{k:v for k,v in crop.items() if k not in ['x','y','width','height','xByFrame']}
            require(immutable(a['crop'])==immutable(b['crop']), 'Panel source geometry and tracking binding must remain unchanged')
            require(a['crop']!=b['crop'] or a['rect']!=b['rect'], 'Selected panel has no change')
            layout_changed |= a['rect']!=b['rect']
        if layout_changed:
            require(before['cameraReceiptSha256']!=after['cameraReceiptSha256'], 'Layout changes require a fresh Assembly Design camera receipt')
        else:
            require(all(before[k]==after[k] for k in ['cameraReceiptPath','cameraReceiptSha256']), 'Crop-only revision preserves the Assembly Design camera receipt')
    return chosen


def prepare(project, packet):
    path = inside(project['root'], packet['previousPlan'])
    require(sha(path)==packet['previousPlanSha256'], 'Previous published plan changed')
    previous, current = plan(project, {'plan':str(path)}), plan(project,packet)
    return previous, current, compare_plans(previous,current,packet['targets'])


def resolve_changes(spec, before, after, ids):
    from framing_plan import fusion_crop
    from resolve_framing import track_positions
    from resolve_panels import prefix, merge_name, center
    fields, curves = {}, {}
    for index,(a,b) in enumerate(zip(before['panels'],after['panels'])):
        if a['id'] not in ids: continue
        def changed(name, old, new):
            values={k:v for k,v in new.items() if old[k]!=v}
            if values: fields[name]=values
        changed(prefix(index)+'Crop',fusion_crop(spec,a['crop']),fusion_crop(spec,b['crop']))
        changed(prefix(index)+'Resize',{'Width':a['rect']['width'],'Height':a['rect']['height']},{'Width':b['rect']['width'],'Height':b['rect']['height']})
        changed(merge_name(index,len(after['panels'])),{'Center':center(spec,a['rect'])},{'Center':center(spec,b['rect'])})
        if b['crop']['mode']=='tracked-crop' and track_positions(a['crop'])!=track_positions(b['crop']):
            curves[prefix(index)+'PathX']=track_positions(b['crop'])
    return fields,curves


def protected_fusion(text, fields, curves):
    """Remove only approved value slots; retain graph links, expressions and flags."""
    from fusion_state import canonical_fusion, field, remove_field
    graph=canonical_fusion(text);tools=field(graph['composition'],'Tools')
    for name,values in fields.items():
        tool=field(tools,name);require(tool,'Panel revision node missing')
        for key in values:
            slot=field(field(tool,'Inputs'),key)
            require(slot and slot.get('constructor')=='Input' and field(slot,'Value') is not None and field(slot,'Expression') is None and field(slot,'SourceOp') is None, 'Panel revision value is absent or driven')
            remove_field(slot,'Value')
    for name in curves:
        tool=field(tools,name)
        require(tool and tool.get('constructor')=='BezierSpline' and field(tool,'KeyFrames') is not None, 'Owned panel tracking spline missing')
        remove_field(tool,'KeyFrames')
    return fingerprint(graph)


def duplicate_snapshot(state, graphs):
    """Compare native copies, allowing only new identities and Resolve cache paths.

    This is not the saved-state fingerprint: same-timeline fingerprints continue
    to include every identity and cache path. All exported graphs are required.
    """
    from fusion_state import canonical_fusion, field, remove_field
    value=copy.deepcopy(state);value.pop('timeline');value.pop('name')
    identities={item['id']:f'{kind}:{track}:{index}' for kind,tracks in value['tracks'].items() for track,items in enumerate(tracks) for index,item in enumerate(items)}
    used=set()
    for kind,tracks in value['tracks'].items():
        for track,items in enumerate(tracks):
            for index,item in enumerate(items):
                require(all(i in identities for i in item['linkedIds']), 'Unexpected external clip link in duplicated timeline')
                item['id']=identities[item['id']];item['linkedIds']=sorted(identities[i] for i in item['linkedIds'])
                for comp in range(len(item['fusion'])):
                    key=(kind,track,index,comp);require(key in graphs, 'Complete duplicate Fusion graph coverage required');used.add(key)
                    graph=canonical_fusion(graphs[key]);prefs=field(graph['composition'],'Prefs');paths=field(field(field(prefs,'Comp'),'Paths'),'Map');cache=field(paths,'ResolveCaches:')
                    if cache is not None:
                        require(cache.get('tag')=='string' and cache['value'].endswith('/Fusion'), 'Unknown Resolve cache metadata')
                        remove_field(paths,'ResolveCaches:')
                    item['fusion'][comp]=fingerprint(graph)
    require(used==set(graphs), 'Unexpected duplicate Fusion graph')
    return fingerprint(value)
