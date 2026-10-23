#!/usr/bin/env python3
"""Conform an accepted draw-on into exact-length picture plates. No generation or upload."""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import subprocess


def probe(path):
    data = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_frames',
        '-show_entries', 'stream=width,height,avg_frame_rate,nb_read_frames,duration,codec_name,pix_fmt',
        '-of', 'json', str(path)], text=True))
    if not data.get('streams'):
        raise ValueError('Input has no video stream')
    return data['streams'][0]


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    ap.add_argument('--alpha-output', type=Path)
    ap.add_argument('--fps', required=True, help='Destination FPS, e.g.30 or30000/1001')
    ap.add_argument('--frames', required=True, type=int)
    ap.add_argument('--canvas', nargs=2, type=int, default=[1080, 1920], metavar=('W', 'H'))
    ap.add_argument('--box', nargs=4, type=int, default=[1000, 800, 40, 260], metavar=('W', 'H', 'X', 'Y'))
    ap.add_argument('--speed', type=float, help='Explicit reveal speed; default fits the source plus hold')
    ap.add_argument('--hold', type=float, default=0.6, help='Minimum finished-drawing hold in seconds')
    a = ap.parse_args()
    fps = Fraction(a.fps)
    if fps <= 0 or a.frames <= 0:
        ap.error('FPS and frame count must be positive')
    duration = a.frames / float(fps)
    if not 0 <= a.hold < duration:
        ap.error('Hold must be nonnegative and shorter than the target duration')
    cw, ch = a.canvas
    bw, bh, bx, by = a.box
    if min(cw, ch, bw, bh) <= 0 or min(bx, by) < 0 or bx + bw > cw or by + bh > ch:
        ap.error('Diagram box must fit inside a positive canvas')
    if cw % 2 or ch % 2:
        ap.error('Canvas dimensions must be even')
    src = a.input.expanduser().resolve(strict=True)
    outputs = [a.output.expanduser().resolve()] + ([a.alpha_output.expanduser().resolve()] if a.alpha_output else [])
    if len(set(outputs)) != len(outputs) or src in outputs:
        ap.error('Input, white plate and alpha plate must use different paths')
    for p in outputs:
        if p.exists() or p.with_suffix(p.suffix + '.json').exists():
            ap.error(f'Refusing to overwrite an existing plate or receipt: {p}')
        if p.suffix.lower() != '.mov':
            ap.error('ProRes output must use .mov')
    info = probe(src)
    source_fps = Fraction(info['avg_frame_rate'])
    source_frames = int(info['nb_read_frames'])
    source_duration = source_frames / float(source_fps)
    speed = a.speed if a.speed is not None else max(1.0, source_duration / (duration - a.hold))
    if speed <= 0 or source_duration / speed > duration - a.hold + 1 / float(fps):
        ap.error('This speed would truncate the animation or requested final hold')
    ratio = min(bw / info['width'], bh / info['height'])
    fw = max(2, int(info['width'] * ratio) // 2 * 2)
    fh = max(2, int(info['height'] * ratio) // 2 * 2)
    px, py = bx + (bw - fw) // 2, by + (bh - fh) // 2
    input_hash = digest(src)
    for i, out in enumerate(outputs):
        alpha = i == 1
        out.parent.mkdir(parents=True, exist_ok=True)
        vf = f'setpts=(PTS-STARTPTS)/{speed:.12g},scale={fw}:{fh}:flags=lanczos'
        if alpha:
            vf += ',format=rgba,colorkey=0xFFFFFF:0.12:0.06'
        vf += f',pad={cw}:{ch}:{px}:{py}:color=' + ('black@0' if alpha else 'white')
        vf += f',setsar=1,fps={fps},tpad=stop_mode=clone:stop_duration={duration:.12g}'
        cmd = ['ffmpeg', '-hide_banner', '-v', 'error', '-nostdin', '-n', '-i', str(src),
               '-vf', vf, '-frames:v', str(a.frames), '-an', '-c:v', 'prores_ks',
               '-profile:v', '4' if alpha else '3', '-pix_fmt', 'yuva444p10le' if alpha else 'yuv422p10le',
               '-threads', '2', str(out)]
        subprocess.run(cmd, check=True)
        got = probe(out)
        if (got['width'], got['height'], int(got['nb_read_frames']), Fraction(got['avg_frame_rate'])) != (cw, ch, a.frames, fps):
            raise RuntimeError(f'Plate verification failed: {out}')
        receipt = {'input': str(src), 'input_sha256': input_hash, 'input_probe': info,
                   'output': str(out), 'output_sha256': digest(out), 'output_probe': got,
                   'frames': a.frames, 'fps': str(fps), 'speed': speed, 'alpha': alpha,
                   'box': a.box, 'command': cmd}
        out.with_suffix(out.suffix + '.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps({'file': str(out), 'frames': a.frames, 'fps': str(fps), 'speed': speed, 'alpha': alpha}))


if __name__ == '__main__':
    main()
