"""Prepare explicit microphone routing on a selected picture clock.

Assembly Design supplies offsets and gains. This transport never estimates sync,
chooses speakers, edits words, or certifies listening. Import its output through
ordinary source intake before using it in a native plan.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def pin(record):
    path = Path(record['path']).resolve(strict=True)
    if digest(path) != record['sha256']:
        raise ValueError(f'Pinned input changed: {path}')
    return path


def integer(value, label, positive=False):
    if type(value) is not int or value < (1 if positive else 0):
        raise ValueError(f'{label} must be an explicit nonnegative integer')
    return value


def map_words(transcript, offset_samples, rate, duration_samples):
    """Retain complete words inside the conformed clock, with original identity."""
    offset = offset_samples / rate
    duration = duration_samples / rate
    kept, excluded = [], []
    for index, word in enumerate(transcript['words']):
        start, end = float(word['start']) + offset, float(word['end']) + offset
        if not all(math.isfinite(v) for v in (start, end)) or end < start:
            raise ValueError('Invalid source word clock')
        if start < 0 or end > duration:
            excluded.append(index)
            continue
        item = copy.deepcopy(word)
        item.update(start=round(start, 9), end=round(end, 9), source_word_index=index,
                    original_start=word['start'], original_end=word['end'])
        kept.append(item)
    return kept, excluded


def prepare(spec, output_dir, ffmpeg='ffmpeg', ffprobe='ffprobe'):
    if spec.get('schema') != 'acq-edit/dialogue-conform-v1':
        raise ValueError('Expected explicit dialogue-conform-v1 specification')
    rate = integer(spec['sampleRate'], 'sampleRate', True)
    if rate != 48000:
        raise ValueError('This conform supports explicit 48 kHz PCM only')
    samples = integer(spec['durationSamples'], 'durationSamples', True)
    offset = spec['transcriptOffsetSamples']
    if type(offset) is not int:
        raise ValueError('Transcript offset must be integer samples')
    evidence = pin(spec['clockEvidence'])
    transcript_path = pin(spec['transcript'])
    microphones = spec['microphones']
    if not microphones or len(microphones) > 8:
        raise ValueError('Supply one to eight explicit microphone routes')
    argv, filters, inputs = [], [], []
    for index, mic in enumerate(microphones):
        source = pin(mic)
        source_start = integer(mic['sourceStartSample'], 'sourceStartSample')
        gain = mic['gain']
        if type(gain) not in (int, float) or not math.isfinite(gain) or not 0 < gain <= 1:
            raise ValueError('Each microphone gain must be explicit and in (0,1]')
        info = json.loads(subprocess.check_output([ffprobe, '-v', 'error', '-show_streams', '-of', 'json', str(source)]))
        audio = [s for s in info['streams'] if s['codec_type'] == 'audio']
        if len(audio) != 1 or audio[0]['channels'] != 1 or int(audio[0]['sample_rate']) != rate or not audio[0]['codec_name'].startswith('pcm_'):
            raise ValueError('Only explicit mono 48 kHz PCM microphone inputs are supported')
        if abs(float(audio[0].get('start_time', 0))) > 1e-9:
            raise ValueError('Input stream must start at zero')
        if float(audio[0]['duration']) * rate + 0.5 < source_start + samples:
            raise ValueError('Microphone does not cover the complete requested clock')
        argv += ['-i', str(source)]
        filters.append(f'[{index}:a:0]atrim=start_sample={source_start}:end_sample={source_start+samples},asetpts=PTS-STARTPTS,volume={gain}[m{index}]')
        inputs.append(f'[m{index}]')
    if sum(m['gain'] for m in microphones) > 1 + 1e-9:
        raise ValueError('Explicit gains must sum to at most one to preserve PCM headroom')
    filters.append(''.join(inputs) + f'amix=inputs={len(inputs)}:duration=shortest:normalize=0[out]')
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=False)
    media, receipt = out / 'dialogue.wav', out / 'receipt.json'
    result = {'schema': 'acq-edit/dialogue-conform-receipt-v1', 'status': 'PREPARING',
              'spec': spec, 'clockEvidence': str(evidence), 'listening': 'not_performed',
              'limitation': 'Clock/routing preparation only; acoustic sync and mix quality require inspection.'}
    try:
        with (out / 'ffmpeg.log').open('w') as log:
            subprocess.run([ffmpeg, '-nostdin', '-v', 'warning', *argv, '-filter_complex', ';'.join(filters),
                            '-map', '[out]', '-c:a', 'pcm_s24le', '-ar', str(rate), '-ac', '1', '-n', str(media)],
                           stdout=log, stderr=log, check=True)
        info = json.loads(subprocess.check_output([ffprobe, '-v', 'error', '-show_streams', '-of', 'json', str(media)]))
        stream = info['streams'][0]
        if stream['codec_name'] != 'pcm_s24le' or stream['channels'] != 1 or int(stream['sample_rate']) != rate or int(stream['duration_ts']) != samples or stream['time_base'] != f'1/{rate}':
            raise ValueError('Output PCM geometry differs from requested samples')
        original = json.loads(transcript_path.read_text())
        words, excluded = map_words(original, offset, rate, samples)
        mapped = {'schema': 'acq-edit/conformed-source-words-v1', 'words': words,
                  'source': str(media), 'originalTranscript': spec['transcript'],
                  'transcriptOffsetSamples': offset, 'sampleRate': rate,
                  'excluded_source_word_indices': excluded,
                  'qualification': 'Exact clock transformation; no ASR text or speaker corrections.'}
        word_path = out / 'source-words.json'
        word_path.write_text(json.dumps(mapped, indent=2) + '\n')
        result.update(status='PREPARED_AWAITING_INTAKE_AND_INSPECTION', media=str(media),
                      mediaSha256=digest(media), words=str(word_path), wordsSha256=digest(word_path),
                      durationSamples=samples, mappedWords=len(words), excludedWords=len(excluded))
    except Exception as error:
        result.update(status='FAILED_PARTIAL_PRESERVED', error=str(error))
        raise
    finally:
        receipt.write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--spec', required=True)
    parser.add_argument('--output-dir', required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(json.loads(Path(args.spec).read_text()), args.output_dir)))
