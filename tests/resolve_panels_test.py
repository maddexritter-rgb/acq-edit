"""Native panel checks reject source, timing and graph damage before rendering."""
import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'python'))
from resolve_panels import verify, timing, center, preflight_fixed_revision
from framing_plan import fusion_crop


class Input:
    def __init__(self, key, target=None):
        self.key, self.target, self.expression = key, target, None
    def GetAttrs(self): return {'INPS_ID': self.key}
    def GetExpression(self): return self.expression
    def GetConnectedOutput(self): return self if self.target else None
    def GetTool(self): return self.target


class Node:
    def __init__(self, name, kind, fields=None, links=None):
        self.attrs = {'TOOLS_Name': name, 'TOOLS_RegID': kind}
        self.fields = fields or {}
        self.inputs = {k: Input(k) for k in self.fields}
        self.inputs.update({k: Input(k, v) for k,v in (links or {}).items()})
        self.data = {}
    def GetAttrs(self): return self.attrs
    def GetInputList(self): return self.inputs
    def GetInput(self, key): return self.fields.get(key)
    def GetData(self, key): return self.data.get(key)
    def __getattr__(self, key): return self.inputs[key]


class Comp:
    def __init__(self): self.nodes, self.prefs = {}, {'Comp.FrameFormat.Width':360, 'Comp.FrameFormat.Height':640}
    def GetAttrs(self): return {'COMPN_RenderStart': 25}
    def GetPrefs(self, key): return self.prefs.get(key)
    def FindTool(self, key): return self.nodes.get(key)
    def GetToolList(self, selected): return self.nodes
    def add(self, node): self.nodes[node.attrs['TOOLS_Name']]=node; return node


