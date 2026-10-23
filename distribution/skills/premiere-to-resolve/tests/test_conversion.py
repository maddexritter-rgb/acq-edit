"""Regression tests for native timing, distinct track/clip states, and fail-closed input binding.
Run with: python3 -m unittest discover -s tests -v
"""
import copy
import json
import os
import subprocess
import pathlib
import sys
import tempfile
import unittest
import xml.etree.ElementTree as E

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
from prepare import prepare, validate_manifest, sha
from audit_prproj import audit, AUDIT_SCHEMA
from convert import snapshot, apply_track_settings, bind_native_audit


def xml_fixture(media):
    root = E.Element('xmeml', version='4')
    s = E.SubElement(root, 'sequence', id='sequence-1')
    def add(p, key, value): E.SubElement(p, key).text = str(value)
    add(s, 'name', 'Vertical test'); add(s, 'duration', 48)
    rate = E.SubElement(s, 'rate'); add(rate, 'timebase', 24); add(rate, 'ntsc', 'FALSE')
    v = E.SubElement(E.SubElement(s, 'media'), 'video')
    sc = E.SubElement(E.SubElement(v, 'format'), 'samplecharacteristics')
    add(sc, 'width', 1080); add(sc, 'height', 1920)
    for index in range(3):
        t = E.SubElement(v, 'track'); add(t, 'enabled', 'TRUE' if index == 0 else 'FALSE')
        c = E.SubElement(t, 'clipitem', id='clip-' + str(index)); add(c, 'name', 'Camera ' + str(index))
        add(c, 'enabled', 'TRUE'); c.append(copy.deepcopy(rate))
        for k, val in [('start', 0), ('end', 48), ('in', 24), ('out', 72)]: add(c, k, val)
        f = E.SubElement(c, 'file', id='file-' + str(index)); add(f, 'pathurl', media.as_uri())
    return root


def native_fixture(media):
    root = E.Element('PremiereData')
    def add(p, k, value): E.SubElement(p, k).text = str(value)
    s = E.SubElement(root, 'Sequence', ObjectUID='sequence'); add(s, 'Name', 'Vertical test')
    groups = E.SubElement(s, 'TrackGroups'); pair = E.SubElement(groups, 'TrackGroup')
    E.SubElement(pair, 'Second', ObjectRef='group')
    g = E.SubElement(root, 'VideoTrackGroup', ObjectID='group'); add(g, 'FrameRect', '0,0,1080,1920')
    tg = E.SubElement(g, 'TrackGroup'); add(tg, 'FrameRate', 10584000000); tracks = E.SubElement(tg, 'Tracks')
    for i in range(3):
        E.SubElement(tracks, 'Track', ObjectURef='track-' + str(i))
        t = E.SubElement(root, 'VideoClipTrack', ObjectUID='track-' + str(i)); ct = E.SubElement(t, 'ClipTrack'); tr = E.SubElement(ct, 'Track')
        add(tr, 'IsMuted', 'false' if i == 0 else 'true')
        props = E.SubElement(E.SubElement(tr, 'Node'), 'Properties'); add(props, 'MZ.TrackName', 'Angle ' + str(i))
        items = E.SubElement(E.SubElement(ct, 'ClipItems'), 'TrackItems'); E.SubElement(items, 'TrackItem', ObjectRef='item-' + str(i))
        it = E.SubElement(root, 'VideoClipTrackItem', ObjectID='item-' + str(i)); ci = E.SubElement(it, 'ClipTrackItem'); ti = E.SubElement(ci, 'TrackItem'); add(ti, 'End', 48 * 10584000000)
        E.SubElement(ci, 'SubClip', ObjectRef='sub-' + str(i)); sub = E.SubElement(root, 'SubClip', ObjectID='sub-' + str(i)); add(sub, 'Name', 'Camera ' + str(i)); E.SubElement(sub, 'Clip', ObjectRef='clip-' + str(i))
        cl = E.SubElement(E.SubElement(root, 'VideoClip', ObjectID='clip-' + str(i)), 'Clip'); add(cl, 'InPoint', 24 * 10584000000); add(cl, 'OutPoint', 72 * 10584000000); E.SubElement(cl, 'Source', ObjectRef='source')
    src = E.SubElement(root, 'VideoMediaSource', ObjectID='source'); E.SubElement(E.SubElement(src, 'MediaSource'), 'Media', ObjectURef='media')
    m = E.SubElement(root, 'Media', ObjectUID='media'); add(m, 'FilePath', media)
    return root


