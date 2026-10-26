#!/usr/bin/env python3
"""Batch source-bound composition evidence. Does not approve or choose crops.

One decode per view, selected at the composition profile's cadence, instead of
one seek per image or running a detector on every unused frame. Camera choices,
sync, ROI and final complete-head calibration remain owning-skill decisions.
"""
import argparse
import concurrent.futures
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.local/skills/horizontal-to-vertical/scripts'))


def sample_frames(count, fps, gap=.51):
    if count < 1 or fps <= 0 or gap <= 0:
        raise ValueError('Positive duration, fps and sample interval required')
    step = max(1, math.floor(fps * gap))
    return sorted(set(range(0, count, step)) | {0, count // 2, count - 1})


def collect(plan, views, output, workers=1):
    import cv2
    import numpy as np
    from premiere_native_reframe import detector_for, select_face, MODEL
    cv2.setNumThreads(1)
    output.mkdir(parents=True, exist_ok=False)
    sources = {s['id']: s for s in plan['sources']}
    fps = plan['fps']['numerator'] / plan['fps']['denominator']
    cuts = {c['id']: c for c in plan['cuts']}

    def one(view):
        cut = cuts[view['cutId']]
        source = sources[view['sourceId']]
        start = view['inFrame']
        evidence_frames = sample_frames(cut['frames'], fps)
        indices = list(range(cut['frames'])) if view.get('tracking') else evidence_frames
        detector, dw, dh = detector_for(view['sourceWidth'], view['sourceHeight'])
        select = '+'.join(f'eq(n\\,{n})' for n in indices)
        cmd = ['ffmpeg', '-v', 'error', '-threads', '2', '-ss', f'{start/fps:.9f}',
               '-i', source['path'], '-an', '-vf', f'select={select},scale={dw}:{dh}',
               '-frames:v', str(len(indices)), '-fps_mode', 'passthrough',
               '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-']
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        samples, dense, previous = [], [], None
        try:
            for n in indices:
                data = proc.stdout.read(dw * dh * 3)
                if len(data) != dw * dh * 3:
                    raise RuntimeError(f'Incomplete source decode: {view["cutId"]} frame {n}')
                frame = np.frombuffer(data, np.uint8).reshape((dh, dw, 3))
                _, faces = detector.detect(frame)
                face = select_face(faces, previous, view['roi'], dw, dh)
                if face is not None:
                    previous = face[0]
                sx, sy = view['sourceWidth'] / dw, view['sourceHeight'] / dh
                measured = None if face is None else [float(face[0])*sx, float(face[1])*sy,
                            float(face[2])*sx, float(face[3])*sy, float(face[4])]
                if view.get('tracking'):
                    dense.append(measured)
                if n in evidence_frames:
                    path = output / f'{view["cutId"]}-{view["role"]}-{n:04d}.jpg'
                    if not cv2.imwrite(str(path), frame):
                        raise RuntimeError('Failed to write source evidence')
                    samples.append({'frame': n, 'face': measured, 'evidence': {'path': str(path),
                        'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}})
            error = proc.stderr.read().decode()
            if proc.wait() != 0:
                raise RuntimeError(error)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
            proc.stdout.close()
            proc.stderr.close()
        print(f'{view["cutId"]}/{view["role"]}: {len(samples)} source samples', flush=True)
        return {**view, 'sourceRange': {'sourceId': source['id'], 'sha256': source['sha256'],
                'inFrame': start, 'frames': cut['frames']}, 'samples': samples, 'denseFaces': dense}

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(one, views))
    result = {'schema': 'acq-edit/composition-samples-v1',
              'status': 'source-evidence-prepared-not-visually-reviewed',
              'detectorModelSha256': hashlib.sha256(MODEL.read_bytes()).hexdigest(),
              'planSha256': hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest(),
              'items': rows}
    (output / 'observations.json').write_text(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--views', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--workers', type=int, choices=(1, 2), default=1)
    args = parser.parse_args()
    collect(json.loads(args.plan.read_text()), json.loads(args.views.read_text()),
            args.output.resolve(), args.workers)
