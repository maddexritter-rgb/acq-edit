"""Compose independently timed native Media Pool inputs with Fusion panels."""
from pathlib import Path
from common import require
from framing_plan import fusion_crop, require_static_fusion_crop
from resolve_framing import write_tracking, verify_comp as verify_crop


def prefix(index):
    return f'ACQ_Panel{index}_'


def merge_name(index, count):
    return 'ACQ_PanelComposite' if index == count-1 else prefix(index)+'Merge'


def timing(comp, span):
    start = comp.GetAttrs()['COMPN_RenderStart']
    return {'ClipTimeStart': span['inFrame'], 'ClipTimeEnd': span['inFrame']+span['frames']-1,
            'GlobalIn': start, 'GlobalOut': start+span['frames']-1,
            'HoldFirstFrame': 0, 'HoldLastFrame': 0, 'Reverse': 0, 'Loop': 0}


def center(spec, rect):
    return {1: (rect['x']+rect['width']/2)/spec['width'],
            2: 1-(rect['y']+rect['height']/2)/spec['height']}


def put(tool, fields):
    for key, value in fields.items():
        tool.SetInput(key, value)
    check(tool, fields)


def check(tool, fields):
    require_static_fusion_crop(tool, fields)
    for key, value in fields.items():
        actual = tool.GetInput(key)
        if isinstance(value, dict):
            require(isinstance(actual, dict) and all(abs(actual.get(k, float('inf'))-v)<1e-9 for k,v in value.items()), 'Panel point changed: '+key)
        else:
            require(actual == value, 'Panel input changed: '+key)


def link(tool, key, expected):
    value = next((v for v in tool.GetInputList().values() if v.GetAttrs().get('INPS_ID') == key), None)
    require(value and not value.GetExpression(), 'Panel input expression or missing connection: '+key)
    output = value.GetConnectedOutput()
    require(output and output.GetTool().GetAttrs()['TOOLS_Name'] == expected.GetAttrs()['TOOLS_Name'], 'Panel graph connection changed: '+key)


def preflight_fixed_revision(timeline, spec, edits):
    """Reject panel rewrites before allocating a native revision timeline."""
    items = timeline.GetItemListInTrack('video', 1)
    for edit in edits:
        require(edit['track']==1 and 0<=edit['itemIndex']<len(items), 'Framing target absent')
        shot = spec['framing']['shots'].get(edit['cutId'])
        require(shot and shot['mode']=='fixed-crop', 'Fixed framing cannot revise panel layouts or tracking; use the owning revision route')
        comp = items[edit['itemIndex']].GetFusionCompByIndex(1)
        require(comp and not comp.FindTool('ACQ_PanelCanvas'), 'Native panel revisions are not supported; preserve the existing camera graph')


def construct(comp, spec, cut, layout, sources):
    require(not comp.FindTool('ACQ_PanelCanvas'), 'Existing panel graph requires reconciliation')
    canvas = comp.AddTool('Background'); require(canvas, 'Fusion canvas unavailable')
    canvas.SetAttrs({'TOOLS_Name': 'ACQ_PanelCanvas'})
    put(canvas, {'UseFrameFormatSettings': 0, 'Width': spec['width'], 'Height': spec['height'], 'TopLeftAlpha': 0})
    background = canvas
    for index, panel in enumerate(layout['panels']):
        name = prefix(index); span = panel['sourceRange']; rect = panel['rect']
        source = comp.AddTool('MediaIn'); crop = comp.AddTool('Crop'); resize = comp.AddTool('BetterResize'); merge = comp.AddTool('Merge')
        require(source and crop and resize and merge, 'Native panel inputs unavailable')
        for tool, label in [(source, name+'Source'), (crop, name+'Crop'), (resize, name+'Resize'), (merge, merge_name(index,len(layout['panels'])))]:
            tool.SetAttrs({'TOOLS_Name': label})
        put(source, {'MediaSource': 'MediaPool', 'MediaID': sources[span['sourceId']].GetMediaId()})
        # Resolve persists this native identity on reopen. Write and verify it
        # during construction instead of excluding it from graph fingerprints.
        source.SetData('MEDIA_ID', sources[span['sourceId']].GetMediaId())
        put(source, timing(comp, span))
        put(crop, fusion_crop(spec, panel['crop']))
        put(resize, {'KeepAspect': 0, 'Width': rect['width'], 'Height': rect['height']})
        crop.ConnectInput('Input', source); resize.ConnectInput('Input', crop)
        write_tracking(comp, crop, panel['crop'], name)
        merge.ConnectInput('Background', background); merge.ConnectInput('Foreground', resize)
        put(merge, {'Center': center(spec, rect), 'Size': 1, 'Angle': 0, 'Blend': 1, 'ApplyMode': 'Normal', 'Operator': 'Over'})
        background = merge
    # Adding camera inputs initializes the composition to source dimensions.
    # Its persisted output format must be established after those inputs exist.
    comp.SetPrefs({'Comp.FrameFormat.Width': spec['width'], 'Comp.FrameFormat.Height': spec['height']})
    verify(comp, spec, cut, composed=False)
    return background