class Item:
    def __init__(self, e): self.e = copy.deepcopy(e)
    def GetName(self): return self.e['name']
    def GetStart(self, precise=False): return self.e['start']
    def GetEnd(self, precise=False): return self.e['end']
    def GetLeftOffset(self, precise=False): return self.e['in']
    def GetMediaPoolItem(self): return self
    def GetLinkedItems(self): return []
    def GetClipProperty(self, key): return self.e['path'] if key == 'File Path' else 'Online'
    def GetClipEnabled(self): return self.e['enabled']
    def GetProperty(self): return {}


class Timeline:
    def __init__(self, seq, project):
        self.seq, self.project = copy.deepcopy(seq), project
        self.settings = dict(timelineResolutionWidth='1080', timelineResolutionHeight='1920', timelineFrameRate='24', useCustomSettings='1', timelineInputResMismatchBehavior='centerCrop')
        self.flags = [True, False, False]; self.names = ['Angle 0', 'Angle 1', 'Angle 2']
        self.items = [[Item(c) for c in tr] for tr in seq['tracks']['video']]
    def GetName(self): return self.seq['name']
    def GetStartFrame(self): return 0
    def GetEndFrame(self): return 48
    def GetSetting(self, key=None): return self.settings if key is None else self.settings[key]
    def GetMarkers(self): return {}
    def GetTrackCount(self, kind): return len(self.items) if kind == 'video' else 0
    def GetItemListInTrack(self, kind, index): return self.items[index-1] if kind == 'video' and index <= len(self.items) else []
    def GetIsTrackEnabled(self, kind, index): return self.flags[index-1] if self.project.current is self and index <= len(self.flags) else False
    def GetTrackName(self, kind, index): return self.names[index-1] if index <= len(self.names) else None
    def SetTrackEnable(self, kind, index, value):
        if self.project.current is not self: return False
        self.flags[index-1] = value; return True
    def SetTrackName(self, kind, index, value):
        if self.project.current is not self: return False
        self.names[index-1] = value; return True


class Project:
    def __init__(self, seq): self.current = None; self.timeline = Timeline(seq, self)
    def GetTimelineCount(self): return 1
    def GetTimelineByIndex(self, index): return self.timeline
    def SetCurrentTimeline(self, timeline): self.current = timeline; return True


class ConversionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.dir = pathlib.Path(self.tmp.name)
        self.media = self.dir/'source.mov'; self.media.write_bytes(b'local fixture')
        self.xml = self.dir/'input.xml'; E.ElementTree(xml_fixture(self.media)).write(self.xml)
        self.path = prepare(self.xml, self.dir/'prepared'); self.m = json.loads(self.path.read_text())
        self.native = self.dir/'source.prproj'; E.ElementTree(native_fixture(self.media)).write(self.native)
    def report(self, project): return snapshot(project, self.m, None, self.dir, export_xml=False)
    def test_prepare_keeps_track_and_clip_flags_independent(self):
        s = self.m['sequences'][0]
        self.assertEqual([x['enabled'] for x in s['track_settings']['video']], [True,False,False])
        self.assertTrue(all(c['enabled'] for tr in s['tracks']['video'] for c in tr))
    def test_native_audit_checks_timing_paths_and_track_flags(self):
        self.assertTrue(audit(self.native, self.m)['passed'])
        self.m['sequences'][0]['track_settings']['video'][1]['enabled'] = True
        self.assertIn('track_enabled', [e['field'] for e in audit(self.native,self.m)['errors']])
    def test_native_audit_catches_one_tick_audio_or_video_rounding(self):
        r = E.parse(self.native); r.find('.//VideoClip/Clip/InPoint').text = str(24*10584000000+1); r.write(self.native)
        self.assertFalse(audit(self.native,self.m)['passed'])
    def test_duplicate_basename_is_not_media_identity(self):
        other = self.dir/'other'; other.mkdir(); wrong = other/'source.mov'; wrong.write_bytes(b'local fixture')
        r = E.parse(self.native); r.find('.//Media/FilePath').text = str(wrong); r.write(self.native)
        self.assertIn('media_path',[x['field'] for x in audit(self.native,self.m)['errors']])
    def test_native_names_fill_missing_xml_labels(self):
        n = audit(self.native,self.m); n.update(project_path=str(self.native), manifest_sha256=sha(self.path), auditor_sha256=sha(pathlib.Path(sys.modules['audit_prproj'].__file__)))
        result = bind_native_audit(self.m,self.path,n)
        self.assertEqual(result['sequences'][0]['track_settings']['video'][1]['name'],'Angle 1')
        n['manifest_sha256'] = 'stale'
        with self.assertRaises(RuntimeError): bind_native_audit(self.m,self.path,n)
    def test_v1_timing_only_receipt_and_manifest_rejected(self):
        bad=copy.deepcopy(self.m); bad['schema']='premiere-to-resolve/v1'
        with self.assertRaises(ValueError): validate_manifest(bad)
        with self.assertRaises(RuntimeError): bind_native_audit(self.m,self.path,{'passed':True})
    def test_snapshot_detects_incorrectly_enabled_alternate(self):
        p=Project(self.m['sequences'][0]); self.assertTrue(self.report(p)['passed'])
        p.timeline.flags[1]=True
        self.assertIn('Vertical test: video2 track enabled state', self.report(p)['errors'])
    def test_clip_flag_checked_independently(self):
        p=Project(self.m['sequences'][0]); p.timeline.items[1][0].e['enabled']=False
        self.assertFalse(self.report(p)['passed'])
    def test_resolution_and_custom_settings_regressions_fail(self):
        p=Project(self.m['sequences'][0]); p.timeline.settings['timelineResolutionWidth']='1920'
        p.timeline.settings['useCustomSettings']='0'
        errors=self.report(p)['errors']; self.assertTrue(any('ResolutionWidth' in x for x in errors)); self.assertTrue(any('custom timeline' in x for x in errors))
    def test_restore_track_flags_names_activates_target_first(self):
        seq=self.m['sequences'][0]; seq['track_settings']['video'][1]['name']='Guest'
        p=Project(seq); p.timeline.flags=[True,True,True]
        changes=apply_track_settings(p,p.timeline,seq)
        self.assertEqual(p.timeline.flags,[True,False,False]);self.assertEqual(p.timeline.names[1],'Guest');self.assertEqual(len(changes),2)
    def test_missing_track_fails_even_when_disabled(self):
        p=Project(self.m['sequences'][0]);p.timeline.items.pop();p.timeline.flags.pop();p.timeline.names.pop()
        self.assertFalse(self.report(p)['passed'])
    def test_resolve_python_launchers_import_their_siblings(self):
        runtime = pathlib.Path(os.environ.get('RESOLVE_PYTHON', '/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Applications/ResolvePython'))
        if not runtime.is_file(): self.skipTest('ResolvePython not installed; set RESOLVE_PYTHON to validate launchers')
        scripts = pathlib.Path(__file__).resolve().parents[1] / 'scripts'
        for name in ('prepare.py', 'audit_prproj.py', 'convert.py', 'handoff.py'):
            run = subprocess.run([str(runtime), str(scripts/name), '--help'], capture_output=True, text=True, timeout=15)
            self.assertEqual(run.returncode, 0, run.stderr)

    def test_unknown_boolean_rejected(self):
        r=E.parse(self.xml);r.find('.//track/enabled').text='maybe';r.write(self.xml)
        with self.assertRaises(ValueError):prepare(self.xml,self.dir/'invalid')
    def test_no_sequences_rejected(self):
        self.xml.write_text('<xmeml version="4"/>')
        with self.assertRaises(ValueError):prepare(self.xml,self.dir/'empty')
    def test_nested_sequence_rejected(self):
        r=E.parse(self.xml);E.SubElement(r.find('.//clipitem'),'sequence');r.write(self.xml)
        with self.assertRaises(ValueError):prepare(self.xml,self.dir/'nested')


if __name__=='__main__': unittest.main()
