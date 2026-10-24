import pathlib,tempfile,unittest,sys,zipfile,copy
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'python'))
from resolve_music_archive import patch_checkpoint
from resolve_precision import SCHEMA_VERSION

class ResolveMusicArchiveTests(unittest.TestCase):
 def fixture(self,root):
  old={'fps':{'numerator':25,'denominator':1},'sampleRate':48000,'sources':[{'id':'a','path':'/old.wav'}],'audio':{'music':[{'sourceId':'a','startFrame':5,'sourceInSample':48000,'samples':28800}]}}
  new=copy.deepcopy(old);new['sources']=[{'id':'b','path':'/new.wav'}];new['audio']['music'][0]['sourceId']='b'
  def clip(ref,path):return b'<Sm2TiAudioClip DbId="clip"><Name>Manual</Name><Start>5</Start><Duration>15|000000000000e03c</Duration><In>25</In><MediaRef>'+ref+b'</MediaRef><MediaFilePath>'+path+b'</MediaFilePath><EffectFiltersBA>protected</EffectFiltersBA></Sm2TiAudioClip>'
  original=clip(b'old',b'/old.wav');replacement=clip(b'new',b'/new.wav')
  def track(block):return b'<Sm2TiTrack DbId="track"><Items>'+block+b'</Items></Sm2TiTrack>'
  pool=SCHEMA_VERSION+b'<Sm2MpFolder DbId="folder"><MediaVec><Original>unchanged</Original></MediaVec></Sm2MpFolder>'
  donor=SCHEMA_VERSION+b'<Sm2MpFolder DbId="donor-folder"><MediaVec><Sm2MpAudioClip DbId="new"><MpFolder>donor-folder</MpFolder><FieldsBlob>native-media-bytes</FieldsBlob></Sm2MpAudioClip></MediaVec></Sm2MpFolder>'
  seq=SCHEMA_VERSION+b'<AudioTrackVec>'+track(b'<Dialogue>protected</Dialogue>')+track(original)+b'</AudioTrackVec><Video>protected</Video>'
  donor_seq=SCHEMA_VERSION+b'<AudioTrackVec>'+track(replacement)+b'</AudioTrackVec>'
  for name,sequence,folder in [('parent',seq,pool),('donor',donor_seq,donor)]:
   with zipfile.ZipFile(root/(name+'.drt'),'w') as z:
    z.writestr('SeqContainer/native.xml',sequence);z.writestr('MediaPool/Master/MpFolder.xml',folder);z.writestr('project.xml',SCHEMA_VERSION+b'<Project>unchanged</Project>')
  return old,new,original,seq,pool
 def test_only_selected_binding_and_new_media_descriptor_change(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);old,new,original,seq,pool=self.fixture(root);before=(root/'parent.drt').read_bytes();proof=patch_checkpoint(root/'parent.drt',root/'donor.drt',root/'new.drt',old,new,[0])
   with zipfile.ZipFile(root/'new.drt') as z:
    expected=seq.replace(b'<MediaRef>old</MediaRef>',b'<MediaRef>new</MediaRef>').replace(b'/old.wav',b'/new.wav');self.assertEqual(z.read('SeqContainer/native.xml'),expected);self.assertIn(b'<MpFolder>folder</MpFolder>',z.read('MediaPool/Master/MpFolder.xml'));self.assertEqual(z.read('project.xml'),SCHEMA_VERSION+b'<Project>unchanged</Project>')
   self.assertEqual((root/'parent.drt').read_bytes(),before);self.assertEqual(proof['bindings'],[{'musicIndex':0,'oldMediaRef':'old','newMediaRef':'new'}])
   with self.assertRaisesRegex(RuntimeError,'exists'):patch_checkpoint(root/'parent.drt',root/'donor.drt',root/'new.drt',old,new,[0])
 def test_changed_source_or_timing_refused_without_output(self):
  for change in ['source','timing']:
   with self.subTest(change=change),tempfile.TemporaryDirectory() as tmp:
    root=pathlib.Path(tmp);old,new,*_=self.fixture(root)
    if change=='source':old['sources'][0]['path']='/unexpected.wav'
    else:new['audio']['music'][0]['samples']+=1920
    with self.assertRaises(RuntimeError):patch_checkpoint(root/'parent.drt',root/'donor.drt',root/'new.drt',old,new,[0])
    self.assertFalse((root/'new.drt').exists())
 def test_unknown_archive_version_refused(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=pathlib.Path(tmp);old,new,*_=self.fixture(root)
   with zipfile.ZipFile(root/'unqualified.drt','w') as z:z.writestr('SeqContainer/native.xml',b'DbAppVer="new"')
   with self.assertRaisesRegex(RuntimeError,'version'):patch_checkpoint(root/'unqualified.drt',root/'donor.drt',root/'new.drt',old,new,[0])
   self.assertFalse((root/'new.drt').exists())

if __name__=='__main__':unittest.main()
