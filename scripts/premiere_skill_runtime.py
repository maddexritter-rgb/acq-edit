"""Installed beside Lab validators as acq_edit_runtime.py; no global skill fallback."""
from pathlib import Path
import sys


def skill_scripts():
    installed = Path(__file__).absolute()
    toolkit = installed.parents[3]
    expected = toolkit / '.local/premiere-agent/scripts/acq_edit_runtime.py'
    if installed != expected or any(path.is_symlink() for path in (toolkit, toolkit / '.local',
            installed.parents[1], installed.parent, installed)):
        raise RuntimeError('Premiere helper must run from its checkout-local installation')
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(toolkit / 'scripts'))
    from materialize import verify
    from prepare_premiere_runtime import verify_helpers
    verify_helpers(installed.parents[1], toolkit)
    verify(toolkit)
    return toolkit / '.local/skills/edit/scripts'
