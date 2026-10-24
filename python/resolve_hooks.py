"""Editable Fusion hook cards using the owning text-hook drawing coordinates."""
from pathlib import Path
from common import require, sha
from resolve_captions import inputs, same, source_name
from resolve_framing import verify_linear_keys


def font_preflight(resolve,prepared):
    fonts=resolve.Fusion().FontManager.GetFontList()
    require(isinstance(fonts,dict),'Native font inventory unavailable')
    for interval in prepared['intervals']:
        for text,style in zip(interval['native_text'],interval['rendered_line_styles']):
            file=fonts.get(text['font_family'],{}).get(text['font_style'])
            require(isinstance(file,str) and Path(file).is_file() and sha(file)==style['font_sha256'], 'Resolve must use the exact measured hook font file and face')
            require(style['font_index']==0,'Resolve hook collection faces need explicit native qualification')


def nodes(spec,prepared):
    width,height=spec['width'],spec['height'];result=[]
    prefix='ACQ_Hook_'
    for i,interval in enumerate(prepared['intervals']):
        x,y,_,_=interval['hook_bounds'];group=[]
        for n,box in enumerate(interval['native_boxes']):
            bx,by,w,h=box['bounds'];name=f'{prefix}{i}_Box{n}';color=[int(box['color'][k:k+2],16)/255 for k in (1,3,5)]
            group.extend([{'name':name+'Mask','type':'RectangleMask','values':{'Width':w/width,'Height':h/height,'Center':{1:(x+bx+w/2)/width,2:1-(y+by+h/2)/height},'CornerRadius':min(1,2*box['radius_px']/min(w,h)),'SoftEdge':0,'Solid':1}},
                {'name':name,'type':'Background','values':{'UseFrameFormatSettings':0,'Width':width,'Height':height,'TopLeftRed':color[0],'TopLeftGreen':color[1],'TopLeftBlue':color[2],'TopLeftAlpha':1},'connections':{'EffectMask':name+'Mask'}}])
        for n,(text,style) in enumerate(zip(interval['native_text'],interval['rendered_line_styles'])):
            name=f'{prefix}{i}_Text{n}';color=[int(style['foreground'][k:k+2],16)/255 for k in (1,3,5)]
            group.append({'name':name,'type':'TextPlus','values':{'UseFrameFormatSettings':0,'Width':width,'Height':height,'StyledText':text['text'],'Font':text['font_family'],'Style':text['font_style'],
                'Size':style['font_size_px']/(width*.72),'Center':{1:(x+text['baseline_px'][0])/width,2:1-(y+text['baseline_px'][1])/height},
                'HorizontalJustificationLeft':1,'VerticalJustificationBottom':1,'HorizontalLeftCenterRight':-1,'VerticalTopCenterBottom':1,
                'Red1':color[0],'Green1':color[1],'Blue1':color[2],'Alpha1':1,'Enabled1':1,'Opacity1':1}})
        for row in group:
            result.append(row)
    # Every painted box/text has its own merge, in the owner's draw order.
    final=[];previous='ACQ_Hook_Clear'
    for row in result:
        final.append(row)
        if row['type']=='RectangleMask':continue
        interval=prepared['intervals'][int(row['name'].split('_')[2])]
        # Per-frame native keys avoid expression-evaluation caches changing the
        # saved graph on first render. Each output frame has an explicit value.
        gate=[int(interval['startFrame']<=frame<interval['endFrame']) for frame in range(prepared['intervals'][-1]['endFrame'])]
        merge=row['name']+'Merge';final.append({'name':merge,'type':'Merge','values':{'MotionBlur':0},'connections':{'Background':previous,'Foreground':row['name']},'gate':gate});previous=merge
    return [{'name':'ACQ_Hook_Clear','type':'Background','values':{'UseFrameFormatSettings':0,'Width':width,'Height':height,'TopLeftAlpha':0}}]+final+[{'name':'ACQ_Hook_Output','type':'MediaOut','values':{},'connections':{'Input':previous}}]


def set_values(tool,values):
    for key,value in values.items():
        tool.SetInput(key,value)
        actual=tool.GetInput(key)
        require(all(same(actual.get(k),v) for k,v in value.items()) if isinstance(value,dict) else same(actual,value),'Fusion hook readback differs: '+key)


