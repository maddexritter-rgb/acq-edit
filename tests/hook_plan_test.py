"""Owning layout, source/context pins and native hook protection boundaries."""
import copy
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'python'))
import hook_plan as hooks
from common import sha, fingerprint

FONT = next((p for p in [Path('/System/Library/Fonts/Supplemental/Arial Bold.ttf'), Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')] if p.is_file()), None)


@unittest.skipIf(FONT is None, 'A real test font is required')
class HookPlanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        p = patch.object(hooks,'SKILLS',ROOT/'distribution/skills'); p.start(); self.addCleanup(p.stop)
        self.project = {'id':'project','root':str(self.root),'backend':'filmcraft'}
        self.spec = {'projectId':'project','backend':'filmcraft','clipId':'clip','width':640,'height':360,
                     'fps':{'numerator':30000,'denominator':1001},'cuts':[{'frames':180}], 'captions':[]}
        self.source = self.root/'source.mp4'; self.source.write_bytes(b'Synthetic probe fixture')
        self.transcript = self.root/'transcript.txt'; self.transcript.write_text('Keep the meaning. Make clean cuts.')
        self.recipe = {'schema':'text-hook/v1','clip_id':'clip','source':str(self.source),'source_sha256':sha(self.source),
            'transcript':str(self.transcript),'transcript_sha256':sha(self.transcript),'transcript_revision':'fixture-v1',
            'selected_text':'Keep the meaning Make clean cuts','display_lines':['Keep the meaning','Make clean cuts'],
            'font_path':str(FONT),'existing_hook':'none','delivery_platform':'custom','caption_bottom_px':0,
            'safe_rect':[38,24,564,310],'protected_rects':[],'geometry_evidence':'Synthetic fixture only',
            'supporting_passages':[{'quote':'Keep the meaning. Make clean cuts.','location':'fixture'}]}

    def resolved(self, recipe=None):
        recipe = recipe or self.recipe
        file = self.root/'recipe.json'; file.write_text(json.dumps(recipe))
        owner = hooks.owner()
        def frame(cmd, **kw): Image.new('RGB',(640,360),'gray').save(cmd[-1])
        probe = {'streams':[{'codec_type':'video','width':640,'height':360,'avg_frame_rate':'30000/1001','duration':'6.006'}], 'format':{'duration':'6.006'}}
        with patch.object(owner,'probe',return_value=probe), patch.object(owner.subprocess,'run',side_effect=frame):
            m = owner.build(file,self.root/'prepared')
        receipt = self.root/'receipt.json'; receipt.write_text(json.dumps({'projectId':'project','backend':'filmcraft','clipId':'clip','media':str(self.source)}))
        path = self.root/'prepared/resolved.json'
        self.spec['hookContract'] = {'path':str(path),'sha256':sha(path),'helperSha256':sha(hooks.SKILLS/hooks.HELPER),
            'basePlanFingerprint':hooks.base_fingerprint(self.spec),'baseReceipt':str(receipt),'baseReceiptSha256':sha(receipt)}
        return m

    def test_owner_coordinates_reconstruct_exact_preview_pixels(self):
        owner = hooks.owner()
        for mode in ['fitted_lines','unified']:
            for case in ['preserve','upper']:
                with self.subTest(mode=mode,case=case):
                    m = copy.deepcopy(self.recipe)
                    m.update(style_id='fixture',style={'id':'fixture','status':'approved','approval_evidence':'Synthetic layout fixture only',
                        'case':case,'foreground':'#183060','background':'#FFFFFF','font_path':str(FONT),'box_mode':mode})
                    plate,g = owner.layout(m,640,360)
                    rebuilt = Image.new('RGBA',plate.size); draw = ImageDraw.Draw(rebuilt)
                    for b in g['native_boxes']:
                        x,y,w,h=b['bounds'];draw.rounded_rectangle((x,y,x+w-1,y+h-1),radius=b['radius_px'],fill=b['color'])
                    for t,s in zip(g['native_text'],g['rendered_line_styles']):
                        font=ImageFont.truetype(s['font_path'],s['font_size_px'],index=s['font_index'])
                        draw.text((t['baseline_px'][0],t['baseline_px'][1]-font.getmetrics()[0]),t['text'],font=font,fill=s['foreground'])
                    self.assertEqual(plate.tobytes(),rebuilt.tobytes())

    def test_fractional_rate_inclusive_five_second_frame_and_cap(self):
        m = self.resolved(); prepared=hooks.validate(self.project,self.spec)
        self.assertEqual(prepared['intervals'][0]['startFrame'],0)
        self.assertEqual(prepared['intervals'][0]['endFrame'],151)
        self.assertAlmostEqual(m['end_seconds'],151*1001/30000)
        self.assertFalse(m['native_explicit_intervals'])

    def test_exact_helper_recipe_font_source_and_context_are_pinned(self):
        self.resolved(); original=copy.deepcopy(self.spec)
        self.spec['captions']=[{'text':'changed'}]
        with self.assertRaisesRegex(RuntimeError,'context changed'):hooks.validate(self.project,self.spec)
        self.spec=copy.deepcopy(original);self.spec['hookContract']['helperSha256']='stale'
        with self.assertRaisesRegex(RuntimeError,'helper changed'):hooks.validate(self.project,self.spec)
        self.spec=copy.deepcopy(original);self.spec['hookContract']['sha256']='stale'
        with self.assertRaisesRegex(RuntimeError,'recipe changed'):hooks.validate(self.project,self.spec)
        self.spec=copy.deepcopy(original);self.source.write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError,'source changed'):hooks.validate(self.project,self.spec)

    def test_other_engine_and_caption_hiding_refuse(self):
        self.resolved(); self.spec['backend']='premiere'
        with self.assertRaisesRegex(RuntimeError,'no qualified'):hooks.validate(self.project,self.spec)
        self.spec['backend']='filmcraft'
        file=Path(self.spec['hookContract']['path']);m=json.loads(file.read_text());m['caption_strategy']='replace';file.write_text(json.dumps(m));self.spec['hookContract']['sha256']=sha(file)
        with self.assertRaisesRegex(RuntimeError,'Unsupported native hook'):hooks.validate(self.project,self.spec)

    def test_resolve_base_inspection_is_pinned_before_native_editing(self):
        self.resolved();self.project['backend']=self.spec['backend']='resolve'
        receipt=Path(self.spec['hookContract']['baseReceipt']);value=json.loads(receipt.read_text())
        inspection=self.root/'inspection.json';inspection.write_text('{"timeline":"fixture"}')
        value.update(backend='resolve',nativeInspectionPath=str(inspection));receipt.write_text(json.dumps(value))
        self.spec['hookContract'].update(baseReceiptSha256=sha(receipt),basePlanFingerprint=hooks.base_fingerprint(self.spec),baseInspectionSha256=sha(inspection))
        hooks.validate(self.project,self.spec);inspection.write_text('{"timeline":"changed"}')
        with self.assertRaisesRegex(RuntimeError,'Base Resolve inspection changed'):hooks.validate(self.project,self.spec)

    def test_tampered_native_coordinates_are_not_a_new_layout_owner(self):
        self.resolved();file=Path(self.spec['hookContract']['path']);m=json.loads(file.read_text());m['placement_intervals'][0]['native_text'][0]['baseline_px'][0]+=1;file.write_text(json.dumps(m));self.spec['hookContract']['sha256']=sha(file)
        with self.assertRaisesRegex(RuntimeError,'owning layout'):hooks.validate(self.project,self.spec)

    def test_animated_native_parameter_refuses(self):
        with self.assertRaisesRegex(RuntimeError,'Animated'):hooks.scalar({'value':{'Float':100},'keyframes':[{'time':0}]})

    def test_native_source_reuse_preserves_entire_existing_project(self):
        before={'view':{'active_sequence':1},'project':{'name':'base','root':{'name':'base','children':[{'Item':2}]},'next_id':10,'items':{
            '1':{'kind':{'Sequence':{'video_tracks':[{'items':[{'name':'manually edited caption'}]}],'audio_tracks':[{'level':-3}]}}},
            '2':{'kind':{'Graphic':{'width':640,'height':360}}}}}}
        prepared={'name':'owned','intervals':[{},{}]}
        after=copy.deepcopy(before);after['project']['name']=after['project']['root']['name']='hook';after['project']['next_id']=15
        after['project']['items']['1']['kind']['Sequence']['video_tracks'].append({'items':[{'name':'owned-0','item':2},{'name':'owned-1','item':2}]})
        with patch.object(hooks,'verify_native'):
            hooks.verify_addition(before,after,self.spec,prepared,'hook',1)
            for path in ['audio','caption']:
                changed=copy.deepcopy(after)
                if path=='audio':changed['project']['items']['1']['kind']['Sequence']['audio_tracks'][0]['level']=0
                else:changed['project']['items']['1']['kind']['Sequence']['video_tracks'][0]['items'][0]['name']='rewritten'
                with self.assertRaisesRegex(RuntimeError,'protected native state'):hooks.verify_addition(before,changed,self.spec,prepared,'hook',1)


class NativeHookReadbackTests(unittest.TestCase):
    def setUp(self):
        fixture=json.loads((ROOT/'tests/fixtures/filmcraft-hook-native.json').read_text())
        self.native=fixture['native'];self.spec=fixture['spec'];self.prepared=fixture['prepared']

    def verify(self, data):
        return hooks.verify_native(data,self.spec,self.prepared,254016000000//25)

    def test_actual_saved_native_text_and_boxes_are_editable(self):
        self.assertEqual(self.verify(self.native)['status'],'NATIVE_HOOK_CONTRACT_VALID')
        self.assertEqual(self.verify(self.native)['intervals'],2)

    def test_changes_to_text_shape_timing_and_visibility_refuse(self):
        for change in ['text','radius','opacity','time','shadow','font','track','animation','layer-order','styled-runs','responsive']:
            with self.subTest(change=change):
                data=copy.deepcopy(self.native);track=data['project']['items']['1']['kind']['Sequence']['video_tracks'][0];item=track['items'][0]
                shape=item['effects'][3]['params'];text=item['effects'][5]['params']
                if change=='text':text['text']['value']={'Text':'Unsupported claim'}
                elif change=='radius':shape['corner_radius']['value']={'Float':0}
                elif change=='opacity':item['effects'][1]['params']['opacity']['value']={'Float':50}
                elif change=='time':item['duration']+=254016000000//25
                elif change=='shadow':text['shadow']['value']={'Bool':True}
                elif change=='font':text['font']['value']={'Text':'Substitute'}
                elif change=='track':track['muted']=True
                elif change=='animation':text['position']['keyframes']=[{'time':0}]
                elif change=='styled-runs':item['effects'][5]['layer']={'runs':[{'size':1}]}
                elif change=='responsive':item['graphic']={'roll':{'speed':20}}
                else:item['effects'][3],item['effects'][5]=item['effects'][5],item['effects'][3]
                with self.assertRaises(RuntimeError):self.verify(data)


if __name__=='__main__':unittest.main()
