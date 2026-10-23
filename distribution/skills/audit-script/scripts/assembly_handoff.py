#!/usr/bin/env python3
"""Prepare native assembly review evidence and fail closed before editor handoff.

Uses the existing Premiere bridge transport read-only. No export or timeline mutation.
This checks evidence/coverage, not whether an agent's editorial judgment is correct.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

CRITERIA = ('content_unit', 'hook', 'retain', 'reward', 'goodwill',
            'value_compression', 'audience_growth')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def validate_report(report, clip, builder_id):
    """The v1 report schema. Validate before consuming a verdict."""
    require(isinstance(report, dict), 'report must be an object')
    require(report.get('schema') == 'assembly-review/v1', 'wrong report schema')
    require(report.get('clip_id') == clip['clip_id'], 'wrong clip ID')
    require(report.get('evidence_sha256') == clip['evidence_sha256'], 'stale review evidence')
    require(nonempty(report.get('agent_id')) and report['agent_id'] != builder_id,
            'missing independent agent ID')
    require(report.get('verdict') in ('PASS', 'REVISE', 'UNKNOWN'), 'invalid verdict')
    for field in ('viewer', 'promise', 'reward', 'handoff_note'):
        require(nonempty(report.get(field)), 'missing ' + field)
    require(isinstance(report.get('checks'), dict) and
            set(report['checks']) == set(CRITERIA), 'all seven criteria are required')
    for key in CRITERIA:
        check = report['checks'][key]
        require(isinstance(check, dict), 'invalid criterion ' + key)
        require(check.get('verdict') in ('PASS', 'REVISE', 'UNKNOWN'), 'invalid ' + key)
        require(nonempty(check.get('evidence')) and nonempty(check.get('reason')),
                'missing evidence/reason: ' + key)
    require(isinstance(report.get('fixes'), list), 'fixes must be a list')
    for fix in report['fixes']:
        require(isinstance(fix, dict) and isinstance(fix.get('required'), bool) and
                nonempty(fix.get('evidence')) and nonempty(fix.get('edit')),
                'invalid fix')
    if report['verdict'] == 'PASS':
        require(all(c['verdict'] == 'PASS' for c in report['checks'].values()),
                'PASS contradicts criterion verdict')
        require(not any(f['required'] for f in report['fixes']), 'unresolved required fix')


def read_native(project, sequence):
    """Read through the default typed bridge, checking identity before and after."""
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'_shared'))
    from premiere_bridge import PremiereBridge,Profile
    client=PremiereBridge(Profile.load())
    try:
        ping=client.inspect('ping',{})['data']
        require(ping.get('projectName')==project,'wrong current project')
        before=client.inspect('lab_snapshot',{})
        info=client.inspect('get_full_sequence_info',{'sequence_id':before['sequenceId']})['data']
        after=client.inspect('lab_snapshot',{})
        require(before==after,'native state changed during review readback')
        require(info['name']==sequence and str(info['id'])==before['sequenceId'],'wrong exact sequence')
        def tracks(rows):
            result=[]
            for row in rows:
                items=[]
                for c in row['clips']:
                    require('sourceIsSequence' in c and 'reversed' in c and 'speed' in c,'native source/playback evidence unavailable')
                    items.append({'name':c['name'],'source':c.get('sourceMediaPath'),'is_sequence':bool(c['sourceIsSequence']),
                        'node':str(c['sourceNodeId']),'start':int(c['startTicks'])/254016000000,
                        'end':int(c['endTicks'])/254016000000,'in_point':int(c['inPointTicks'])/254016000000,
                        'out_point':int(c['outPointTicks'])/254016000000,'disabled':not c['enabled'],
                        'speed':c['speed'],'reversed':bool(c['reversed'])})
                result.append({'muted':bool(row['isMuted']),'items':items})
            return result
        return {'project':project,'project_path':before['projectPath'],'sequence':sequence,
                'sequence_id':before['sequenceId'],'video':tracks(info['videoTracks']),'audio':tracks(info['audioTracks'])}
    finally:client.close()


def groups(state):
    require(state.get('video') and not state['video'][0]['muted'], 'missing/muted V1')
    items = sorted(state['video'][0]['items'], key=lambda i: i['start'])
    require(items, 'empty assembly')
    result = []
    for item in items:
        require(item['end'] > item['start'] and not item.get('disabled'), 'invalid V1 item')
        if not result or item['start'] - result[-1][-1]['end'] > 5:
            result.append([])
        result[-1].append(item)
    # No unaccounted video/audio islands outside the V1 clip groups.
    for track in state['video'] + state['audio']:
        for item in track['items']:
            require(not item.get('is_sequence') and nonempty(item.get('source')),
                    'nested/multicam or non-file media cannot be fingerprinted; use native source items')
            require(any(item['start'] >= g[0]['start'] - .05 and
                        item['end'] <= g[-1]['end'] + .05 for g in result),
                    'media outside a clip group; reconcile native coverage first')
    return result


def make_packet(state, transcript_dir, builder_id):
    require(nonempty(builder_id), 'builder ID required')
    clips = []
    for index, group in enumerate(groups(state), 1):
        clip_id = 'clip_%03d' % index
        transcript = (Path(transcript_dir) / (clip_id + '.txt')).resolve()
        content = transcript.read_text()
        require(nonempty(content), 'empty transcript: ' + clip_id)
        clip = dict(clip_id=clip_id, start=group[0]['start'], end=group[-1]['end'],
                    transcript_path=str(transcript), transcript=content)
        # Whole native state deliberately invalidates the batch after ANY timeline edit.
        clip['evidence_sha256'] = digest({'native': state, 'clip': clip})
        clips.append(clip)
    return dict(schema='assembly-packet/v1', builder_id=builder_id, native=state, clips=clips)


def check_packet(packet, live_state, reviews):
    require(packet.get('schema') == 'assembly-packet/v1', 'wrong packet schema')
    require(nonempty(packet.get('builder_id')), 'missing builder ID')
    require(packet['native'] == live_state, 'Premiere changed since review; prepare and re-review')
    expected = groups(live_state)
    require(len(packet['clips']) == len(expected), 'incomplete native clip coverage')
    agent_ids = set()
    for index, (clip, group) in enumerate(zip(packet['clips'], expected), 1):
        require(clip['clip_id'] == 'clip_%03d' % index, 'missing/duplicate clip')
        require(clip['start'] == group[0]['start'] and clip['end'] == group[-1]['end'],
                'clip range mismatch')
        require(nonempty(clip['transcript']) and
                Path(clip['transcript_path']).read_text() == clip['transcript'],
                'transcript changed; prepare and re-review')
        raw = {k: v for k, v in clip.items() if k != 'evidence_sha256'}
        require(clip['evidence_sha256'] == digest({'native': live_state, 'clip': raw}),
                'packet evidence mismatch')
        report = json.loads((Path(reviews) / (clip['clip_id'] + '.json')).read_text())
        validate_report(report, clip, packet['builder_id'])
        require(report['agent_id'] not in agent_ids, 'use a fresh agent per clip')
        agent_ids.add(report['agent_id'])
        require(report['verdict'] == 'PASS', clip['clip_id'] + ': ' + report['verdict'])
    return len(expected)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare', action='store_true')
    mode.add_argument('--check', action='store_true')
    parser.add_argument('--packet', required=True)
    parser.add_argument('--require-project', required=True)
    parser.add_argument('--require-sequence', required=True)
    parser.add_argument('--transcripts')
    parser.add_argument('--builder-id')
    parser.add_argument('--reviews')
    args = parser.parse_args(argv)
    try:
        state = read_native(args.require_project, args.require_sequence)
        if args.prepare:
            require(args.transcripts and args.builder_id, '--transcripts and --builder-id required')
            packet = make_packet(state, args.transcripts, args.builder_id)
            Path(args.packet).write_text(json.dumps(packet, indent=2) + '\n')
            print('Prepared %d clips for fresh-agent review; NOT a handoff pass.' % len(packet['clips']))
        else:
            require(args.reviews, '--reviews required')
            packet = json.loads(Path(args.packet).read_text())
            count = check_packet(packet, state, args.reviews)
            print('ASSEMBLY REVIEW PASS: %d/%d clips; live timeline matches; evidence %s' %
                  (count, count, digest(state)))
        return 0
    except Exception as error:
        print('ASSEMBLY HANDOFF BLOCKED: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
