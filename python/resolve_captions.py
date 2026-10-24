"""Native Fusion execution of caption-clips cards and explicit Resolve styling."""
from common import require
from caption_plan import profile_caption_motion

TICKS = 254016000000
ROLES = ('wide', 'tight', 'text')


def verify_fonts(resolve, prepared):
    fonts = resolve.Fusion().FontManager.GetFontList()
    require(isinstance(fonts, dict), 'Resolve font inventory unavailable')
    for card in prepared['cards']:
        style = card['style']
        face = style['italicStyle'] if card['italic'] else style['fontStyle']
        require(face in fonts.get(style['font'], {}),
                'Exact Resolve caption font face missing: ' + style['font'] + ' / ' + face)


def linear_expression(points, clock):
    """Emit the owner's piecewise linear curve without resampling or guessing easing."""
    expr = repr(points[-1][1])
    for (start, first), (end, last) in reversed(list(zip(points, points[1:]))):
        value = f'({first!r}+({last-first!r})*max(0,({clock})-{start!r})/{end-start!r})'
        expr = f'iif(({clock}) < {end!r}, {value}, {expr})'
    return expr


def card_nodes(spec, prepared, cut, render_start):
    ft = TICKS * spec['fps']['denominator'] / spec['fps']['numerator']
    result = []
    for index, card in enumerate(prepared['cards']):
        start = max(card['start_frame'], cut['recordFrame'])
        end = min(card['end_frame'], cut['recordFrame'] + cut['frames'])
        if end <= start:
            continue
        style = card['style']
        face = style['italicStyle'] if card['italic'] else style['fontStyle']
        clock = f'(time-{render_start!r}+{cut["recordFrame"]-card["start_frame"]+card.get("elapsed_frames",0)!r})'
        motion, opacity = profile_caption_motion(prepared['profile'], ft, card['end_frame'] - card['start_frame'],
                                                 center=(spec['width']/2, spec['height']/2), canvas_height=spec['height'])
        def points(param, extract):
            keys = param.get('keyframes', [])
            return [(k['time']/ft, extract(k['value'])) for k in keys] if keys else [(0, extract(param['value']))]
        offset = linear_expression(points(motion, lambda v: (v['Vec2']['y']-spec['height']/2)/spec['height']), clock)
        alpha = linear_expression(points(opacity, lambda v: v['Float']/100), clock)
        gate = f'iif(time >= {render_start+start-cut["recordFrame"]!r} and time < {render_start+end-cut["recordFrame"]!r}, ({alpha}), 0)'
        for role in ROLES:
            shadow = prepared['profile']['resolve_caption_shadows'].get(role)
            x, y = style['center']
            if shadow: x += shadow['offset'][0]; y += shadow['offset'][1]
            color = [0., 0., 0.] if shadow else [int(style['color'][i:i+2], 16)/255 for i in (1,3,5)]
            values = {'UseFrameFormatSettings': 0, 'Width': spec['width'], 'Height': spec['height'],
                      'StyledText': card['text'], 'Font': style['font'], 'Style': face, 'Size': style['fusionSize'],
                      'VerticalJustificationNew': 3, 'HorizontalJustificationNew': 3,
                      'Red1': color[0], 'Green1': color[1], 'Blue1': color[2], 'Alpha1': 1,
                      'Enabled1': 1, 'Opacity1': shadow['opacity'] if shadow else 1,
                      'SoftnessX1': shadow['softness'][0] if shadow else 0,
                      'SoftnessY1': shadow['softness'][1] if shadow else 0}
            result.append({'textName': f'ACQ_Caption_{index}_{role}', 'mergeName': f'ACQ_CaptionMerge_{index}_{role}',
                           'values': values, 'center': f'Point({x!r},({y!r})-({offset}))', 'blend': gate,
                           'start': render_start+start-cut['recordFrame'], 'end': render_start+end-cut['recordFrame']})
    return result


def inputs(tool):
    return {value.GetAttrs()['INPS_ID']: value for value in tool.GetInputList().values()}


def same(actual, expected):
    return abs(actual-expected) < 1e-6 if isinstance(expected, (int, float)) and isinstance(actual, (int, float)) else actual == expected


