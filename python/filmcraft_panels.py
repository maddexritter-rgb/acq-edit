"""Native, independent panel nests. Original dialogue remains on the master."""
import copy
from common import require, fingerprint
from panel_layout import panel_spec


def construct(c, spec, sources, frame_ticks):
    from framing_plan import filmcraft_motion, filmcraft_tracking
    master = c.tool('sequence_inspect')['id']
    layouts = {}
    settings = {'fps': spec['fps']['numerator']/spec['fps']['denominator'], 'sampleRate': spec['sampleRate'], 'audio': 0}
    for cut in spec['cuts']:
        layout = spec.get('framing', {}).get('shots', {}).get(cut['id'], {})
        if layout.get('mode') != 'panel-layout': continue
        panel_ids = []
        for panel in layout['panels']:
            p = panel_spec(spec, cut, panel); child_cut = p['cuts'][0]
            sequence = c.run('file.newSequence', {**settings, 'name': 'ACQ_Panel_'+cut['id']+'_'+panel['id'], 'width': p['width'], 'height': p['height'], 'video': 1})['sequence']
            c.run('timeline.place', {'item': sources[child_cut['sourceId']], 'track': 'V1', 'video': True, 'audio': False,
                                    'time': 0, 'sourceIn': child_cut['sourceInFrame']*frame_ticks, 'duration': cut['frames']*frame_ticks, 'insert': False})
            items = c.tool('sequence_inspect')['video'][0]['items']; require(len(items) == 1, 'Panel source placement failed')
            for key, value in filmcraft_motion(p, panel['crop']).items():
                c.run('effects.setParam', {'clip': items[0]['clip'], 'effect': 'motion', 'param': key, 'value': value})
            filmcraft_tracking(c, items[0], child_cut, panel['crop'], frame_ticks)
            panel_ids.append(sequence)
        container = c.run('file.newSequence', {**settings, 'name': 'ACQ_Layout_'+cut['id'], 'width': spec['width'], 'height': spec['height'], 'video': len(panel_ids)})['sequence']
        c.run('sequence.nestSequences', {'on': True})
        for index, (panel, sequence) in enumerate(zip(layout['panels'], panel_ids)):
            c.run('timeline.place', {'item': sequence, 'track': f'V{index+1}', 'video': True, 'audio': False,
                                    'time': 0, 'sourceIn': 0, 'duration': cut['frames']*frame_ticks, 'insert': False})
            items = c.tool('sequence_inspect')['video'][index]['items']; require(len(items) == 1 and items[0]['item'] == sequence, 'Panel must remain a native nest')
            r = panel['rect']
            for key, value in {'anchor': [r['width']/2, r['height']/2], 'position': [r['x']+r['width']/2, r['y']+r['height']/2], 'scale': 100}.items():
                c.run('effects.setParam', {'clip': items[0]['clip'], 'effect': 'motion', 'param': key, 'value': value})
        layouts[cut['id']] = container
    c.run('sequence.open', {'item': master})
    return layouts


def bind(data, spec, layouts, frame_ticks):
    """Bind generated video-only nests without a delete command touching linked audio.

    Only new construction uses this typed project operation. Native reopen/readback
    is mandatory; revisions must not reconstruct a user's existing composition.
    """
    seq = data['project']['items'][str(data['view']['active_sequence'])]['kind']['Sequence']
    require(len(seq['video_tracks'][0]['items']) == len(spec['cuts']), 'Panel binding picture coverage differs')
    for cut, item in zip(spec['cuts'], seq['video_tracks'][0]['items']):
        if cut['id'] not in layouts: continue
        require((item['start'], item['source_in'], item['duration']) == (cut['recordFrame']*frame_ticks, cut['sourceInFrame']*frame_ticks, cut['frames']*frame_ticks), 'Stale panel parent range')
        item['item'] = layouts[cut['id']]; item['source_in'] = 0; item['name'] = 'ACQ_Layout_'+cut['id']
        motion = next(e['params'] for e in item['effects'] if e['effect'] == 'motion')
        for key, value in {'anchor': {'Vec2': {'x': spec['width']/2, 'y': spec['height']/2}},
                           'position': {'Vec2': {'x': spec['width']/2, 'y': spec['height']/2}}, 'scale': {'Float': 100}}.items():
            require(not motion[key].get('keyframes'), 'New panel parent unexpectedly animated')
            motion[key]['value'] = value


