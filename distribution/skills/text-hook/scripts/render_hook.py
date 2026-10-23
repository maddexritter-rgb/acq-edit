#!/usr/bin/env python3
"""Measure and render a supplied hook; never generate copy or infer scene geometry."""
import argparse
import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def probe(path):
    return json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)
    ]))


def norm(text):
    return ' '.join(text.split())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def overlaps(a, b):
    return a[0] < b[0]+b[2] and b[0] < a[0]+a[2] and a[1] < b[1]+b[3] and b[1] < a[1]+a[3]


def effective_safe_rect(m, width, height):
    """Intersect supplied geometry with the symmetric Instagram Reels text zone."""
    supplied = m['safe_rect']
    require(len(supplied) == 4 and all(math.isfinite(x) for x in supplied), 'Invalid safe rectangle')
    require(supplied[0] >= 0 and supplied[1] >= 0 and supplied[2] > 0 and supplied[3] > 0 and
            supplied[0]+supplied[2] <= width and supplied[1]+supplied[3] <= height,
            'Safe rectangle outside canvas')
    platform = m.get('delivery_platform', 'instagram_reels' if abs(width/height-9/16) < 0.01 else 'custom')
    require(platform in ('instagram_reels', 'custom'), 'Unsupported delivery platform')
    if platform == 'custom':
        return supplied
    require(abs(width/height-9/16) < 0.01, 'Instagram Reels safe zone requires a 9:16 canvas')
    side = math.ceil(width * .06)
    top = math.ceil(height * .14)
    bottom = math.floor(height * .65)
    x0, y0 = max(supplied[0], side), max(supplied[1], top)
    x1 = min(supplied[0]+supplied[2], width-side)
    y1 = min(supplied[1]+supplied[3], bottom)
    require(x1 > x0 and y1 > y0, 'Supplied safe rectangle misses Instagram Reels safe zone')
    return [x0, y0, x1-x0, y1-y0]


def fitted_font_size(m, width, height, common_size):
    """Apply the Reels size treatment after finding the largest readable fit."""
    platform = m.get('delivery_platform', 'instagram_reels' if abs(width/height-9/16) < 0.01 else 'custom')
    multiplier = m.get('font_size_multiplier', .85 if platform == 'instagram_reels' else 1.0)
    require(isinstance(multiplier, (int, float)) and math.isfinite(multiplier) and
            .5 <= multiplier <= 1.0, 'Invalid font size multiplier')
    floor = round((50 if m.get('style') else 70) * width / 1080)
    return max(floor, round(common_size * multiplier)), multiplier


