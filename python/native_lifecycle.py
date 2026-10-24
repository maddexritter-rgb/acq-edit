"""Record FilmCraft child identity without replacing the canonical transport."""
import json
import os
import uuid
from pathlib import Path


def tracked_client(base):
    class TrackedClient(base):
        def __init__(self,*args,**kwargs):
            directory=os.environ.get('ACQ_EDIT_NATIVE_OPERATION_DIR')
            self._operation_file=None
            if directory:
                self._operation_file=Path(directory)/'children'/(str(uuid.uuid4())+'.json')
                self._operation={'operationId':os.environ['ACQ_EDIT_NATIVE_OPERATION_ID'],'kind':'filmcraft','pid':None,'pending':True}
                self._write_operation()
            try:super().__init__(*args,**kwargs)
            finally:
                if self._operation_file and hasattr(self,'p'):
                    self._operation.update(pid=self.p.pid,pending=False)
                    self._write_operation()

        def _write_operation(self):
            target=self._operation_file;target.parent.mkdir(parents=True,exist_ok=True)
            temporary=target.with_suffix('.'+str(uuid.uuid4())+'.pending')
            with temporary.open('x') as stream:json.dump(self._operation,stream)
            os.replace(temporary,target)

        def close(self):
            try:return super().close()
            finally:
                if self._operation_file and hasattr(self,'p'):
                    self._operation.update(pid=self.p.pid,pending=False,exitCode=self.p.poll())
                    self._write_operation()
    return TrackedClient