def verify(data, spec, cut, parent, frame_ticks):
    from framing_plan import verify_filmcraft_framing_data
    items = data['project']['items']; layout = spec['framing']['shots'][cut['id']]
    def sequence(item_id, width, height, tracks):
        seq = items[str(item_id)]['kind'].get('Sequence'); require(seq, 'Panel nest replaced with flattened media')
        s = seq['settings']
        require((s['width'], s['height'], s['frame_rate']) == (width, height, {'num': spec['fps']['numerator'], 'den': spec['fps']['denominator']}), 'Panel sequence geometry changed')
        require(s['sample_rate'] == spec['sampleRate'] and s['par'] == [1, 1], 'Panel sample rate or pixel aspect changed')
        require(len(seq['video_tracks']) == tracks and not seq['audio_tracks'], 'Panel track or audio coverage changed')
        require(not seq.get('caption_tracks') and all(t['enabled'] and not t.get('transitions') and not t.get('effects') and not t.get('muted') and not t.get('solo') for t in seq['video_tracks']), 'Panel track state changed')
        return seq
    def effects(item):
        require([e['effect'] for e in item['effects']] == ['motion', 'opacity', 'time_remap'] and all(e['enabled'] and not e.get('masks') for e in item['effects']), 'Panel effect stack changed')
        expected = {'motion': {'anti_flicker': {'Float': 0}, 'rotation': {'Float': 0}, 'scale_width': {'Float': 100}, 'uniform_scale': {'Bool': True}},
                    'opacity': {'blend': {'Choice': 0}, 'opacity': {'Float': 100}}, 'time_remap': {'speed': {'Float': 100}}}
        for effect in item['effects']:
            for key, value in expected[effect['effect']].items():
                field = effect['params'][key]
                require(field['value'] == value and not field.get('keyframes'), 'Panel rotation, opacity or time-remap changed')
    def placement(item, start, source_in, width, height, position):
        effects(item)
        require(item['enabled'] and item['speed'] == 1 and not item['reverse'], 'Panel visibility or speed changed')
        require((item['start'], item['source_in'], item['duration']) == (start, source_in, cut['frames']*frame_ticks), 'Panel clocks changed')
        m = next(e['params'] for e in item['effects'] if e['effect'] == 'motion')
        for key, value in {'anchor': {'Vec2': {'x': width/2, 'y': height/2}}, 'position': {'Vec2': dict(zip(['x', 'y'], position))}, 'scale': {'Float': 100}}.items():
            require(m[key]['value'] == value and not m[key].get('keyframes'), 'Panel parent transform changed')
    placement(parent, cut['recordFrame']*frame_ticks, 0, spec['width'], spec['height'], [spec['width']/2, spec['height']/2])
    container = sequence(parent['item'], spec['width'], spec['height'], len(layout['panels']))
    for panel, track in zip(layout['panels'], container['video_tracks']):
        require(len(track['items']) == 1, 'Panel occurrence coverage changed')
        nest = track['items'][0]; r = panel['rect']
        placement(nest, 0, 0, r['width'], r['height'], [r['x']+r['width']/2, r['y']+r['height']/2])
        child = sequence(nest['item'], r['width'], r['height'], 1)
        require(len(child['video_tracks'][0]['items']) == 1, 'Panel camera coverage changed')
        picture = child['video_tracks'][0]['items'][0]
        effects(picture)
        require(picture['enabled'] and picture['speed'] == 1 and not picture['reverse'], 'Panel camera speed or visibility changed')
        verify_filmcraft_framing_data(data, panel_spec(spec, cut, panel), frame_ticks, nest['item'])


