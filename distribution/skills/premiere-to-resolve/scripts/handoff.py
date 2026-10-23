#!/usr/bin/env python3
"""One-shot saved Premiere/XML -> audited native Resolve handoff.

Run in Resolve's scripting Python. Requires an existing genuine XML export and
saved project. This command never uses or opens Premiere and never retries imports.
"""
import argparse
import json
import pathlib
import sys

# ResolvePython does not populate sys.path with the launched script directory.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from prepare import prepare
from audit_prproj import write_audit
from convert import require, run


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--xml', required=True); p.add_argument('--project', required=True)
    p.add_argument('--project-name', required=True); p.add_argument('--expected-current-project', required=True)
    p.add_argument('--work', required=True); p.add_argument('--output', required=True)
    p.add_argument('--path-map', help='Exact original to verified local media JSON mapping')
    a = p.parse_args()
    work = pathlib.Path(a.work).resolve()
    require(not work.exists(), 'Work directory exists; inspect the checkpoint, do not replay')
    require(not pathlib.Path(a.output).exists(), 'Output already exists')
    require(pathlib.Path(a.project).is_file() and pathlib.Path(a.xml).is_file(), 'Saved project and native XML export required')
    mapping = json.loads(pathlib.Path(a.path_map).read_text()) if a.path_map else None
    work.mkdir(parents=True)
    state = {'phase': 'preparing', 'project': str(pathlib.Path(a.project).resolve()), 'xml': str(pathlib.Path(a.xml).resolve())}
    def record():
        temp = work / 'state.json.tmp'; temp.write_text(json.dumps(state, indent=2)); temp.replace(work / 'state.json')
    try:
        record()
        manifest = prepare(a.xml, work / 'prepared', mapping)
        state['phase'] = 'auditing'; record()
        receipt = work / 'native-audit.json'
        result = write_audit(a.project, manifest, receipt)
        require(result['passed'], 'Native audit failed: ' + json.dumps(result['errors'][:8]))
        state['phase'] = 'converting'; record()
        converted = run(manifest, receipt, a.project_name, a.expected_current_project, a.output, work / 'conversion')
        state.update(phase=converted['state'], output=converted['output']); record()
    except Exception as exc:
        state.update(failed_phase=state['phase'], phase='failed', error=str(exc)); record()
        raise


if __name__ == '__main__':
    main()
