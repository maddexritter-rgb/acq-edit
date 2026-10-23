import unittest,tempfile,pathlib,sys,copy,json,concurrent.futures,time
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"scripts"))
import tracking_cache as tc
class CacheTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.t.name);self.media=self.root/'media';self.media.write_bytes(b'media');self.code=self.root/'code';self.code.write_text('1');self.item={'media_path':str(self.media),'source_in':0.,'source_out':1.};self.calls=0
 def tearDown(self):self.t.cleanup()
 def producer(self,item,preset,step):
  self.calls+=1;duration=item['source_out']-item['source_in'];return {'relative_times':[0,duration-1/30],'face_x':[.5,.5],'face_y':[.5,.5],'fps':30}
 def run_cache(self,item=None,preset=None):return tc.get_or_compute(item or self.item,preset or {'roi':[0,0,1,1]},.25,self.root/'cache',self.producer,[self.code])
 def test_hit(self):self.assertFalse(self.run_cache()[1]['hit']);self.assertTrue(self.run_cache()[1]['hit']);self.assertEqual(self.calls,1)
 def test_same_count_boundary_change(self):self.run_cache();self.assertFalse(self.run_cache({**self.item,'source_out':1.2})[1]['hit'])
 def test_same_count_reorder(self):
  a=self.run_cache()[1]['key'];b=self.run_cache({**self.item,'source_in':2.,'source_out':3.})[1]['key'];self.assertNotEqual(a,b)
 def test_source_same_size_mutation(self):self.run_cache();self.media.write_bytes(b'other');self.assertFalse(self.run_cache()[1]['hit'])
 def test_code_and_preset(self):self.run_cache();self.code.write_text('2');self.assertFalse(self.run_cache()[1]['hit']);self.assertFalse(self.run_cache(preset={'roi':[.1,0,1,1]})[1]['hit'])
 def test_corrupt_result(self):
  _,r=self.run_cache();p=pathlib.Path(r['path']);x=json.loads(p.read_text());x['result']['face_x'][0]=.2;p.write_text(json.dumps(x));self.assertFalse(self.run_cache()[1]['hit'])
 def test_parallel_same_key(self):
  with concurrent.futures.ThreadPoolExecutor(max_workers=4) as e:r=list(e.map(lambda _:self.run_cache(),range(4)))
  self.assertEqual(self.calls,1);self.assertEqual(sum(v[1]['hit'] for v in r),3)
 def test_failed_producer_never_publishes(self):
  def fail(*a):raise RuntimeError('interrupted')
  with self.assertRaises(RuntimeError):tc.get_or_compute(self.item,{},.25,self.root/'cache',fail,[self.code])
  self.assertFalse(list((self.root/'cache').glob('*.json')))
 def test_input_changes_during_compute(self):
  def mutate(*args):self.media.write_bytes(b'after');return self.producer(*args)
  with self.assertRaises(ValueError):tc.get_or_compute(self.item,{},.25,self.root/'cache',mutate,[self.code])
 def test_incomplete_coverage_rejected(self):
  with self.assertRaises(ValueError):tc.validate_result({'relative_times':[0,.5],'face_x':[.5,.5],'face_y':[.5,.5],'fps':30},1)
