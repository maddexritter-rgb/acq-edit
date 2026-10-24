"""Native Fusion transport and immutable Resolve archive insertion boundaries."""
import copy,json,sys,tempfile,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
from resolve_hook_archive import append_hook
from resolve_hooks import nodes,font_preflight,verify_comp
from common import sha
from unittest.mock import MagicMock


class ResolveHookTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  data=json.loads((ROOT/'tests/fixtures/filmcraft-hook-native.json').read_text());self.spec=data['spec'];self.prepared=data['prepared']
 def test_owner_geometry_maps_to_native_baseline_and_rounding(self):
  rows=nodes(self.spec,self.prepared);text=next(r for r in rows if r['type']=='TextPlus');interval=self.prepared['intervals'][0];native=interval['native_text'][0];style=interval['rendered_line_styles'][0]
  self.assertEqual(text['values']['StyledText'],native['text'])
  self.assertAlmostEqual(text['values']['Size']*.72*640,style['font_size_px'])
  self.assertAlmostEqual(text['values']['Center'][1]*640,interval['hook_bounds'][0]+native['baseline_px'][0])
  self.assertAlmostEqual((1-text['values']['Center'][2])*360,interval['hook_bounds'][1]+native['baseline_px'][1])
  self.assertEqual(text['values']['HorizontalLeftCenterRight'],-1)
  self.assertEqual(text['values']['VerticalTopCenterBottom'],1)
  self.assertEqual(rows[-1]['type'],'MediaOut');self.assertTrue(all(r['type'] in ['RectangleMask','Background','TextPlus','Merge','MediaOut'] for r in rows))
  gates=[tuple(r['gate']) for r in rows if 'gate' in r]
  self.assertEqual(set(gates),{tuple([1]*25+[0]*25),tuple([0]*25+[1]*25)})
  self.assertTrue(all(r['values']['MotionBlur']==0 for r in rows if 'gate' in r))
 def test_native_visibility_and_graph_changes_are_rejected(self):
  rows=nodes(self.spec,self.prepared);tools={};ports={}
  for row in rows:
   tool=MagicMock();tool.GetAttrs.return_value={'TOOLS_Name':row['name'],'TOOLS_RegID':row['type']};tools[row['name']]=tool
   ports[row['name']]={}
   for key in set(row['values'])|set(row.get('connections',{}))|({'Blend'} if 'gate' in row else set()):
    port=MagicMock();port.GetAttrs.return_value={'INPS_ID':key};port.GetExpression.return_value=None;port.GetConnectedOutput.return_value=None;ports[row['name']][key]=port
   tool.GetInputList.return_value=ports[row['name']]
   tool.GetInput.side_effect=lambda key,frame=None,row=row:row['gate'][frame] if key=='Blend' else row['values'][key]
   if 'gate' in row:
    name=row['name']+'Blend';spline=MagicMock();spline.GetAttrs.return_value={'TOOLS_Name':name,'TOOLS_RegID':'BezierSpline'}
    spline.GetKeyFrames.return_value={i:{1:v,'Flags':{'Linear':True}} for i,v in enumerate(row['gate'])};tools[name]=spline
  for row in rows:
   connections={**row.get('connections',{}),**({'Blend':row['name']+'Blend'} if 'gate' in row else {})}
   for key,source in connections.items():
    port=ports[row['name']][key];output=MagicMock();output.GetTool.return_value=tools[source];port.GetConnectedOutput.return_value=output
  comp=MagicMock();comp.GetToolList.return_value=tools;verify_comp(comp,self.spec,self.prepared)
  row=next(r for r in rows if 'gate' in r);port=ports[row['name']]['Blend'];port.GetExpression.return_value='1'
  with self.assertRaisesRegex(RuntimeError,'expression replaced'):verify_comp(comp,self.spec,self.prepared)
  port.GetExpression.return_value=None;spline=tools[row['name']+'Blend'];spline.GetKeyFrames.return_value[24][1]=0
  with self.assertRaisesRegex(RuntimeError,'value changed'):verify_comp(comp,self.spec,self.prepared)
  spline.GetKeyFrames.return_value[24][1]=1;ports[row['name']]['Foreground'].GetConnectedOutput.return_value=None
  with self.assertRaisesRegex(RuntimeError,'source differs'):verify_comp(comp,self.spec,self.prepared)
 def test_font_inventory_requires_exact_bytes_not_just_family(self):
  p=self.root/'font.ttf';p.write_bytes(b'fixture');prepared=copy.deepcopy(self.prepared)
  for interval in prepared['intervals']:
   for style in interval['rendered_line_styles']:style.update(font_sha256=sha(p),font_index=0)
  host=MagicMock();host.Fusion.return_value.FontManager.GetFontList.return_value={'Arial':{'Bold':str(p)}}
  font_preflight(host,prepared);p.write_bytes(b'other font version')
  with self.assertRaisesRegex(RuntimeError,'exact measured'):font_preflight(host,prepared)
 def archive(self,name,sequence):
  path=self.root/name;header=b'<!--DbAppVer="21.1.1.0010" DbPrjVer="17"-->'
  with zipfile.ZipFile(path,'x') as z:
   z.writestr('project.xml',header+b'<project><preserved/></project>');z.writestr('SeqContainer/sequence.xml',header+sequence)
   z.writestr('MediaPool/Master/MpFolder.xml',header+b'<pool><source/></pool>')
  return path
 def test_append_preserves_all_parent_bytes_and_clamps_only_owned_duration(self):
  parent=self.archive('parent.drt',b'<seq><VideoTrackVec><Element><Sm2TiTrack DbId="old"><Sequence>parent-id</Sequence><Items><custom/></Items></Sm2TiTrack></Element></VideoTrackVec><AudioTrackVec><audio-preserved/></AudioTrackVec></seq>')
  donor=self.archive('donor.drt',b'<seq><VideoTrackVec><Element><Sm2TiTrack DbId="new"><Sequence>donor-id</Sequence><Items><Sm2TiVideoClip DbId="hook"><PrettyType>Fusion Composition</PrettyType><Name>fixture</Name><Start>0</Start><In/><Duration>125</Duration><CompositionBA>opaque-native-graph</CompositionBA><MediaFilePath/></Sm2TiVideoClip></Items></Sm2TiTrack></Element></VideoTrackVec><AudioTrackVec/></seq>')
  target=self.root/'new.drt';pins=[sha(parent),sha(donor)];proof=append_hook(parent,donor,target,{'name':'fixture','intervals':[{'endFrame':126}]});self.assertEqual(proof['addedTrack'],2);self.assertEqual(pins,[sha(parent),sha(donor)])
  with zipfile.ZipFile(parent) as a,zipfile.ZipFile(target) as b:
   for entry in ['project.xml','MediaPool/Master/MpFolder.xml']:self.assertEqual(a.read(entry),b.read(entry))
   data=b.read('SeqContainer/sequence.xml');self.assertIn(b'<Duration>126</Duration>',data);self.assertNotIn(b'<Sequence>donor-id</Sequence>',data);self.assertIn(b'<audio-preserved/>',data)
  with self.assertRaisesRegex(RuntimeError,'exists'):append_hook(parent,donor,target,{'name':'fixture','intervals':[{'endFrame':126}]})
  with self.assertRaisesRegex(RuntimeError,'identity'):append_hook(parent,donor,self.root/'wrong.drt',{'name':'wrong','intervals':[{'endFrame':126}]})
 def test_foreign_version_or_source_media_is_not_a_native_hook_donor(self):
  p=self.root/'foreign.drt'
  with zipfile.ZipFile(p,'x') as z:z.writestr('project.xml',b'<foreign/>')
  with self.assertRaisesRegex(RuntimeError,'Unqualified'):append_hook(p,p,self.root/'out.drt',{'name':'fixture','intervals':[{'endFrame':126}]})


if __name__=='__main__':unittest.main()