def layout(m, width, height, caption_bottom=None, protected_rects=None, forced_size=None,
           caption_bounds=None):
    lines = m['display_lines']
    require(1 <= len(lines) <= 3 and all(isinstance(s, str) and s.strip() for s in lines), 'Use one to three nonempty display lines')
    require(norm(' '.join(lines)) == norm(m['selected_text']), 'Display lines must preserve selected text')
    require('.' not in m['selected_text'] and all('.' not in line for line in lines),
            'Displayed text hooks do not use periods; rewrite the wording without changing its claim')
    require(m['existing_hook'] == 'none', 'Existing hook requires a clean source or explicit native replacement')
    style = m.get('style')
    line_specs = None
    box_mode = (style or {}).get('box_mode', 'fitted_lines')
    require(box_mode in ('fitted_lines', 'unified'), 'Unsupported hook box mode')
    require('balance_line_widths' not in (style or {}),
            'Obsolete equal-width treatment; use short_line_width_ratio')
    short_line_width_ratio = (style or {}).get('short_line_width_ratio')
    if short_line_width_ratio is not None:
        require(isinstance(short_line_width_ratio, (int, float)) and
                not isinstance(short_line_width_ratio, bool) and
                math.isfinite(short_line_width_ratio) and .75 <= short_line_width_ratio <= .95,
                'Short line width ratio must be between .75 and .95')
        require(box_mode == 'fitted_lines' and len(lines) == 2,
                'Short line width ratio needs two fitted lines')
    if style:
        require(style.get('status') == 'approved' and style.get('approval_evidence'), 'Style is not user-approved')
        require(m.get('style_id') == style.get('id'), 'Style identity mismatch')
        require(style.get('case') in ('preserve', 'upper'), 'Unsupported style case')
        for color in ('foreground', 'background'):
            value = style.get(color, '')
            require(isinstance(value, str) and len(value) == 7 and value[0] == '#' and
                    all(c in '0123456789abcdefABCDEF' for c in value[1:]), 'Use opaque hex style colors')
        supplied = style.get('line_styles')
        require(supplied is None or (isinstance(supplied, list) and
                len(supplied) in (1, len(lines)) and all(isinstance(v, dict) for v in supplied)),
                'Style line_styles must cover the semantic display lines')
        line_specs = []
        for index, line in enumerate(lines):
            override = supplied[min(index, len(supplied)-1)] if supplied else {}
            spec = {key: override.get(key, style[key]) for key in ('font_path', 'foreground', 'background', 'case')}
            spec['font_index'] = override.get('font_index', style.get('font_index', 0))
            spec['size_multiplier'] = override.get('size_multiplier', 1.0)
            spec['transition_clearance_px'] = override.get('transition_clearance_px', 0)
            require(isinstance(spec['font_index'], int) and 0 <= spec['font_index'] <= 32,
                    'Invalid font collection index')
            require(isinstance(spec['size_multiplier'], (int, float)) and
                    math.isfinite(spec['size_multiplier']) and .8 <= spec['size_multiplier'] <= 1.6,
                    'Invalid line size multiplier')
            require(isinstance(spec['transition_clearance_px'], (int, float)) and
                    math.isfinite(spec['transition_clearance_px']) and
                    0 <= spec['transition_clearance_px'] <= 40,
                    'Invalid transition clearance')
            require(spec['case'] in ('preserve', 'upper'), 'Unsupported line case')
            for color in ('foreground', 'background'):
                value = spec[color]
                require(isinstance(value, str) and len(value) == 7 and value[0] == '#' and
                        all(c in '0123456789abcdefABCDEF' for c in value[1:]),
                        'Use opaque hex line colors')
            line_specs.append(spec)
        if box_mode == 'unified':
            require(all(spec['background'] == style['background'] for spec in line_specs),
                    'Unified card requires one background color')
        lines = [line.upper() if spec['case'] == 'upper' else line for line, spec in zip(lines, line_specs)]
    scale = width / 1080
    px, py, gap, radius = [round(x * scale) for x in
        ((style or {}).get('padding_x_px', 22), (style or {}).get('padding_y_px', 12),
         24, (style or {}).get('corner_radius_px', 18))]
    line_gap = round((style or {}).get('line_gap_px', -10) * scale)
    require(0 <= px <= round(60*scale) and 0 <= py <= round(40*scale) and
            0 <= radius <= round(40*scale) and -round(20*scale) <= line_gap <= round(40*scale),
            'Style card geometry outside supported bounds')
    safe = effective_safe_rect(m, width, height)
    caption_strategy = m.get('caption_strategy', 'preserve')
    require(caption_strategy in ('preserve', 'replace'), 'Unsupported caption strategy')
    bottom = m['caption_bottom_px'] if caption_bottom is None else caption_bottom
    if caption_bounds is not None:
        bottom = caption_bounds[1] + caption_bounds[3]
    require(0 <= bottom <= height, 'Invalid caption bottom')
    font_paths = [Path(spec['font_path']).expanduser() for spec in line_specs] if line_specs else [Path(m['font_path']).expanduser()]*len(lines)
    font_indices = [spec['font_index'] for spec in line_specs] if line_specs else [0]*len(lines)
    size_multipliers = [spec['size_multiplier'] for spec in line_specs] if line_specs else [1.0]*len(lines)
    transition_clearances = ([round(spec['transition_clearance_px']*scale) for spec in line_specs]
                             if line_specs else [0]*len(lines))
    require(all(path.is_file() for path in font_paths), 'Selected font missing; do not substitute silently')
    minimum = 60 if style else 84
    sizes = [forced_size] if forced_size else range(round(116*scale), round(minimum*scale)-1, -max(1, round(2*scale)))
    candidates = []
    for size in sizes:
        line_sizes = [round(size*multiplier) for multiplier in size_multipliers]
        fonts = [ImageFont.truetype(str(path), line_size, index=index)
                 for path, line_size, index in zip(font_paths, line_sizes, font_indices)]
        if short_line_width_ratio is not None:
            ink_widths = [font.getlength(line) for font, line in zip(fonts, lines)]
            shorter = min(range(2), key=lambda index: ink_widths[index])
            longer = 1-shorter
            target_width = ink_widths[longer]*short_line_width_ratio
            minimum_size = round(size*.8)
            maximum = round(size*1.6)
            estimate = round(line_sizes[shorter]*target_width/ink_widths[shorter])
            options = {max(minimum_size, min(maximum, estimate+step))
                       for step in range(-3, 4)}
            best = min(options, key=lambda candidate: abs(
                ImageFont.truetype(str(font_paths[shorter]), candidate,
                                   index=font_indices[shorter]).getlength(lines[shorter])-target_width))
            font = ImageFont.truetype(str(font_paths[shorter]), best,
                                      index=font_indices[shorter])
            actual_ratio = font.getlength(lines[shorter])/ink_widths[longer]
            if abs(actual_ratio-short_line_width_ratio) > .025:
                continue
            line_sizes[shorter], fonts[shorter] = best, font
        boxes = [font.getbbox(line) for font, line in zip(fonts, lines)]
        widths = [b[2]-b[0]+2*px for b in boxes]
        bottom_pads = ([max(py, clearance-line_gap) if index < len(lines)-1 else py
                        for index, clearance in enumerate(transition_clearances)]
                       if box_mode == 'fitted_lines' else [py]*len(lines))
        heights = [b[3]-b[1]+py+bottom_pad for b, bottom_pad in zip(boxes, bottom_pads)]
        bw = max(widths)
        bh = (sum(b[3]-b[1] for b in boxes)+2*py+line_gap*(len(lines)-1)
              if box_mode == 'unified' else sum(heights)+line_gap*(len(lines)-1))
        x = (width-bw)//2  # Always centered on the canvas; never shift away from Reels buttons.
        if x < safe[0] or x+bw > safe[0]+safe[2]:
            continue
        if caption_strategy == 'replace':
            require('replacement_hook_top_px' in m, 'Caption replacement needs a measured hook top')
            placements = [('replace', round(m['replacement_hook_top_px']))]
        else:
            placements = [('below', max(round(bottom+gap), math.ceil(safe[1])))]
            if caption_bounds is not None:
                # Safe-zone bottom may be above the visible caption. Keep at least
                # the caption gap, then lift the card as needed to stay safe.
                placements.append(('above', min(round(caption_bounds[1]-gap-bh),
                                                 safe[1]+safe[3]-bh)))
        for side, y in placements:
            rect = [x, y, bw, bh]
            if y < safe[1] or y+bh > safe[1]+safe[3]:
                continue
            if any(overlaps(rect, b) for b in (m['protected_rects'] if protected_rects is None else protected_rects)):
                continue
            candidates.append((side, size, rect, boxes, widths, heights, line_sizes))
    # Keep the original below-caption treatment whenever it fits readably;
    # above-caption placement is a measured fallback, never a horizontal dodge.
    for preferred_side in ('below', 'above', 'replace'):
        for side, size, rect, boxes, widths, heights, line_sizes in candidates:
            if side != preferred_side:
                continue
            x, y, bw, bh = rect
            fonts = [ImageFont.truetype(str(path), line_size, index=index)
                     for path, line_size, index in zip(font_paths, line_sizes, font_indices)]
            plate = Image.new('RGBA', (bw, bh), (0, 0, 0, 0))
            draw = ImageDraw.Draw(plate)
            if box_mode == 'unified':
                draw.rounded_rectangle((0, 0, bw-1, bh-1), radius=radius, fill=style['background'])
            rows, line_box_bounds, cursor = [], [], (py if box_mode == 'unified' else 0)
            for index, (line, b, w, h) in enumerate(zip(lines, boxes, widths, heights)):
                left = (bw-w)//2
                spec = line_specs[index] if line_specs else {'foreground':'#000000','background':'#FFFFFF'}
                if box_mode != 'unified':
                    draw.rounded_rectangle((left, cursor, left+w-1, cursor+h-1), radius=radius, fill=spec['background'])
                    line_box_bounds.append([left, cursor, w, h])
                rows.append((line, (bw-(b[2]-b[0]))/2-b[0],
                             cursor-b[1] if box_mode == 'unified' else cursor+py-b[1],
                             fonts[index], spec['foreground']))
                cursor += (b[3]-b[1] if box_mode == 'unified' else h)+line_gap
            for line, tx, ty, font, foreground in rows:
                draw.text((tx, ty), line, font=font, fill=foreground)
            first = line_specs[0] if line_specs else {'foreground':'#000000','background':'#FFFFFF'}
            resolved_lines = [{'text': line, 'font_path': str(path), 'font_index': index,
                               'font_sha256': digest(path),
                               'font_size_px': line_size,
                               'foreground': spec['foreground'], 'background': spec['background']}
                              for line, path, index, line_size, spec in
                              zip(lines, font_paths, font_indices, line_sizes, line_specs or [first]*len(lines))]
            return plate, {'bounds': rect, 'font_size_px': size, 'font_path': str(font_paths[0]),
                           'font_sha256': digest(font_paths[0]), 'gap_px': gap, 'anchor_side': side,
                           'box_mode': box_mode,
                           'short_line_width_ratio': short_line_width_ratio,
                           'rendered_line_boxes': line_box_bounds,
                           'effective_safe_rect': safe, 'rendered_display_lines': lines,
                           'rendered_line_styles': resolved_lines,
                           'foreground': first['foreground'], 'background': first['background']}
    raise ValueError('Placement conflict: no centered readable hook fits the safe zone around captions and protected regions')


