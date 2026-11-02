import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from premiere_panels import request,verify,reconcile_caption_copy

class NativePanels(unittest.TestCase):
 def test_caption_copy_rebinds_only_after_full_native_panel_verification(self):
  spec,cut,entry,project,links=self.fixture();original=copy.deepcopy(entry)
  project['project_path']='/captioned.prproj';project['active_sequence_id']='captioned-master'
  project['sequences'][-1]['sequence_id']='captioned-master'
  for link in links.values():link['project_path']='/captioned.prproj'
  receipt={'target':'/captioned.prproj','sequence_uid':'captioned-master','insertion':{'sequence_uid':'master','originals_retained':True}}
  rebound=reconcile_caption_copy(spec,cut,entry,project,links,receipt)
  self.assertEqual(entry,original);self.assertEqual(rebound['result']['sequence_id'],'captioned-master')
  links['panel0']['items'][0]['item']['media_path']='/other.mov'
  with self.assertRaises(RuntimeError):reconcile_caption_copy(spec,cut,entry,project,links,receipt)
 def fixture(self):
  cut={'id':'cut','recordFrame':0,'frames':2};panels=[]
  for i in range(2):panels.append({'sourceRange':{'sourceId':str(i),'sha256':'hash'+str(i),'inFrame':10+i,'frames':2},'rect':dict(x=0,y=i*960,width=1080,height=960),'crop':dict(mode='tracked-crop',sourceWidth=1920,sourceHeight=1080,width=1080,height=960,y=60,xByFrame=[400,401])})
  spec=dict(width=1080,height=1920,fps={'numerator':24000,'denominator':1001},sources=[dict(id=str(i),sha256='hash'+str(i),path='/source'+str(i)+'.mov') for i in range(2)],framing={'shots':{'cut':{'mode':'panel-layout','panels':panels}}})
  r=request(spec,cut,{'0':'original0','1':'original1'},'Split');duration=r['end_ticks'];sequences=[];pins=[];links={}
  def components(scale,pos,keys=None):
   motion=[{'name':k,'value':v} for k,v in [('Position',pos),('Scale',scale),('Rotation',0),('Anchor Point',[.5,.5]),('Crop Left',0),('Crop Top',0),('Crop Right',0),('Crop Bottom',0)]]
   if keys:motion[3]['keys']=keys
   return [{'matchName':'AE.ADBE Opacity','properties':[dict(name='Opacity',value=100)]},{'matchName':'AE.ADBE Motion','properties':motion}]
  for i,p in enumerate(r['panels']):
   sid='panel'+str(i);item=dict(id='camera'+str(i),name='source'+str(i),sourceId='subclip'+str(i),start='0',end=duration,inPoint=p['source_in_ticks'],outPoint=p['source_out_ticks'],speed=1,disabled=False,components=components(p['scale'],[.5,.5],[dict(ticks=str(int(p['source_in_ticks'])+j*int(r['frame_ticks'])),value=k) for j,k in enumerate(p['anchor_keys'])]))
   sequences.append(dict(sequence_id=sid,name='Split_PANEL_'+str(i),snapshot={'settings':dict(videoFrameWidth=1080,videoFrameHeight=960,videoFrameRate={'ticks':r['frame_ticks']}),'tracks':[dict(kind=0,index=0,muted=False,clips=[item]),dict(kind=1,index=0,muted=False,clips=[])]}))
   pins.append(dict(sequence_id=sid,picture_item_id=item['id']))
   links[sid]=dict(project_path='/project.prproj',sequence_id=sid,verification='stable_native_panel_sources',items=[dict(kind='video',item=dict(node_id=item['id'],media_path=p['media_path'],offline=False,speed_reversed=False,is_sequence=False))])
  placements=[];tracks=[]
  for i in range(3):
   panel=1 if i==0 else 0;item=dict(id='nest'+str(i),name='Split_PANEL_'+str(panel),sourceId='seqsource'+str(panel),start='0',end=duration,inPoint='0',outPoint=duration,speed=1,disabled=False,components=components(115 if i==1 else 100,[.5,.75 if i==0 else .25]))
   if i==1:item['components'].append(dict(matchName='AE.ADBE Drop Shadow',properties=[dict(name=k,value=v) for k,v in {'Opacity':98,'Direction':180,'Distance':49.700008392334,'Softness':150,'Shadow Only':True}.items()]))
   tracks.append(dict(kind=0,index=i+1,muted=False,clips=[item]));placements.append(dict(node_id=item['id'],source_id=item['sourceId'],sequence_id='panel'+str(panel)))
  sequences.append(dict(sequence_id='master',name='Master',snapshot={'tracks':tracks}));project=dict(project_path='/project.prproj',active_sequence_id='master',sequences=sequences)
  entry=dict(cutId='cut',request=r,result=dict(project_path='/project.prproj',sequence_id='master',panels=pins,placements=placements))
  return spec,cut,entry,project,links
 def test_valid_dense_independent_panels(self):self.assertEqual(verify(*self.fixture())['keys'],4)
 def test_source_file_substitution_fails(self):
  args=self.fixture();args[4]['panel0']['items'][0]['item']['media_path']='/flattened.mp4'
  with self.assertRaisesRegex(RuntimeError,'flattened'):verify(*args)
 def test_lost_key_fails(self):
  args=self.fixture();args[3]['sequences'][0]['snapshot']['tracks'][0]['clips'][0]['components'][1]['properties'][3]['keys'].pop()
  with self.assertRaisesRegex(RuntimeError,'dense'):verify(*args)
 def test_frame_rounding_fails(self):
  args=self.fixture();args[3]['sequences'][0]['snapshot']['tracks'][0]['clips'][0]['outPoint']=str(int(args[2]['request']['panels'][0]['source_out_ticks'])-1)
  with self.assertRaisesRegex(RuntimeError,'clocks'):verify(*args)
 def test_duplicate_audio_fails(self):
  args=self.fixture();args[3]['sequences'][-1]['snapshot']['tracks'].append(dict(kind=1,index=1,clips=[dict(sourceId='seqsource0')]))
  with self.assertRaisesRegex(RuntimeError,'audio remains'):verify(*args)
 def test_shadow_only_and_link_required(self):
  args=self.fixture();args[3]['sequences'][-1]['snapshot']['tracks'][1]['clips'][0]['components'][-1]['properties'][-1]['value']=False
  with self.assertRaisesRegex(RuntimeError,'shadow-only'):verify(*args)
 def test_changed_camera_plan_fails(self):
  args=self.fixture();args[0]['framing']['shots']['cut']['panels'][0]['sourceRange']['inFrame']+=1
  with self.assertRaisesRegex(RuntimeError,'frozen'):verify(*args)
 def test_panel_audio_fails(self):
  args=self.fixture();args[3]['sequences'][0]['snapshot']['tracks'][1]['clips']=[{}]
  with self.assertRaisesRegex(RuntimeError,'duplicated audio'):verify(*args)
if __name__=='__main__':unittest.main()