def revision_operations(data, previous, current, targets):
    from framing_plan import filmcraft_motion
    items=data['project']['items'];master=items[str(data['view']['active_sequence'])]['kind']['Sequence']
    operations=[]
    for cut,parent in zip(previous['cuts'],master['video_tracks'][0]['items']):
        if cut['id'] not in targets:continue
        old=previous['framing']['shots'][cut['id']];new=current['framing']['shots'][cut['id']]
        container=items[str(parent['item'])]['kind']['Sequence']
        for index,(a,b) in enumerate(zip(old['panels'],new['panels'])):
            if a['id'] not in targets[cut['id']]:continue
            nest=container['video_tracks'][index]['items'][0];child=items[str(nest['item'])]['kind']['Sequence'];camera=child['video_tracks'][0]['items'][0]
            changed=lambda old,new:{key:value for key,value in new.items() if old[key]!=value}
            placement=lambda panel:{'anchor':[panel['rect']['width']/2,panel['rect']['height']/2], 'position':[panel['rect']['x']+panel['rect']['width']/2,panel['rect']['y']+panel['rect']['height']/2]}
            camera_motion=changed(filmcraft_motion(panel_spec(previous,cut,a),a['crop']),filmcraft_motion(panel_spec(current,cut,b),b['crop']))
            anchors=lambda panel:[[x+panel['crop']['width']/2,panel['crop']['y']+panel['crop']['height']/2] for x in panel['crop'].get('xByFrame',[])]
            operations.append({'container':parent['item'],'child':nest['item'],'nestClip':nest['id'],'cameraClip':camera['id'],
                'settings':changed({k:a['rect'][k] for k in ['width','height']},{k:b['rect'][k] for k in ['width','height']}),
                'nestMotion':changed(placement(a),placement(b)),'cameraMotion':camera_motion,
                'trackingChanged':b['crop']['mode']=='tracked-crop' and anchors(a)!=anchors(b),
                'panel':b,'cut':cut})
    require(operations,'No native panel targets')
    return operations


def protected_revision(data, operations, destination_name=None):
    value=copy.deepcopy(data['project'])
    if destination_name is not None:value['name']=destination_name;value['root']['name']=destination_name
    def motion(sequence_id,clip_id):
        seq=value['items'][str(sequence_id)]['kind']['Sequence']
        item=next((item for track in seq['video_tracks'] for item in track['items'] if item['id']==clip_id),None)
        require(item,'Native panel revision target missing')
        return next(effect['params'] for effect in item['effects'] if effect['effect']=='motion')
    for op in operations:
        settings=value['items'][str(op['child'])]['kind']['Sequence']['settings']
        for key in op['settings']:settings.pop(key)
        for target,clip,fields in [('container','nestClip','nestMotion'),('child','cameraClip','cameraMotion')]:
            params=motion(op[target],op[clip])
            for key in op[fields]:params[key].pop('value')
        if op['trackingChanged']:motion(op['child'],op['cameraClip'])['anchor'].pop('keyframes')
    return fingerprint({'activeSequence':data['view']['active_sequence'],'project':value})


def revise(c, spec, operations, frame_ticks):
    from framing_plan import filmcraft_motion,filmcraft_tracking
    master=c.tool('sequence_inspect')['id']
    for op in operations:
        c.run('sequence.open',{'item':op['container']})
        for key,value in op['nestMotion'].items():c.run('effects.setParam',{'clip':op['nestClip'],'effect':'motion','param':key,'value':value})
        c.run('sequence.open',{'item':op['child']})
        if op['settings']:c.run('sequence.settings',{**op['settings'],'scaleMotion':False})
        panel=op['panel'];child_spec=panel_spec(spec,op['cut'],panel)
        if op['trackingChanged']:c.run('effects.toggleAnimation',{'clip':op['cameraClip'],'effect':'motion','param':'anchor'})
        fields=dict(op['cameraMotion'])
        if op['trackingChanged']:fields['anchor']=filmcraft_motion(child_spec,panel['crop'])['anchor']
        for key,value in fields.items():c.run('effects.setParam',{'clip':op['cameraClip'],'effect':'motion','param':key,'value':value})
        if op['trackingChanged']:filmcraft_tracking(c,{'clip':op['cameraClip']},child_spec['cuts'][0],panel['crop'],frame_ticks)
    c.run('sequence.open',{'item':master})
