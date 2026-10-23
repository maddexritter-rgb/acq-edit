"""Archive contract checks; native host/render acceptance is documented separately."""
import copy,sys,tempfile,unittest,zipfile
from fractions import Fraction
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'python'))
from resolve_precision import patch_checkpoint,native_time,read_time
from common import sha
class ResolvePrecisionTests(unittest.TestCase):
 def fixture(self,root):
  root=Path(root);source=root/'frame.drt';target=root/'sample.drt'
  xml=b'''<?xml version="1.0"?><!----><!--DbAppVer="21.1.1.0010" DbPrjVer="17"--><Sm2SequenceContainer><ListMgt::LmVersionTable>preserve native syntax</ListMgt::LmVersionTable><AudioTrackVec><Sm2TiAudioClip DbId="a"><Start>0</Start><In/><Duration>25</Duration><MediaFilePath>/source/played.wav</MediaFilePath><FieldsBlob>unchanged</FieldsBlob></Sm2TiAudioClip><Sm2TiAudioClip DbId="b"><Start>25</Start><In>50</In><Duration>25</Duration><MediaFilePath>/source/played.wav</MediaFilePath></Sm2TiAudioClip></AudioTrackVec></Sm2SequenceContainer>'''
  with zipfile.ZipFile(source,'w') as z:z.writestr('project.xml',b'unchanged project');z.writestr('SeqContainer/one.xml',xml)
  spec={'fps':{'numerator':25,'denominator':1},'sampleRate':48000,'sources':[{'id':'audio','path':'/source/played.wav'}],'cuts':[{'id':'a','audioSourceId':'audio','sourceInFrame':0,'recordFrame':0,'frames':25,'audioInSample':11,'audioSamples':48006,'audioRecordSample':11},{'id':'b','audioSourceId':'audio','sourceInFrame':50,'recordFrame':25,'frames':25,'audioInSample':96017,'audioSamples':47972,'audioRecordSample':48017}]}
  return source,target,spec,xml
 def test_preserves_archive_and_only_changes_exact_timing(self):
  with tempfile.TemporaryDirectory() as root:
   source,target,spec,xml=self.fixture(root);before=sha(source);result=patch_checkpoint(source,target,spec);self.assertEqual(before,sha(source));self.assertEqual(len(result['cuts']),2)
   with zipfile.ZipFile(target) as z:
    self.assertEqual(z.read('project.xml'),b'unchanged project');actual=z.read('SeqContainer/one.xml')
    expected=xml.replace(b'<Start>0</Start>',('<Start>'+native_time(11,Fraction(25),48000)+'</Start>').encode()).replace(b'<In/>',('<In>'+native_time(11,Fraction(25),48000)+'</In>').encode()).replace(b'<Duration>25</Duration>',('<Duration>'+native_time(48006,Fraction(25),48000)+'</Duration>').encode(),1).replace(b'<Start>25</Start>',('<Start>'+native_time(48017,Fraction(25),48000)+'</Start>').encode()).replace(b'<In>50</In>',('<In>'+native_time(96017,Fraction(25),48000)+'</In>').encode()).replace(b'<Duration>25</Duration>',('<Duration>'+native_time(47972,Fraction(25),48000)+'</Duration>').encode(),1)
    self.assertEqual(actual,expected)
   with self.assertRaisesRegex(RuntimeError,'checkpoint exists'):patch_checkpoint(source,target,spec)
 def test_sample_values_roundtrip_at_native_precision(self):
  for sample in [0,11,48017,96017,143989,48000*60*60*3+17]:
   with self.subTest(sample=sample):self.assertLess(abs(read_time(native_time(sample,Fraction(25),48000))*1920-sample),.001)
  for value in [-1,1.5,True]:
   with self.assertRaisesRegex(RuntimeError,'sample count'):native_time(value,Fraction(25),48000)
 def test_refuses_changed_source_or_geometry_before_writing(self):
  for change in ['source','geometry','count']:
   with tempfile.TemporaryDirectory() as root:
    source,target,spec,_=self.fixture(root)
    if change=='source':spec['sources'][0]['path']='/other.wav'
    if change=='geometry':spec['cuts'][1]['sourceInFrame']=51
    if change=='count':spec['cuts'].pop()
    with self.assertRaises(RuntimeError):patch_checkpoint(source,target,spec)
    self.assertFalse(target.exists())
 def test_refuses_new_archive_schema_and_ambiguous_fields(self):
  for change in ['version','field']:
   with tempfile.TemporaryDirectory() as root:
    source,target,spec,xml=self.fixture(root);bad=Path(root)/'unknown.drt'
    xml=xml.replace(b'21.1.1.0010',b'21.2.0.0001') if change=='version' else xml.replace(b'<In/>',b'<In/><In/>')
    with zipfile.ZipFile(bad,'w') as z:z.writestr('SeqContainer/one.xml',xml)
    with self.assertRaises(RuntimeError):patch_checkpoint(bad,target,spec)
    self.assertFalse(target.exists())
if __name__=='__main__':unittest.main()
