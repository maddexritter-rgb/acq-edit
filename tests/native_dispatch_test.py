"""Wrong project/engine or concurrent work must not load an editor integration."""
import fcntl
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
import native


class NativeDispatchTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup);self.root=Path(folder.name)
        (self.root/'10_WORK').mkdir()
        self.config=self.root/'config.json';self.config.write_text('{}')
        self.project=self.root/'project.json';self.project.write_text(json.dumps({'id':'fixture','root':str(self.root),'backend':'resolve'}))
        self.packet=self.root/'10_WORK/packet.json';self.packet.write_text('{}')

    def call(self,action,backend='resolve',packet=None):
        return native.execute(action,backend,self.config,self.project,packet or self.packet)

    def test_backend_mismatch_never_imports_an_adapter(self):
        with patch.object(native.importlib,'import_module') as load:
            for backend in ['filmcraft','premiere']:
                for action in ['compile','captions','inspect','open','build','revise','render']:
                    with self.subTest(backend=backend,action=action),self.assertRaisesRegex(RuntimeError,'Backend is fixed'):self.call(action,backend)
            load.assert_not_called()
        self.assertFalse((self.root/'10_WORK/native.lock').exists())

    def test_outside_packet_and_busy_project_never_initialize_an_adapter(self):
        with patch.object(native.importlib,'import_module') as load:
            with self.assertRaisesRegex(RuntimeError,'outside'):self.call('build',packet=self.root.parent/'foreign-packet.json')
            with (self.root/'10_WORK/native.lock').open('a') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                with self.assertRaises(BlockingIOError):self.call('revise')
            load.assert_not_called()

    def test_native_call_imports_only_selected_adapter_under_project_lock(self):
        adapter=Mock();adapter.inspect.return_value={'selected':'resolve'}
        def factory(config):
            with (self.root/'10_WORK/native.lock').open('a') as lock:
                with self.assertRaises(BlockingIOError):fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            return adapter
        with patch.object(native.importlib,'import_module',return_value=types.SimpleNamespace(Adapter=factory)) as load:
            self.assertEqual(self.call('inspect'),{'selected':'resolve'});load.assert_called_once_with('resolve')
        adapter.inspect.assert_called_once_with(json.loads(self.project.read_text()),{})

    def test_shared_preparation_loads_no_native_adapter(self):
        compile_plan=Mock(return_value={'compiled':True});prepare_plan=Mock(return_value={'captions':True})
        with patch.dict(sys.modules,{'assembly_plan':types.SimpleNamespace(compile_plan=compile_plan),'caption_plan':types.SimpleNamespace(prepare_plan=prepare_plan)}),patch.object(native.importlib,'import_module') as load:
            self.assertEqual(self.call('compile'),{'compiled':True});self.assertEqual(self.call('captions'),{'captions':True});load.assert_not_called()


if __name__=='__main__':unittest.main()