def construct(comp,spec,prepared):
    existing=list(comp.GetToolList(False).values())
    require(len(existing)==1 and existing[0].GetAttrs()['TOOLS_RegID']=='MediaOut','Use a fresh empty native Fusion generator')
    existing[0].SetAttrs({'TOOLS_Name':'ACQ_Hook_Output'})
    end=prepared['intervals'][-1]['endFrame'];comp.SetAttrs({'COMPN_GlobalStart':0,'COMPN_GlobalEnd':end-1,'COMPN_RenderStart':0,'COMPN_RenderEnd':end-1})
    rows=nodes(spec,prepared);created={'ACQ_Hook_Output':existing[0]}
    for row in rows:
        tool=created.get(row['name']) or comp.AddTool(row['type']);require(tool,'Fusion hook node unavailable: '+row['type']);tool.SetAttrs({'TOOLS_Name':row['name']});created[row['name']]=tool;set_values(tool,row['values'])
        if 'gate' in row:
            spline=comp.BezierSpline();require(spline,'Native hook visibility keys unavailable')
            spline.SetAttrs({'TOOLS_Name':row['name']+'Blend','TOOLB_NameSet':False});tool.Blend=spline
            spline.SetKeyFrames({frame:{1:value,'Flags':{'Linear':True}} for frame,value in enumerate(row['gate'])},True)
        for key,source in row.get('connections',{}).items():tool.ConnectInput(key,created[source])
    return verify_comp(comp,spec,prepared)


def verify_comp(comp,spec,prepared):
    rows=nodes(spec,prepared);actual={t.GetAttrs()['TOOLS_Name']:t for t in comp.GetToolList(False).values()}
    require(set(actual)=={r['name'] for r in rows}|{r['name']+'Blend' for r in rows if 'gate' in r},'Unexpected/missing hook Fusion nodes')
    for row in rows:
        tool=actual[row['name']];require(tool.GetAttrs()['TOOLS_RegID']==row['type'],'Hook node type differs');values=inputs(tool)
        for key,value in row['values'].items():
            observed=tool.GetInput(key)
            require(not values[key].GetExpression() and not values[key].GetConnectedOutput(),'Hook constant input is driven: '+key)
            require(all(same(observed.get(k),v) for k,v in value.items()) if isinstance(value,dict) else same(observed,value),'Hook input differs: '+key)
        if 'gate' in row:
            require(not values['Blend'].GetExpression(),'Hook visibility expression replaced native keys')
            require(source_name(values['Blend'])==row['name']+'Blend','Hook visibility driver differs')
            spline=actual[row['name']+'Blend'];require(spline.GetAttrs()['TOOLS_RegID']=='BezierSpline','Hook visibility modifier differs')
            verify_linear_keys(spline.GetKeyFrames(),0,row['gate'])
            for frame,value in enumerate(row['gate']):require(same(tool.GetInput('Blend',frame),value),'Hook interval clock differs')
        for key,source in row.get('connections',{}).items():require(source_name(values[key])==source,'Hook graph source differs')
    return {'editableText':True,'nativeNodes':len(actual),'userApproved':False}


def verify_timeline(timeline,spec,prepared):
    items=timeline.GetItemListInTrack('video',timeline.GetTrackCount('video')) or []
    require(len(items)==1,'Hook must occupy one independent top track')
    item=items[0];require(item.GetName()==prepared['name'] and item.GetMediaPoolItem() is None,'Hook is not the named native Fusion generator')
    require(item.GetStart(True)==0 and item.GetLeftOffset(True)==0 and item.GetDuration(True)==prepared['intervals'][-1]['endFrame'],'Hook native placement differs')
    require(item.GetClipEnabled() and timeline.GetIsTrackEnabled('video',timeline.GetTrackCount('video')) and not item.GetLinkedItems(),'Hook hidden or linked')
    require(item.GetFusionCompCount()==1,'Hook has unexpected Fusion compositions')
    return verify_comp(item.GetFusionCompByIndex(1),spec,prepared)