def construct(comp, source, output, cut, spec, prepared):
    for row in card_nodes(spec, prepared, cut, comp.GetAttrs()['COMPN_RenderStart']):
        require(not comp.FindTool(row['textName']) and not comp.FindTool(row['mergeName']), 'Owned caption node already exists; do not replay construction')
        text, merge = comp.AddTool('TextPlus'), comp.AddTool('Merge')
        require(text and merge, 'Native Fusion caption nodes unavailable')
        text.SetAttrs({'TOOLS_Name': row['textName']}); merge.SetAttrs({'TOOLS_Name': row['mergeName']})
        for key, value in row['values'].items():
            text.SetInput(key, value)
            require(same(text.GetInput(key), value), 'Fusion caption property readback differs: ' + key)
        text.Center.SetExpression(row['center']); merge.Blend.SetExpression(row['blend'])
        require(text.Center.GetExpression() == row['center'] and merge.Blend.GetExpression() == row['blend'], 'Fusion caption expression readback differs')
        merge.ConnectInput('Background', source); merge.ConnectInput('Foreground', text); source = merge
    output.ConnectInput('Input', source)
    return verify_comp(comp, cut, spec, prepared)


def source_name(handle):
    connected = handle.GetConnectedOutput()
    return connected.GetTool().GetAttrs()['TOOLS_Name'] if connected else None


def verify_comp(comp, cut, spec, prepared):
    rows = card_nodes(spec, prepared, cut, comp.GetAttrs()['COMPN_RenderStart'])
    expected_names = {row[key] for row in rows for key in ['textName', 'mergeName']}
    tools = comp.GetToolList(False)
    owned = {tool.GetAttrs()['TOOLS_Name'] for tool in tools.values() if tool.GetAttrs()['TOOLS_Name'].startswith(('ACQ_Caption_', 'ACQ_CaptionMerge_'))}
    require(owned == expected_names, 'Native Fusion caption coverage differs')
    source = comp.FindTool('ACQ_FramingResize')
    if not source:
        source = next((t for t in tools.values() if t.GetAttrs()['TOOLS_RegID'] == 'MediaIn'), None)
    require(source, 'Caption background source absent')
    for row in rows:
        text, merge = comp.FindTool(row['textName']), comp.FindTool(row['mergeName'])
        require(text.GetAttrs()['TOOLS_RegID'] == 'TextPlus' and merge.GetAttrs()['TOOLS_RegID'] == 'Merge', 'Native caption node type differs')
        ti, mi = inputs(text), inputs(merge)
        for key, value in row['values'].items():
            require(not ti[key].GetExpression() and not ti[key].GetConnectedOutput() and same(text.GetInput(key), value), 'Native caption input changed: ' + key)
        require(ti['Center'].GetExpression() == row['center'] and mi['Blend'].GetExpression() == row['blend'], 'Native caption clock/animation changed')
        require(source_name(mi['Background']) == source.GetAttrs()['TOOLS_Name'] and source_name(mi['Foreground']) == row['textName'], 'Native caption graph connection changed')
        for time in [row['start'], (row['start']+row['end']-1)/2, row['end']-1]:
            center = text.GetInput('Center', time); alpha = merge.GetInput('Blend', time)
            require(isinstance(center, dict) and all(isinstance(center.get(i), (int, float)) for i in [1,2]) and isinstance(alpha, (int,float)) and 0 <= alpha <= 1, 'Native caption expression failed evaluation')
        source = merge
    output = next((t for t in tools.values() if t.GetAttrs()['TOOLS_RegID'] == 'MediaOut'), None)
    require(output and source_name(inputs(output)['Input']) == source.GetAttrs()['TOOLS_Name'], 'Native caption output disconnected')
    return {'cards': len(rows)//3, 'textNodes': len(rows), 'status': 'native-fusion-caption-contract-verified'}


def verify_timeline(timeline, spec, prepared):
    items = timeline.GetItemListInTrack('video', 1)
    require(len(items) == len(spec['cuts']), 'Caption picture coverage differs')
    require(timeline.GetIsTrackEnabled('video', 1), 'Caption picture track disabled')
    for item, cut in zip(items, spec['cuts']):
        require(item.GetStart(True) == cut['recordFrame'] and item.GetDuration(True) == cut['frames'] and item.GetLeftOffset(True) == cut['sourceInFrame'], 'Caption picture clocks changed')
        require(item.GetClipEnabled(), 'Caption picture clip disabled')
        cards = [c for c in prepared['cards'] if c['start_frame'] < cut['recordFrame']+cut['frames'] and c['end_frame'] > cut['recordFrame']]
        if cards:
            require(item.GetFusionCompCount() == 1, 'Expected one owned caption composition')
            verify_comp(item.GetFusionCompByIndex(1), cut, spec, prepared)
