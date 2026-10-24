"""Transport the text-hook owner's measured card into editable native graphics."""
import copy
import importlib.util
import math
import json
import os
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from common import SKILLS, inside, read, save, sha, require, fingerprint

HELPER = 'text-hook/scripts/render_hook.py'


def owner():
    location = SKILLS / HELPER
    spec = importlib.util.spec_from_file_location('acq_hook_owner', location)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def base_fingerprint(spec):
    return fingerprint({k: v for k, v in spec.items() if k != 'hookContract'})


def opening_end(spec):
    return min(math.ceil(5*Fraction(spec['fps']['numerator'],spec['fps']['denominator']))+1,
               sum(c['frames'] for c in spec['cuts']))


def validate_strategy(project, spec, recipe):
    strategy = recipe.get('caption_strategy', 'preserve')
    require(strategy in ['preserve','replace'], 'Unsupported caption treatment')
    if strategy == 'replace':
        from caption_visibility import ranges
        require(ranges(spec) == [{'startFrame':0,'endFrame':opening_end(spec)}],
                'Native replacement requires the caption owner to hide exactly the hook opening first')
        clean = inside(project['root'], recipe.get('clean_opening_source', ''))
        source = inside(project['root'], recipe['source'])
        require(clean == source and sha(clean) == recipe.get('clean_opening_sha256'),
                'Use the exact natively rendered caption-hidden base as the verified clean opening')


def prepare_plan(project, packet):
    from common import plan, verify_native_render
    spec = plan(project, packet)
    require(spec['backend'] in ['filmcraft','resolve'], 'Native hook transport requires FilmCraft or Resolve; no backend switch is permitted')
    require(not spec.get('hookContract'), 'Existing hooks need an identified replacement operation; additive duplication is refused')
    recipe_path = inside(project['root'], packet['recipe'])
    require(sha(recipe_path) == packet['recipeSha256'], 'Hook recipe changed')
    recipe = read(recipe_path)
    require(recipe.get('clip_id') == spec['clipId'], 'Hook recipe belongs to another clip')
    validate_strategy(project, spec, recipe)
    require(recipe.get('existing_hook') == 'none', 'Existing hook requires explicit identified replacement')
    source = inside(project['root'], recipe['source'])
    inside(project['root'], recipe['transcript'])
    receipt_path = inside(project['root'], packet['baseReceipt'])
    require(sha(receipt_path) == packet['baseReceiptSha256'], 'Base render receipt changed')
    receipt = read(receipt_path)
    require(receipt['projectId'] == project['id'] and receipt['backend'] == project['backend'] and receipt['clipId'] == spec['clipId'] and receipt['nativeRendered'] is True, 'Hook must refer to this clip and selected native backend')
    require(inside(project['root'], receipt['media']) == source and read(inside(project['root'], receipt['planPath'])) == spec, 'Hook must study the exact current finished cut')
    require(sha(inside(project['root'], receipt['nativeProject'])) == receipt['nativeFingerprint'], 'Base native project changed; reconcile before hook design')
    verify_native_render(source, spec)
    out = inside(Path(project['root'])/'10_WORK', packet['output'])
    require(not out.exists(), 'Hook output exists; preserve it and use a fresh revision')
    owner().build(recipe_path, out, render=False)
    contract = {'path': str(out/'resolved.json'), 'sha256': sha(out/'resolved.json'),
                'helperSha256': sha(SKILLS/HELPER), 'basePlanFingerprint': base_fingerprint(spec),
                'baseReceipt': str(receipt_path), 'baseReceiptSha256': sha(receipt_path)}
    if spec['backend']=='resolve':
        contract['baseInspectionSha256']=sha(inside(project['root'],receipt['nativeInspectionPath']))
    spec['hookContract'] = contract
    validate(project, spec)
    save(out/'plan.json', spec)
    return {'plan': str(out/'plan.json'), 'sha256': sha(out/'plan.json'), 'recipe': contract['path'],
            'status': 'prepared-awaiting-editable-native-construction', 'userApproved': False}