class ResolvePanelsTests(unittest.TestCase):
    def fixture(self):
        comp=Comp(); cut={'id':'cut','sourceInFrame':25,'recordFrame':50,'frames':25}
        spec={'width':360,'height':640,'sources':[], 'framing':{'shots':{'cut':{'mode':'panel-layout','panels':[]}}}}
        previous=comp.add(Node('ACQ_PanelCanvas','Background',{'UseFrameFormatSettings':0,'Width':360,'Height':640,'TopLeftAlpha':0}))
        for i in range(2):
            source_id=str(i); name=f'ACQ_Panel{i}_'; path=str(Path(f'camera{i}.mp4').resolve())
            spec['sources'].append({'id':source_id,'path':path})
            panel={'sourceRange':{'sourceId':source_id,'inFrame':50+i*25,'frames':25},
                   'rect':{'x':0,'y':320*i,'width':360,'height':320},
                   'crop':{'mode':'fixed-crop','sourceWidth':640,'sourceHeight':360,'x':80,'y':20,'width':360,'height':320}}
            spec['framing']['shots']['cut']['panels'].append(panel)
            source=comp.add(Node(name+'Source','MediaIn',{'MediaSource':'MediaPool','MediaID':source_id,**timing(comp,panel['sourceRange'])}))
            source.attrs.update(TOOLS_Clip_Path=path,TOOLS_Clip_MediaID=source_id,TOOLI_Clip_Width=640,TOOLI_Clip_Height=360);source.data['MEDIA_ID']=source_id
            crop=comp.add(Node(name+'Crop','Crop',fusion_crop(spec,panel['crop']),{'Input':source}))
            resize=comp.add(Node(name+'Resize','BetterResize',{'KeepAspect':0,'Width':360,'Height':320},{'Input':crop}))
            previous=comp.add(Node('ACQ_PanelComposite' if i==1 else name+'Merge','Merge',{'Center':center(spec,panel['rect']),'Size':1,'Angle':0,'Blend':1,'ApplyMode':'Normal','Operator':'Over'},{'Background':previous,'Foreground':resize}))
        comp.add(Node('MediaOut1','MediaOut',links={'Input':previous}))
        return comp,spec,cut

    def test_source_trim_is_independent_of_master_clock_and_panel_center_uses_top_origin(self):
        comp,spec,cut=self.fixture();verify(comp,spec,cut)
        self.assertEqual(timing(comp,{'inFrame':75,'frames':25}),{'ClipTimeStart':75,'ClipTimeEnd':99,'GlobalIn':25,'GlobalOut':49,'HoldFirstFrame':0,'HoldLastFrame':0,'Reverse':0,'Loop':0})
        self.assertEqual(center(spec,{'x':0,'y':320,'width':360,'height':320}),{1:.5,2:.25})

    def test_source_identity_and_range_corruption_is_refused(self):
        for damage in ['path','binding','persistent','resolution','trim','hold','driven']:
            comp,spec,cut=self.fixture();node=comp.FindTool('ACQ_Panel1_Source')
            if damage=='path':node.attrs['TOOLS_Clip_Path']='other.mp4'
            elif damage=='binding':node.fields['MediaID']='wrong'
            elif damage=='persistent':node.data['MEDIA_ID']='wrong'
            elif damage=='resolution':node.attrs['TOOLI_Clip_Width']=720
            elif damage=='trim':node.fields['ClipTimeStart']+=1
            elif damage=='hold':node.fields['HoldLastFrame']=1
            else:node.inputs['ClipTimeStart'].expression='time'
            with self.subTest(damage=damage),self.assertRaises(RuntimeError):verify(comp,spec,cut)

    def test_hidden_geometry_and_output_changes_are_refused(self):
        for damage in ['bypass','mask','resize','position','mode','connection','output','format']:
            comp,spec,cut=self.fixture();merge=comp.FindTool('ACQ_PanelComposite')
            if damage=='bypass':merge.attrs['TOOLB_PassThrough']=True
            elif damage=='mask':merge.inputs['EffectMask']=Input('EffectMask',comp.FindTool('ACQ_PanelCanvas'))
            elif damage=='resize':comp.FindTool('ACQ_Panel1_Resize').fields['Width']=359
            elif damage=='position':merge.fields['Center']={1:.5,2:.3}
            elif damage=='mode':merge.fields['Operator']='In'
            elif damage=='connection':merge.inputs['Foreground'].target=comp.FindTool('ACQ_Panel0_Resize')
            elif damage=='output':comp.FindTool('MediaOut1').inputs['Input'].target=comp.FindTool('ACQ_Panel1_Source')
            else:comp.prefs['Comp.FrameFormat.Width']=640
            with self.subTest(damage=damage),self.assertRaises(RuntimeError):verify(comp,spec,cut)

    def test_owned_captions_may_follow_panels_but_unknown_layers_cannot(self):
        comp,spec,cut=self.fixture();text=comp.add(Node('ACQ_Caption_0','TextPlus'))
        merge=comp.add(Node('CaptionMerge','Merge',links={'Background':comp.FindTool('ACQ_PanelComposite'),'Foreground':text}))
        comp.FindTool('MediaOut1').inputs['Input'].target=merge;verify(comp,spec,cut)
        text.attrs['TOOLS_Name']='UnownedText'
        with self.assertRaisesRegex(RuntimeError,'Unknown layer'):verify(comp,spec,cut)

    def test_fixed_revision_refuses_panel_target_even_when_new_plan_claims_fixed_crop(self):
        comp,spec,cut=self.fixture();item=Mock();item.GetFusionCompByIndex.return_value=comp
        timeline=Mock();timeline.GetItemListInTrack.return_value=[item]
        edits=[{'track':1,'itemIndex':0,'cutId':'cut'}]
        with self.assertRaisesRegex(RuntimeError,'cannot revise panel'):preflight_fixed_revision(timeline,spec,edits)
        spec['framing']['shots']['cut']={'mode':'fixed-crop'}
        with self.assertRaisesRegex(RuntimeError,'Native panel revisions'):preflight_fixed_revision(timeline,spec,edits)
        timeline.DuplicateTimeline.assert_not_called()


if __name__=='__main__':unittest.main()
