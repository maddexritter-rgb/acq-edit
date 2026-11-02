import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'distribution/skills/_shared'))
from premiere_bridge import StdioMcp

class SourceReadTest(unittest.TestCase):
    def test_dense_project_read_has_one_bounded_request(self):
        c=StdioMcp.__new__(StdioMcp);c.timeout=30;calls=[]
        c.request=lambda method,args,timeout=None:calls.append((method,args,timeout)) or {'done':True}
        self.assertEqual(c.call('inspect_project_sequences',{'project_path':'/p.prproj'}),{'done':True})
        self.assertEqual(len(calls),1);self.assertEqual(calls[0][2],300)
        c.call('lab_snapshot',{});self.assertIsNone(calls[1][2])
    def test_timeout_does_not_resubmit_or_hide_uncertainty(self):
        c=StdioMcp.__new__(StdioMcp);c.timeout=30;calls=[]
        def fail(*args,**kwargs):calls.append(args);raise TimeoutError('pending')
        c.request=fail
        with self.assertRaises(TimeoutError):c.call('inspect_project_sequences',{})
        self.assertEqual(len(calls),1)

if __name__=='__main__':unittest.main()