def validate(project, spec):
    contract = spec.get('hookContract')
    if not contract: return None
    require(spec['backend'] in ['filmcraft','resolve'], 'This backend has no qualified native hook transport; do not discard or bake the hook')
    try:
        import PIL
    except ImportError:
        interpreter=os.environ.get('ACQ_EDIT_SHARED_PYTHON')
        require(interpreter and Path(interpreter).resolve()!=Path(sys.executable).resolve(), 'Hook layout validation requires the configured shared Python with Pillow')
        result=subprocess.run([interpreter,str(Path(__file__).resolve())],input=json.dumps({'project':project,'spec':spec}),text=True,capture_output=True,timeout=120)
        require(result.returncode==0,'Hook layout validation failed: '+result.stderr[-2000:])
        return json.loads(result.stdout)
    require(contract['basePlanFingerprint'] == base_fingerprint(spec), 'Hook geometry/copy context changed; recalculate the hook from the current finished cut')
    require(contract['helperSha256'] == sha(SKILLS/HELPER), 'Hook helper changed; preserve the recipe and reconcile')
    path = inside(project['root'], contract['path'])
    require(sha(path) == contract['sha256'], 'Resolved hook recipe changed')
    m = read(path)
    for field in ['source', 'transcript']:
        require(sha(inside(project['root'], m[field])) == m[field+'_sha256'], 'Hook '+field+' changed')
    receipt_path = inside(project['root'], contract['baseReceipt'])
    require(sha(receipt_path) == contract['baseReceiptSha256'], 'Base render receipt changed')
    receipt = read(receipt_path)
    if spec['backend']=='resolve':
        require(contract.get('baseInspectionSha256')==sha(inside(project['root'],receipt['nativeInspectionPath'])), 'Base Resolve inspection changed')
    require(receipt['projectId'] == project['id'] and receipt['backend'] == project['backend'] and receipt['clipId'] == spec['clipId'], 'Base hook receipt identity differs')
    require(Path(receipt['media']).resolve() == Path(m['source']).resolve(), 'Hook source differs from base render')
    require(m['schema'] == 'text-hook/v1' and m['clip_id'] == spec['clipId'] and m['existing_hook'] == 'none', 'Unsupported native hook recipe')
    validate_strategy(project, spec, m)
    require(m['animation'] == 'none', 'Hook animation requires a separately supported native operation')
    require(m['canvas'] == [spec['width'], spec['height']] and Fraction(m['frame_rate']) == Fraction(spec['fps']['numerator'],spec['fps']['denominator']), 'Hook canvas or frame clock differs')
    fps = Fraction(spec['fps']['numerator'], spec['fps']['denominator'])
    end = opening_end(spec)
    require(abs(m['end_seconds']*float(fps)-end) < 1e-6, 'Hook must include the first frame at or after five seconds')
    cursor = 0; intervals = []
    for interval in m['placement_intervals']:
        start, stop = (math.ceil(interval[k]*float(fps)-1e-8) for k in ['start_seconds','end_seconds'])
        require(start == cursor and stop > start and stop <= end, 'Hook placement does not cover the opening frame grid')
        cursor = stop
        # Re-run the owner at its selected size. Only the owner decides placement.
        b = interval['caption_bounds']
        _, geometry = owner().layout(m, spec['width'], spec['height'], caption_bottom=b[1]+b[3],
            caption_bounds=b if m['native_explicit_intervals'] else None,
            protected_rects=interval.get('protected_rects', m['protected_rects']), forced_size=m['font_size_px'])
        require(geometry['bounds'] == interval['hook_bounds'], 'Resolved hook placement no longer matches the owner')
        for key in ['native_text','native_boxes','rendered_line_styles']:
            require(geometry[key] == interval[key], 'Native hook drawing differs from owning layout: '+key)
        for style in interval['rendered_line_styles']:
            require(sha(Path(style['font_path']).expanduser()) == style['font_sha256'], 'Exact hook font changed; do not substitute')
        intervals.append({**interval, 'startFrame': start, 'endFrame': stop})
    require(cursor == end, 'Hook opening coverage is incomplete')
    return {'recipe': m, 'intervals': intervals, 'name': 'acq-edit-hook-'+contract['sha256'][:16]}


