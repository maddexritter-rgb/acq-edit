import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from native_lifecycle import tracked_client


class NativeLifecycleTests(unittest.TestCase):
    def test_records_child_even_when_initialization_fails_after_spawn(self):
        class Transport:
            def __init__(self):
                self.p=type('Child',(),{'pid':12345})();raise RuntimeError('MCP initialize failed')
        with tempfile.TemporaryDirectory() as root,patch.dict(os.environ,{'ACQ_EDIT_NATIVE_OPERATION_DIR':root,'ACQ_EDIT_NATIVE_OPERATION_ID':'operation'}):
            with self.assertRaisesRegex(RuntimeError,'initialize failed'):tracked_client(Transport)()
            receipt=json.loads(next((Path(root)/'children').glob('*.json')).read_text())
            self.assertEqual(receipt,{'operationId':'operation','kind':'filmcraft','pid':12345,'pending':False})

    def test_records_exit_and_retains_unknown_launch_without_claiming_termination(self):
        class Transport:
            def __init__(self):self.p=type('Child',(),{'pid':12345,'poll':lambda _:0})()
            def close(self):return 'closed'
        class Unknown:
            def __init__(self):raise RuntimeError('unrecorded launch')
        with tempfile.TemporaryDirectory() as root,patch.dict(os.environ,{'ACQ_EDIT_NATIVE_OPERATION_DIR':root,'ACQ_EDIT_NATIVE_OPERATION_ID':'operation'}):
            client=tracked_client(Transport)();self.assertEqual(client.close(),'closed')
            with self.assertRaises(RuntimeError):tracked_client(Unknown)()
            rows=[json.loads(p.read_text()) for p in (Path(root)/'children').glob('*.json')]
            self.assertEqual(len(rows),2);self.assertTrue(any(r.get('exitCode')==0 for r in rows));self.assertTrue(any(r['pending'] and r['pid'] is None for r in rows))


if __name__=='__main__':unittest.main()