def verify(comp, spec, cut, composed=True):
    require(comp.GetPrefs('Comp.FrameFormat.Width')==spec['width'] and comp.GetPrefs('Comp.FrameFormat.Height')==spec['height'], 'Panel composition frame format changed')
    layout = spec['framing']['shots'][cut['id']]; canvas = comp.FindTool('ACQ_PanelCanvas')
    require(canvas and canvas.GetAttrs()['TOOLS_RegID']=='Background' and not canvas.GetAttrs().get('TOOLB_PassThrough'), 'Panel canvas missing or bypassed')
    check(canvas, {'UseFrameFormatSettings': 0, 'Width': spec['width'], 'Height': spec['height'], 'TopLeftAlpha': 0})
    background = canvas
    for index, panel in enumerate(layout['panels']):
        name = prefix(index); span = panel['sourceRange']; rect = panel['rect']
        nodes = [comp.FindTool(n) for n in [name+'Source', name+'Crop', name+'Resize', merge_name(index,len(layout['panels']))]]
        require(all(nodes), 'Owned panel graph missing'); source, crop, resize, merge = nodes
        for tool, kind in zip(nodes, ['MediaIn', 'Crop', 'BetterResize', 'Merge']):
            attrs = tool.GetAttrs()
            require(attrs['TOOLS_RegID']==kind and not attrs.get('TOOLB_PassThrough'), 'Panel node type or bypass changed')
            mask=next((v for v in tool.GetInputList().values() if v.GetAttrs().get('INPS_ID')=='EffectMask'), None)
            require(not mask or not mask.GetConnectedOutput() and not mask.GetExpression(), 'Unexpected panel mask')
        record = next(s for s in spec['sources'] if s['id']==span['sourceId']); attrs=source.GetAttrs()
        require(Path(attrs.get('TOOLS_Clip_Path','')).resolve()==Path(record['path']).resolve(), 'Panel Media Pool source path changed')
        require(source.GetInput('MediaID') and source.GetInput('MediaID')==attrs.get('TOOLS_Clip_MediaID'), 'Panel Media Pool binding changed')
        require(source.GetData('MEDIA_ID')==source.GetInput('MediaID'), 'Persisted panel Media Pool identity changed')
        require((attrs.get('TOOLI_Clip_Width'),attrs.get('TOOLI_Clip_Height'))==(panel['crop']['sourceWidth'],panel['crop']['sourceHeight']), 'Panel source resolution changed')
        check(source, {'MediaSource': 'MediaPool', **timing(comp,span)})
        verify_crop(comp,crop,panel['crop'],name)
        if panel['crop']['mode']=='fixed-crop': link(crop,'Input',source)
        else: link(comp.FindTool(name+'Track'),'Input',source)
        check(resize, {'KeepAspect': 0, 'Width': rect['width'], 'Height': rect['height']}); link(resize,'Input',crop)
        check(merge, {'Center': center(spec,rect), 'Size': 1, 'Angle': 0, 'Blend': 1, 'ApplyMode': 'Normal', 'Operator': 'Over'})
        link(merge,'Background',background); link(merge,'Foreground',resize)
        background=merge
    if composed:
        # Only the caption owner's merge chain may follow the panel composite.
        outputs=[t for t in comp.GetToolList(False).values() if t.GetAttrs()['TOOLS_RegID']=='MediaOut']
        require(len(outputs)==1, 'Panel composition output changed')
        output=outputs[0].Input.GetConnectedOutput(); require(output, 'Panel output disconnected')
        node=output.GetTool(); seen=set()
        while node.GetAttrs()['TOOLS_Name'] != background.GetAttrs()['TOOLS_Name']:
            attrs=node.GetAttrs(); name=attrs['TOOLS_Name']
            require(name not in seen and attrs['TOOLS_RegID']=='Merge', 'Panel output bypasses the composed cameras')
            seen.add(name); foreground=node.Foreground.GetConnectedOutput(); previous=node.Background.GetConnectedOutput()
            require(foreground and previous and foreground.GetTool().GetAttrs()['TOOLS_RegID']=='TextPlus' and foreground.GetTool().GetAttrs()['TOOLS_Name'].startswith('ACQ_Caption_'), 'Unknown layer after panel composition')
            node=previous.GetTool()
    return background