def layers(interval):
    x, y, _, _ = interval['hook_bounds']; result = []
    for box in interval['native_boxes']:
        bx, by, w, h = box['bounds']
        result.append({'kind': 'shape', 'position': [x+bx+w/2, y+by+h/2], 'size': [w,h],
                       'color': box['color'], 'corner_radius': box['radius_px']})
    for text, style in zip(interval['native_text'], interval['rendered_line_styles']):
        result.append({'kind': 'text', 'text': text['text'], 'position': [x+text['baseline_px'][0], y+text['baseline_px'][1]],
                       'font': text['font_family'], 'font_style': text['font_style'], 'size': style['font_size_px'], 'color': style['foreground']})
    return result


def build_native(client, spec, prepared, frame_ticks):
    fonts = {f['family']: set(f['styles']) for f in client.run('fonts.list')}
    for interval in prepared['intervals']:
        for layer in layers(interval):
            if layer['kind'] == 'text':
                require(layer['font_style'] in fonts.get(layer['font'], set()), 'Exact native hook face unavailable: '+layer['font']+' / '+layer['font_style'])
    track = len(client.tool('sequence_inspect')['video'])
    client.run('sequence.addTracks', {'video': 1, 'audio': 0, 'videoAfter': 'last'})
    for index, interval in enumerate(prepared['intervals']):
        clip = None
        for layer in layers(interval):
            args = {'track': track, 'time': interval['startFrame']*frame_ticks,
                    'seconds': (interval['endFrame']-interval['startFrame'])*spec['fps']['denominator']/spec['fps']['numerator']}
            if clip is not None: args['clip'] = clip
            if layer['kind'] == 'shape':
                item = client.run('graphics.newShape', {**args, 'shape':'rectangle', 'position':layer['position'], 'size':layer['size']})
                props = {'color':layer['color'], 'cornerRadius':layer['corner_radius']}
            else:
                item = client.run('graphics.newText', {**args, 'text':layer['text'], 'position':layer['position'], 'font':layer['font'], 'fontStyle':layer['font_style'], 'size':layer['size']})
                props = {'text':layer['text'], 'color':layer['color'], 'align':'left', 'ligatures':True, 'kerning':True,
                         'fauxBold':False, 'fauxItalic':False, 'background':False, 'tracking':0}
            clip = item['clip']
            client.run('graphics.set', {**item, 'props':{**props, 'stroke':False, 'stroke2':False, 'shadow':False, 'opacity':100, 'fill':True}})
        client.run('clip.rename', {'clip':clip, 'name':prepared['name']+'-'+str(index)})


def scalar(param):
    require(set(param) == {'value'}, 'Animated hook parameters are unsupported')
    value = param['value']; require(len(value)==1, 'Invalid native parameter')
    return next(iter(value.values()))