def build(manifest, output_dir, render=False):
    m = json.loads(Path(manifest).read_text())
    require(m.get('schema') in ('text-hook/v1', 'hook-overlay/v1'), 'Unsupported handoff schema')
    require(m.get('clip_id') and m.get('transcript_revision'), 'Missing clip/transcript identity')
    source = Path(m['source']).expanduser().resolve()
    clean_source = None
    if m.get('caption_strategy', 'preserve') == 'replace':
        require(m.get('clean_opening_source') and m.get('clean_opening_sha256'),
                'Caption replacement needs a verified caption-free source')
        clean_source = Path(m['clean_opening_source']).expanduser().resolve()
        require(digest(clean_source) == m['clean_opening_sha256'], 'Stale clean opening hash')
    transcript = Path(m['transcript']).expanduser().resolve()
    require(digest(source) == m['source_sha256'], 'Stale source hash')
    require(digest(transcript) == m['transcript_sha256'], 'Stale transcript hash')
    text = norm(transcript.read_text())
    require(m.get('supporting_passages'), 'Missing supporting passages')
    require(all(norm(p['quote']) and norm(p['quote']) in text for p in m['supporting_passages']), 'Support quote absent from current transcript')
    require(m.get('geometry_evidence'), 'Missing opening geometry evidence')
    info = probe(source)
    video = next(s for s in info['streams'] if s['codec_type'] == 'video')
    width, height = video['width'], video['height']
    require(video.get('sample_aspect_ratio', '1:1') in ('1:1', 'N/A'), 'Normalize non-square pixels before layout')
    require(not any(d.get('rotation', 0) for d in video.get('side_data_list', [])), 'Resolve display rotation before layout')
    a, b = map(int, video['avg_frame_rate'].split('/'))
    fps = a/b
    require(fps > 0, 'Invalid frame rate')
    duration = float(video.get('duration', info['format']['duration']))
    # Keep the first sampled frame at or after five seconds, then clear on the
    # following frame boundary. This honors the inclusive editorial handoff.
    end = min((math.ceil(5*fps - 1e-9)+1)/fps, duration)
    if clean_source:
        clean_info = probe(clean_source)
        clean_video = next(s for s in clean_info['streams'] if s['codec_type'] == 'video')
        require((clean_video['width'], clean_video['height']) == (width, height),
                'Caption-free opening has different canvas')
        require(clean_video['avg_frame_rate'] == video['avg_frame_rate'],
                'Caption-free opening has different frame rate')
        require(float(clean_video.get('duration', clean_info['format']['duration'])) >= end,
                'Caption-free opening ends before hook')
    intervals = m.get('placement_intervals')
    if intervals is None:
        require('caption_bottom_px' in m, 'Missing caption geometry')
        intervals = [{'start_seconds': 0, 'end_seconds': end,
                      'caption_bounds': [0, m['caption_bottom_px'], width, 0],
                      'protected_rects': m['protected_rects'],
                      'evidence': m['geometry_evidence']}]
    require(isinstance(intervals, list) and intervals, 'Missing placement intervals')
    cursor = 0.0
    for interval in intervals:
        start, stop = float(interval['start_seconds']), float(interval['end_seconds'])
        require(abs(start-cursor) < 1/fps/4 and stop > start and stop <= end+1/fps/4,
                'Placement intervals must cover the five-second opening without gaps or overlaps')
        cursor = stop
        require(interval.get('evidence'), 'Placement interval needs frame or native geometry evidence')
        bounds = interval.get('caption_bounds')
        require(bounds is not None and len(bounds) == 4 and all(math.isfinite(x) for x in bounds),
                'Placement interval needs measured speech-caption bounds')
        require(bounds[1] >= 0 and bounds[1]+bounds[3] <= height, 'Caption bounds outside canvas')
        require(isinstance(interval.get('protected_rects', []), list), 'Invalid protected geometry')
    require(abs(cursor-end) < 1/fps/4, 'Placement intervals do not reach the hook end')
    initial=[]
    for interval in intervals:
        b=interval['caption_bounds']
        initial.append(layout(m,width,height,caption_bottom=b[1]+b[3],
                              caption_bounds=b if m.get('placement_intervals') is not None else None,
                              protected_rects=interval.get('protected_rects',m['protected_rects'])))
    common_size=min(r['font_size_px'] for _,r in initial)
    displayed_size, font_size_multiplier = fitted_font_size(m,width,height,common_size)
    placed=[]
    for interval in intervals:
        b=interval['caption_bounds']
        placed.append(layout(m,width,height,caption_bottom=b[1]+b[3],
                             caption_bounds=b if m.get('placement_intervals') is not None else None,
                             protected_rects=interval.get('protected_rects',m['protected_rects']),
                             forced_size=displayed_size))
    plate, resolved = placed[0]
    out = Path(output_dir).expanduser().resolve()
    require(not out.exists(), 'Output directory already exists; use a fresh revision')
    if render:
        ancestor = out.parent
        while not ancestor.exists():
            ancestor = ancestor.parent
        required_bytes = int(duration * 2_000_000 * 1.25 + 50_000_000)
        require(shutil.disk_usage(ancestor).free > required_bytes,
                'Insufficient free space for this review render; use an authorized work location')
    out.mkdir(parents=True)
    plate.save(out/'plate.png')
    resolved_intervals=[]
    for index,(interval,(layer,geometry)) in enumerate(zip(intervals,placed)):
        filename=f'plate-{index:02}.png'
        layer.save(out/filename)
        resolved_intervals.append({**interval,'hook_bounds':geometry['bounds'],
                                   'gap_px':geometry['gap_px'],'anchor_side':geometry['anchor_side'],
                                   'effective_safe_rect':geometry['effective_safe_rect'],'plate':filename})
    frame = out/'source-frame.png'
    subprocess.run(['ffmpeg', '-v', 'error', '-n', '-ss', str(min(0.5, duration/2)), '-i', str(source), '-frames:v', '1', str(frame)], check=True)
    still = Image.open(frame).convert('RGBA')
    still.alpha_composite(plate, tuple(resolved['bounds'][:2]))
    still.convert('RGB').save(out/'preview.jpg', quality=95)
    receipt = {**m, **resolved, 'placement_intervals':resolved_intervals,
               'canvas': [width, height], 'start_seconds': 0, 'end_seconds': end,
               'base_fit_font_size_px': common_size, 'font_size_multiplier':font_size_multiplier,
               'frame_rate': video['avg_frame_rate'], 'animation': 'none', 'status': 'geometry_checked_preview_unreviewed',
               'native_verified': False, 'user_approved': False}
    (out/'resolved.json').write_text(json.dumps(receipt, indent=2)+'\n')
    if render:
        target = out/'review.mp4'
        plate_inputs=[]
        filters=[]
        previous='0:v'
        plate_input_offset = 1
        clean_inputs = []
        if clean_source:
            clean_inputs = ['-i', str(clean_source)]
            filters.append(f"[0:v][1:v]overlay=x=0:y=0:enable='lt(t,{end:.9f})':eof_action=pass:shortest=0[clean_opening]")
            previous = 'clean_opening'
            plate_input_offset = 2
        for index,interval in enumerate(resolved_intervals):
            plate_inputs += ['-loop','1','-framerate',video['avg_frame_rate'],'-i',str(out/interval['plate'])]
            x,y=interval['hook_bounds'][:2]
            output=f'v{index}'
            filters.append(f"[{previous}][{index+plate_input_offset}:v]overlay=x={x}:y={y}:enable='gte(t,{interval['start_seconds']:.9f})*lt(t,{interval['end_seconds']:.9f})':shortest=1[{output}]")
            previous=output
        command = ['ffmpeg', '-v', 'error', '-n', '-i', str(source), *clean_inputs, *plate_inputs,
                   '-filter_complex', ';'.join(filters),
                   '-map', f'[{previous}]', '-map', '0:a?', '-c:v', 'h264_videotoolbox', '-b:v', '16M', '-pix_fmt', 'yuv420p',
                   '-fps_mode', 'passthrough', '-c:a', 'copy', '-movflags', '+faststart', str(target)]
        try:
            subprocess.run(command, check=True)
            subprocess.run(['ffmpeg', '-v', 'error', '-i', str(target), '-f', 'null', '-'], check=True)
        except subprocess.CalledProcessError:
            receipt['status'] = 'render_failed'
            (out/'resolved.json').write_text(json.dumps(receipt, indent=2)+'\n')
            raise
        receipt.update(video=str(target), full_decode='passed', status='rendered_unreviewed')
    (out/'resolved.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--render', action='store_true')
    args = parser.parse_args()
    try:
        result = build(args.manifest, args.output_dir, args.render)
        print(json.dumps({'status': result['status'], 'bounds': result['bounds']}))
    except (ValueError, KeyError, StopIteration) as exc:
        parser.exit(2, f'Hook refused: {exc}\n')
