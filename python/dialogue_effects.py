"""Transport explicitly reviewed native dialogue treatment; no automatic mix choices."""
import math
from common import inside, require, sha, read

RANGES = {
 'highpass': {'cutoff': (20, 20000)},
 'amplify': {'gain': (-96, 24)},
 'single_band_compressor': {'threshold': (-60, 0), 'ratio': (1, 30),
                          'attack': (.1, 300), 'release': (1, 3000), 'output': (-30, 30)},
 'hard_limiter': {'max': (-30, 0), 'boost': (0, 30), 'release': (1, 1000)},
}

def validate(project, spec):
    treatment = spec.get('audio', {}).get('dialogueEffects')
    if treatment is None:
        return None
    require(spec['backend'] == 'filmcraft', 'Native dialogue effect transport is currently FilmCraft-only; implement the selected editor route explicitly')
    require(set(treatment) == {'schema', 'receiptPath', 'receiptSha256', 'cuts'} and
            treatment['schema'] == 'acq-edit/dialogue-effects-v1', 'Unknown dialogue treatment')
    receipt = inside(project['root'], treatment['receiptPath'])
    require(sha(receipt) == treatment['receiptSha256'], 'Dialogue treatment evidence changed')
    require(set(treatment['cuts']) == {c['id'] for c in spec['cuts']}, 'Dialogue treatment must cover exact cuts')
    for chain in treatment['cuts'].values():
        require(isinstance(chain, list) and 1 <= len(chain) <= 4, 'Bounded native dialogue chain required')
        ids = [e['effect'] for e in chain]
        require(len(ids) == len(set(ids)), 'Duplicate dialogue effect refused')
        for effect in chain:
            require(set(effect) == {'effect', 'params'} and effect['effect'] in RANGES, 'Unsupported dialogue effect')
            bounds = RANGES[effect['effect']]
            require(set(effect['params']) == set(bounds), 'Supply all supported dialogue effect parameters')
            for name, value in effect['params'].items():
                low, high = bounds[name]
                require(type(value) in (int, float) and math.isfinite(value) and low <= value <= high,
                        'Dialogue effect parameter outside native range: ' + name)
    return treatment

def apply(client, spec, clips):
    treatment = spec.get('audio', {}).get('dialogueEffects')
    if not treatment:
        return
    require(len(clips) == len(spec['cuts']), 'Dialogue native item count differs')
    for cut, clip in zip(spec['cuts'], clips):
        for effect in treatment['cuts'][cut['id']]:
            client.run('effects.apply', {'clips': [clip['clip']], 'effect': effect['effect']})
            for name, value in effect['params'].items():
                client.run('effects.setParam', {'clip': clip['clip'], 'effect': effect['effect'], 'param': name, 'value': value})

def verify(native, spec):
    treatment = spec.get('audio', {}).get('dialogueEffects')
    if not treatment:
        return
    data = read(native)
    sequence = data['project']['items'][str(data['view']['active_sequence'])]['kind']['Sequence']
    items = sequence['audio_tracks'][0]['items']
    require(len(items) == len(spec['cuts']), 'Dialogue treatment native coverage changed')
    for cut, item in zip(spec['cuts'], items):
        chain = treatment['cuts'][cut['id']]
        effects = item['effects']
        require([e['effect'] for e in effects] == ['volume', 'channel_volume', 'panner'] + [e['effect'] for e in chain],
                'Native dialogue effect order or membership changed')
        for expected, actual in zip(chain, effects[3:]):
            require(actual['enabled'] and not actual.get('masks'), 'Disabled or masked dialogue effect')
            for name, value in expected['params'].items():
                field = actual['params'][name]
                require(not field.get('keyframes') and field['value'] == {'Float': float(value)},
                        'Native dialogue parameter changed: ' + name)
