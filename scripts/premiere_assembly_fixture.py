#!/usr/bin/env python3
"""Synthetic compiler replay fixture only. No editorial approval or Premiere calls."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
    return str(path)


def build(runtime, output):
    runtime, output = Path(runtime).resolve(), Path(output).resolve()
    fixtures = runtime / 'lab/runtime/fixtures'
    if not output.is_relative_to(fixtures) or output == fixtures:
        raise ValueError('Fixture must be a new child of this runtime fixture root')
    sys.path.insert(0, str(runtime / 'scripts'))
    from acq_edit_runtime import skill_scripts
    scripts = skill_scripts()
    sys.path.insert(0, str(scripts))
    from compile_assembly import compile_design
    import review_xml
    output.mkdir(parents=True, exist_ok=False)
    source = output / 'synthetic.mov'
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi', '-i',
                    'testsrc2=size=640x360:rate=25:duration=3', '-f', 'lavfi', '-i',
                    'sine=frequency=440:sample_rate=48000:duration=3', '-c:v', 'prores_ks',
                    '-profile:v', '0', '-c:a', 'pcm_s16le', '-shortest', str(source)], check=True)
    words = write(output / 'words.json', {'testFixture': True, 'words': [
        {'word': word, 'start': start, 'end': end, 'speaker': 'A'}
        for word, start, end in [('First', .1, .3), ('claim', .5, .8),
                                 ('discard', 1.3, 1.5), ('Complete', 2.1, 2.4), ('payoff', 2.5, 2.8)]]})
    selection = write(output / 'selection.json', {'schema': 'edit.assembly-selection/v2',
        'testFixture': 'Synthetic replay only; no authoring preflight or speech verification',
        'clips': [{'id': 'synthetic', 'media': str(source), 'source_words': words,
            'interaction_word_range': [0, 4], 'paper_cut': [
                {'word_range': [0, 1], 'action': 'KEEP'},
                {'word_range': [2, 2], 'action': 'CUT', 'reason': 'Synthetic omitted token'},
                {'word_range': [3, 4], 'action': 'KEEP'}],
            'speaker_roles': {'A': 'expert'}, 'payoff_speaker': 'A',
            'hook_word_range': [0, 0], 'reasoning_word_range': [1, 1], 'payoff_word_range': [3, 4]}]})
    # Replay mode is deliberately not first-time editorial authoring or a brain receipt.
    compiled = write(output / 'compiled.json', compile_design(Path(selection), check_templates=False))
    resolved = write(output / 'resolved.json', {'schema': 'edit.resolved-assembly/v1',
        'compiled_path': compiled, 'compiled_sha256': digest(compiled), 'clips': [
            {'id': 'synthetic', 'source_frames': [[0, 25], [50, 75]],
             'status': 'EDITOR_REVIEW', 'note': 'Synthetic tones and test picture; no actual speech.'}]})
    xml = output / 'assembly.xml'
    review_xml.build([], 'Synthetic compiler replay', xml, gap_frames=0, assemblies_path=Path(resolved))
    expected = xml.with_suffix('.expected.json')
    args = [str(xml), digest(xml), str(expected), digest(expected), str(fixtures),
            resolved, digest(resolved), '0']
    result = subprocess.run([sys.executable, '-B', str(runtime / 'scripts/validate-assembly-import.py'),
                             '--compiled', *args], check=True, capture_output=True, text=True)
    proof = json.loads(result.stdout)
    write(output / 'compiler-proof.json', proof)
    report = {'schema': 'acq-edit/premiere-assembly-fixture-v1', 'fixtureRoot': str(fixtures),
              'xml': str(xml), 'expected': str(expected), 'resolved': resolved,
              'validationArguments': args, 'sourceFrames': [[0, 25], [50, 75]],
              'nativeHostCalled': False, 'editorialApproved': False,
              'verification': proof['provenance']['verification']}
    write(output / 'fixture.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.runtime, args.output), indent=2))