def verify_native(data, spec, prepared, frame_ticks):
    seq = data['project']['items'][str(data['view']['active_sequence'])]['kind']['Sequence']
    owned = [(track, item) for track in seq['video_tracks'] for item in track['items'] if item['name'].startswith(prepared['name']+'-')]
    require(len(owned) == len(prepared['intervals']), 'Native hook interval coverage differs')
    require(all(track is seq['video_tracks'][-1] for track, _ in owned) and len(seq['video_tracks'][-1]['items']) == len(owned), 'Hook must occupy its separate top video track')
    require(not any(track.get('solo') for track in seq['video_tracks']), 'Solo video tracks need reconciliation before hook verification')
    for index, ((track,item), interval) in enumerate(zip(owned,prepared['intervals'])):
        require(track['enabled'] and not track['muted'] and not track['effects'] and not track['transitions'], 'Hook track is hidden or processed')
        require(item['name'] == prepared['name']+'-'+str(index) and item['enabled'] and item['speed']==1 and not item['reverse'] and item['source_in']==0 and item['frame_hold'] is None, 'Hook identity, enable or source clock differs')
        require(item.get('link') is None and item.get('group') is None and not item.get('scale_to_frame'), 'Hook must remain an independent native graphic')
        require(not item.get('graphic') and not item.get('multicam'), 'Responsive/multicam hook behavior is unsupported')
        require((item['start'],item['duration']) == (interval['startFrame']*frame_ticks,(interval['endFrame']-interval['startFrame'])*frame_ticks), 'Native hook timing differs')
        expected = layers(interval); effects = item['effects']
        require([e['effect'] for e in effects] == ['motion','opacity','time_remap']+['graphic_shape' if l['kind']=='shape' else 'graphic_text' for l in expected], 'Hook native layer order differs')
        require(all(e['enabled'] for e in effects), 'Hook effect disabled')
        require(all(not e.get('layer') for e in effects), 'Styled runs, responsive pins or other layer overrides require a supported hook operation')
        for effect, checks in [(effects[0], {'position':{'x':spec['width']/2,'y':spec['height']/2}, 'anchor':{'x':spec['width']/2,'y':spec['height']/2}, 'scale':100,'scale_width':100,'rotation':0}), (effects[1],{'opacity':100,'blend':0}), (effects[2],{'speed':100})]:
            for key,value in checks.items(): require(scalar(effect['params'][key])==value,'Hook clip transform changed: '+key)
        for effect, layer in zip(effects[3:], expected):
            values = {k:scalar(v) for k,v in effect['params'].items()}
            checks = {'position':dict(zip(['x','y'],layer['position'])), 'scale':100,'scale_width':100,'rotation':0,'opacity':100,'fill':True,'fill_kind':0,'shadow':False,'stroke':False,'stroke2':False,'anchor':{'x':0,'y':0}}
            checks.update({'shape':0,'size':dict(zip(['x','y'],layer['size'])),'corner_radius':layer['corner_radius']} if layer['kind']=='shape' else {'text':layer['text'],'font':layer['font'],'font_style':layer['font_style'],'size':layer['size'],'align':0,'tracking':0,'baseline_shift':0,'caps':0,'box_width':0,'box_height':0,'vertical':False,'faux_bold':False,'faux_italic':False,'background':False,'underline':False,'kerning':True,'ligatures':True})
            for key,value in checks.items(): require(values[key]==value,'Native hook property differs: '+key)
            color = [int(layer['color'][i:i+2],16)/255 for i in (1,3,5)]+[1]
            require(all(abs(a-b)<1e-6 for a,b in zip(values['fill_color'],color)), 'Hook color differs')
    return {'status':'NATIVE_HOOK_CONTRACT_VALID','intervals':len(owned),'editableText':True,'userApproved':False}


def verify_addition(before, after, spec, prepared, destination, frame_ticks):
    verify_native(after, spec, prepared, frame_ticks)
    expected = copy.deepcopy(before['project']); actual = copy.deepcopy(after['project'])
    key = str(before['view']['active_sequence'])
    require(after['view']['active_sequence'] == before['view']['active_sequence'], 'Hook changed active sequence')
    old_seq = expected['items'][key]['kind']['Sequence']; new_seq = actual['items'][key]['kind']['Sequence']
    require(len(new_seq['video_tracks']) == len(old_seq['video_tracks'])+1, 'Hook must add exactly one top video track')
    added_track = new_seq['video_tracks'].pop()
    require(len(added_track['items'])==len(prepared['intervals']) and all(i['name'].startswith(prepared['name']+'-') for i in added_track['items']), 'Added track contains unrelated material')
    added = set(actual['items'])-set(expected['items'])
    sources = {str(i['item']) for i in added_track['items']}
    require(len(sources)==1 and added == sources-set(expected['items']), 'Unexpected native sources created by hook')
    require(all('Graphic' in actual['items'][i]['kind'] for i in sources), 'Hook must use native graphic sources')
    for item in added:
        require('Graphic' in actual['items'][item]['kind'], 'Hook must remain editable native graphics')
        del actual['items'][item]
    expected['root']['children'] += [{'Item':int(i)} for i in sorted(added,key=int)]
    # IDs for the added track, graphic sources and clips are the only allocations.
    require(actual['next_id'] == expected['next_id']+1+2*len(prepared['intervals'])+len(added), 'Unexpected native ID allocation')
    actual['next_id'] = expected['next_id']
    expected['name'] = destination; expected['root']['name'] = destination
    require(fingerprint(actual)==fingerprint(expected), 'Hook addition changed protected native state')


if __name__=='__main__':
    request=json.load(sys.stdin)
    print(json.dumps(validate(request['project'],request['spec'])))
