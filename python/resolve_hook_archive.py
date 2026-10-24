"""Append one self-contained native Fusion track to a new Resolve DRT checkpoint.

Only Resolve 21.1.1.0010 archives are accepted. The parent archive is immutable;
all its existing entries/bytes survive except insertion into VideoTrackVec.
"""
import re
import zipfile
from common import require, sha
from resolve_music_archive import archive_entries, sequence, replace_field
from resolve_precision import field, read_time


def append_hook(parent, donor, target, prepared):
    require(not target.exists(), 'Hook archive exists; reconcile before retrying')
    parent_hash, donor_hash = sha(parent), sha(donor)
    entries, donors = archive_entries(parent), archive_entries(donor)
    info, data = sequence(entries); _, sample = sequence(donors)
    regions = re.findall(rb'<VideoTrackVec>(.*?)</VideoTrackVec>', data, re.S)
    donor_regions = re.findall(rb'<VideoTrackVec>(.*?)</VideoTrackVec>', sample, re.S)
    require(len(regions)==len(donor_regions)==1, 'Expected native video track vectors')
    tracks = re.findall(rb'<Sm2TiTrack\b[^>]*>.*?</Sm2TiTrack>', regions[0], re.S)
    donor_tracks = re.findall(rb'<Sm2TiTrack\b[^>]*>.*?</Sm2TiTrack>', donor_regions[0], re.S)
    require(tracks and len(donor_tracks)==1, 'Hook donor requires one independent native track')
    track = donor_tracks[0]
    clips = re.findall(rb'<Sm2TiVideoClip\b[^>]*>.*?</Sm2TiVideoClip>', track, re.S)
    require(len(clips)==1 and b'<Sm2TiAudioClip' not in sample and b'<MediaRef>' not in track, 'Hook donor must contain only a self-contained Fusion generator')
    clip = clips[0]
    require(field(clip,'PrettyType')[1]==b'Fusion Composition' and field(clip,'Name')[1].decode()==prepared['name'], 'Unexpected native hook generator identity')
    require(read_time(field(clip,'Start')[1].decode())==0 and read_time(field(clip,'In')[1].decode())==0 and not field(clip,'MediaFilePath')[1], 'Hook donor has media or an offset source clock')
    require(len(re.findall(rb'<CompositionBA>[^<]+</CompositionBA>',clip))==1, 'Expected one embedded Fusion graph')
    known=set(re.findall(rb'DbId="([^"]+)"',b''.join(b for _,b in entries)))
    added=re.findall(rb'DbId="([^"]+)"',track)
    require(len(added)==len(set(added)) and not known.intersection(added), 'Native hook donor identity collision')
    sequence_id=field(tracks[0],'Sequence')[1]
    require(all(field(t,'Sequence')[1]==sequence_id for t in tracks),'Ambiguous parent sequence identity')
    track=replace_field(track,'Sequence',sequence_id)
    end=prepared['intervals'][-1]['endFrame']
    require(type(end)==int and end>0,'Invalid hook duration')
    replacement=replace_field(clip,'Duration',str(end).encode())
    require(track.count(clip)==1,'Ambiguous generator payload');track=track.replace(clip,replacement,1)
    insertion=b'  <Element>\n'+track+b'\n  </Element>\n'
    changed=data.replace(b'</VideoTrackVec>',insertion+b'</VideoTrackVec>',1)
    require(changed.replace(insertion,b'',1)==data,'Hook archive changed existing sequence bytes')
    with zipfile.ZipFile(target,'x') as output:
        for entry,body in entries:output.writestr(entry,changed if entry.filename==info.filename else body)
    with zipfile.ZipFile(target) as output:
        require(output.namelist()==[i.filename for i,_ in entries], 'Hook archive changed entry order/coverage')
        for entry,body in entries:require(output.read(entry.filename)==(changed if entry.filename==info.filename else body),'Hook archive readback differs')
    require(sha(parent)==parent_hash and sha(donor)==donor_hash,'Input archive changed')
    return {'schema':'acq-edit/resolve-hook-track-v1','parentSha256':parent_hash,'donorSha256':donor_hash,'outputSha256':sha(target),'addedTrack':len(tracks)+1,'hookFrames':end,'existingBytesPreserved':True,'nativeImportRequired':True}
