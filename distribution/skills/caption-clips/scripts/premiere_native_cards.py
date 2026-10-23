#!/usr/bin/env python3
"""Build editable native caption graphics offline; verify the saved project.

This is a renderer/transport, not a transcriber or a second caption engine.
Style donors and project-specific choices are explicit external inputs.
"""
import argparse,base64,copy,gzip,hashlib,json,math,struct,sys,uuid
from pathlib import Path
from fractions import Fraction
import xml.etree.ElementTree as ET
# Staged Lab copy reuses canonical graph primitives without copying a second
# implementation. The normal installed sibling package remains the first choice.
sys.dont_write_bytecode=True
if not (Path(__file__).resolve().parent/'native_graphics').is_dir():
    sys.path.append(str(Path("__ACQ_SKILLS__/caption-clips/scripts")))
from native_graphics.native_caption_batch_graph import build_batch,insert_batch
from native_graphics.decode_graphic_text import decode_runs
from native_graphics.caption_style_review import validate as validate_style_review
from native_graphics.native_styled_text_probe import replace_font_identifiers
from native_graphics.native_canvas import sequence_canvas,media_canvas,geometry_problems,payload_box

TICKS=254016000000

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '_shared'))
from premiere_graph_integrity import validate_aliases

def load(path):
    blob=Path(path).read_bytes()
    return ET.fromstring(gzip.decompress(blob) if blob[:2]==b'\x1f\x8b' else blob)

def objects(root):return {n.get('ObjectID'):n for n in root if n.get('ObjectID')}

def track_items(root,uid,index):
    ids=objects(root);uids={n.get('ObjectUID'):n for n in root if n.get('ObjectUID')}
    def resolve(e):return ids[e.get('ObjectRef')] if e.get('ObjectRef') else uids[e.get('ObjectURef')]
    seq=uids[uid];tracks=[]
    if seq.tag!='Sequence':raise ValueError('Sequence identity required')
    for r in seq.findall('TrackGroups/TrackGroup/Second'):
        group=resolve(r)
        if group.tag=='VideoTrackGroup':
            tracks.extend(resolve(t) for t in group.findall('TrackGroup/Tracks/Track') if t.get('Index')==str(index))
    if len(tracks)!=1:raise ValueError('Exact unique caption track required')
    return seq,[resolve(r) for r in tracks[0].findall('ClipTrack/ClipItems/TrackItems/TrackItem')]

def pool(root):
    result={}
    for n in root.iter('StartKeyframeValue'):
        if n.get('BinaryHash') and n.get('Encoding')=='base64' and n.text:
            b=base64.b64decode(n.text);key=n.get('BinaryHash')
            if key in result and result[key]!=b:raise ValueError('Conflicting payload hash')
            result[key]=b
    return result

def text_node(root,item):
    ids=objects(root);chain=ids[item.find('ClipTrackItem/ComponentOwner/Components').get('ObjectRef')]
    nodes=[]
    for ref in chain.findall('ComponentChain/Components/Component'):
        fx=ids[ref.get('ObjectRef')]
        if fx.findtext('MatchName')=='AE.ADBE Text':
            nodes.extend(ids[r.get('ObjectRef')].find('StartKeyframeValue') for r in fx.findall('Component/Params/Param')
                         if ids[r.get('ObjectRef')].findtext('Name')=='Source Text')
    if len(nodes)!=1 or nodes[0] is None:raise ValueError('Exactly one native text layer required')
    return nodes[0]

def text_position(root,item):
    """Write the native Text layer position, not the clip's outer Motion.

    Donor position is only a calibration seed. Every resolved card owns an
    explicit center/y contract so a donor authored on another canvas cannot
    shift or clip an otherwise valid two-line phrase.
    """
    ids=objects(root);chain=ids[item.find('ClipTrackItem/ComponentOwner/Components').get('ObjectRef')]
    hits=[]
    for ref in chain.findall('ComponentChain/Components/Component'):
        fx=ids[ref.get('ObjectRef')]
        if fx.findtext('MatchName')!='AE.ADBE Text':continue
        for param_ref in fx.findall('Component/Params/Param'):
            param=ids[param_ref.get('ObjectRef')]
            if param.findtext('Name')=='Position':hits.append(param)
    if len(hits)!=1:raise ValueError('Exactly one native text position is required')
    key=hits[0].find('StartKeyframe')
    parts=key.text.split(',')
    if len(parts)<2 or ':' not in parts[1]:raise ValueError('Unknown native text position schema')
    x,y=parts[1].split(':',1)
    return [float(x),float(y)],key,parts

def set_text_position(root,item,x_pct,y_pct):
    current,key,parts=text_position(root,item)
    parts[1]=f'{float(x_pct):.9f}:{float(y_pct):.9f}'
    key.text=','.join(parts)

def position_mode(profile):
    """Whether a card owns an explicit position, or inherits the donor's.

    Two donor conventions exist and they are NOT interchangeable:

    * ``donors_by_style`` profiles are SEED donors. Their text position is a
      calibration artefact, so every resolved card is centered and placed from
      its own ``y_pct``.
    * legacy per-speaker ``donors`` profiles carry an APPROVED baked position
      (e.g. a top-left-anchored box at x=0.09 whose text is centered *inside the
      box*). Overwriting that with x=0.5 shifts the whole card right by ~40% of
      frame width and clips it -- the donor position IS the approved look.

    Defaulting by profile shape keeps existing profiles working untouched;
    ``text_position_mode`` overrides it explicitly when a profile needs the
    other convention.
    """
    mode=profile.get('text_position_mode')
    if mode in ('explicit_centered','donor'):return mode
    if mode is not None:raise ValueError('Unknown text_position_mode: '+str(mode))
    return 'explicit_centered' if 'donors_by_style' in profile else 'donor'

def payload(node,shared):
    return base64.b64decode(node.text) if node.get('Encoding')=='base64' and node.text else shared[node.get('BinaryHash')]

def card_position(profile,card,donor_position,mode):
    """Explicit opt-in Y transport preserving the donor's point/box convention."""
    y=card['y_pct'];base=profile['y_pct']
    if any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=100 for v in (y,base)):
        raise ValueError('Finite in-canvas caption Y percentages required')
    if y!=base:
        adapter=profile.get('position_adapter',{})
        if adapter.get('schema')!='native-text-position-offset/v1' or adapter.get('segment_y_pct',{}).get(card['id'])!=y:
            raise ValueError('Position differs from approved donor; explicit per-segment position adapter needed')
    if mode=='explicit_centered':return [0.5,y/100.0]
    if mode!='donor' or len(donor_position)!=2 or any(not math.isfinite(v) for v in donor_position):raise ValueError('Known native donor position required')
    return [donor_position[0],donor_position[1]+(y-base)/100.0]

def donor_run_offset(donor,word):
    """Return the donor run for one resolved word without flattening italic state.

    Legacy profiles have one italic contract per speaker. New profiles may expose
    both upright and italic face runs in the same donor: {weight:{upright:N,
    italic:N}}. An unavailable run is an explicit setup error, never a reason to
    replace the word with the base face.
    """
    try: candidate=donor['runs'][word['weight']]
    except KeyError: raise ValueError('Donor lacks requested weight: '+str(word.get('weight')))
    if isinstance(candidate,dict):
        state='italic' if word.get('italic') else 'upright'
        if state not in candidate: raise ValueError('Donor lacks requested '+state+' run for '+str(word.get('weight')))
        return candidate[state]
    if bool(word.get('italic'))!=bool(donor.get('italic')):
        raise ValueError('Unsupported italic change; prepare an explicit italic donor run')
    return candidate

def donor_for_card(profile,card):
    """Resolve a reviewed single-style donor without weakening legacy profiles.

    A profile may retain the legacy per-speaker ``donors`` map, or expose
    ``donors_by_style`` for native face switching. Style donors intentionally
    require every visible word in one reveal state to share the selected face;
    mixed-run cards still require a calibrated multi-run donor.
    """
    if 'donors_by_style' not in profile:
        return profile['donors'][card['speaker']]
    styles={(w.get('font_postscript'),bool(w.get('italic'))) for w in card['words']}
    if len(styles)!=1:raise ValueError('Style-donor cards must be homogeneous; split or review the semantic card')
    face,italic=next(iter(styles))
    if italic:key='italic'
    elif face=='Inter-SemiBold':key='semibold'
    else:key='regular'
    try:return profile['donors_by_style'][key]
    except KeyError:raise ValueError('Prepared profile lacks '+key+' donor')

def word_requests(card,donor,runs):
    """Preserve explicit line breaks instead of flattening native two-line cards."""
    requests=[];cursor=0;text=card['text']
    for i,w in enumerate(card['words']):
        token=w['text'];at=donor_run_offset(donor,w)
        if i==0:
            separator=''
        else:
            found=text.find(token,cursor)
            if found<0:raise ValueError('Word/card text mismatch')
            separator=text[cursor:found]
            if separator not in (' ','\n'):raise ValueError('Unsupported native word separator')
        # Premiere's native Source Text payload uses CR for a visual paragraph
        # break. LF survives saved-file readback but renders as a missing-glyph
        # box and leaves the phrase on one clipped line.
        native_separator='\r' if separator=='\n' else separator
        requests.append((at,native_separator+token));cursor=text.find(token,cursor)+len(token)
    if ''.join(t for _,t in requests).replace('\r','\n')!=text:raise ValueError('Word/card text mismatch')
    return requests

def build(project,profile_path,manifest_path,output,sequence_name,revision_path=None):
    output=Path(output);receipt_path=output.with_suffix('.receipt.json')
    if output.exists() or receipt_path.exists():raise FileExistsError(output)
    project=Path(project);source_hash=hashlib.sha256(project.read_bytes()).hexdigest()
    input_hashes={str(Path(p).resolve()):hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in (project,profile_path,manifest_path)}
    profile=json.loads(Path(profile_path).read_text());manifest=json.loads(Path(manifest_path).read_text())
    style_review=validate_style_review(manifest)
    if profile['project_sha256']!=source_hash:raise ValueError('Prepared project changed; refresh profile after reviewing edits')
    mode=position_mode(profile)
    root=load(project);validate_aliases(root);shared=pool(root);ids=objects(root)
    seq,old=track_items(root,profile['sequence_uid'],profile['track_index'])
    if [n.get('ObjectID') for n in old]!=profile['expected_item_ids']:raise ValueError('Caption track identity changed')
    scope=None
    if revision_path is not None:
        from native_caption_revision import load_scope,merge_scope,assert_protected_graph,verify_inputs,receipt_scope
        scope=load_scope(project,profile,manifest,revision_path,old,verify)
    # Canvas gate. A donor's paragraph box and its Graphic media frame are absolute
    # pixels of the canvas it was authored on; only Position is normalized. A donor
    # from a 2160x3840 template cloned into 1080x1920 rendered off-centre and could
    # not be clicked to edit, while every text/run/timing readback still passed.
    canvas=sequence_canvas(root,profile['sequence_uid'])
    for label,declared in (('profile donor_canvas',profile.get('donor_canvas')),('manifest canvas_px',manifest.get('canvas_px'))):
        if declared is not None and tuple(declared)!=tuple(canvas):
            raise ValueError(f'{label} {declared[0]}x{declared[1]} does not match the target sequence {canvas[0]}x{canvas[1]}')
    checked_donors=set()
    rate=Fraction(manifest['frame_rate']['numerator'],manifest['frame_rate']['denominator']);step=Fraction(TICKS,1)/rate
    if step.denominator!=1:raise ValueError('Frame rate is not representable by integer Premiere ticks')
    # `.get(a, manifest['cards'])` evaluated the default EAGERLY, so a manifest
    # carrying render_segments and no cards raised KeyError before the get ran.
    # Key PRESENCE is the selector, not truthiness: `or` would silently fall back
    # to 'cards' for an empty render_segments list, which is a different manifest.
    step=int(step);plan=[]
    cards=manifest['render_segments'] if 'render_segments' in manifest else manifest.get('cards')
    if cards is None:raise ValueError('Manifest has neither render_segments nor cards')
    all_cards=cards
    if scope is not None:cards=[c for c in cards if c['id'] in scope['plan']['after_segment_ids']]
    for c in cards:
        for k in ('start_frame','end_frame'):
            if type(c[k]) is not int:raise ValueError('Integer frame intervals required')
        elapsed=c.get('animation_elapsed_frames',0)
        if type(elapsed)is not int or elapsed<0:raise ValueError('Invalid animation phase')
        card_position(profile,c,[0.0,0.0],mode)  # Validate the explicit per-segment contract before cloning.
        size=c['font_size_px']
        if not isinstance(size,(int,float)) or not math.isfinite(size) or size<=0:raise ValueError('Resolved finite font size required')
        donor=donor_for_card(profile,c);item=ids[donor['item_id']]
        if donor['item_id'] not in checked_donors:
            problems=geometry_problems(canvas=canvas,media=media_canvas(root,item),position=text_position(root,item)[0],
                                       box=payload_box(payload(text_node(root,item),shared)),mode=mode,y_pct=profile['y_pct'])
            if problems:raise ValueError(f"Donor {donor['item_id']} does not fit the {canvas[0]}x{canvas[1]} target: "+'; '.join(problems))
            checked_donors.add(donor['item_id'])
        sub=ids[item.find('ClipTrackItem/SubClip').get('ObjectRef')];clip=ids[sub.find('Clip').get('ObjectRef')]
        runs=decode_runs(payload(text_node(root,item),shared))
        for w in c['words']:
            at=donor_run_offset(donor,w)
            source_face=runs[at]['font_postscript']
            resolved_face=profile.get('font_replacements',{}).get(source_face,source_face)
            if 'font_postscript' in w and resolved_face!=w['font_postscript']:
                raise ValueError('Exact requested face not present in selected donor run')
            if w['color']!=donor['color']:raise ValueError('Unsupported color change')
        requests=word_requests(c,donor,runs)
        plan.append(dict(id=c['id'],donor_item_id=donor['item_id'],shared_ids=[clip.find('Clip/Source').get('ObjectRef')],
            external_uids=[sub.find('MasterClip').get('ObjectURef')],start_ticks=c['start_frame']*step,
            end_ticks=c['end_frame']*step,animation_elapsed_ticks=elapsed*step,runs=requests))
    built,receipts=build_batch(root,plan,shared) if plan or scope is None else (copy.deepcopy(root),[])
    insertion=None
    if scope is None:
        insertion=insert_batch(built,sequence_uid=profile['sequence_uid'],track_index=profile['track_index'],
                               expected_old_item_ids=profile['expected_item_ids'],receipts=receipts)
    ids=objects(built)
    for row,card in zip(receipts,cards):
        node=text_node(built,ids[row['item_id']]);raw=payload(node,shared)
        replacements=profile.get('font_replacements',{})
        present={run['font_postscript'] for run in decode_runs(raw)}
        active={source:target for source,target in replacements.items() if source in present}
        if active:raw=replace_font_identifiers(raw,active)
        b=bytearray(raw);seen=set()
        for run in decode_runs(b):
            at=run['style_table_offset']
            if at in seen:continue
            seen.add(at);vt=at-struct.unpack_from('<i',b,at)[0]
            # FlatBuffers truncates trailing absent slots, so the font-size slot
            # (field 1, at vt+6) may not exist. Reading it unchecked returned bytes
            # from whatever followed the vtable and the next line wrote a float at a
            # garbage offset -- then expected_runs was decoded from that SAME
            # corrupted buffer, so verify() compared the corruption against itself
            # and passed. decode_runs.field() has had this guard all along.
            if struct.unpack_from('<H',b,vt)[0]<8:raise ValueError('Donor lacks explicit font size')
            offset=struct.unpack_from('<H',b,vt+6)[0]
            if not offset:raise ValueError('Donor lacks explicit font size')
            struct.pack_into('<f',b,at+offset,card['font_size_px'])
        node.set('Encoding','base64');node.set('BinaryHash',str(uuid.uuid4()));node.text=base64.b64encode(b).decode()
        donor_position=text_position(built,ids[row['item_id']])[0]
        desired=card_position(profile,card,donor_position,mode)
        if mode=='explicit_centered' or card['y_pct']!=profile['y_pct']:
            set_text_position(built,ids[row['item_id']],*desired)
        row['expected_text_position']=desired
        if card['y_pct']!=profile['y_pct']:
            row['position_transport']={'schema':'native-text-position-offset/v1','donor_position':donor_position,'base_y_pct':profile['y_pct'],'target_y_pct':card['y_pct'],'native_verified':False}
        row['expected_runs']=decode_runs(b)
        # Intent, not observation: recorded from the profile so verify() can fail.
        row['y_pct']=card['y_pct'];row['intended_center_px']=[0.5*canvas[0],card['y_pct']/100.0*canvas[1]]
    partial=None
    if scope is not None:
        insertion,receipts=merge_scope(root,built,profile,scope,receipts,all_cards,insert_batch)
        proof=assert_protected_graph(root,built,profile);verify_inputs(scope)
        partial=receipt_scope(scope,proof)
    old_uid=profile['sequence_uid'];new_uid=str(uuid.uuid4())
    for e in built.iter():
        for k,v in list(e.attrib.items()):
            if v==old_uid:e.set(k,new_uid)
        if e.text and old_uid in e.text:e.text=e.text.replace(old_uid,new_uid)
    final=next(s for s in built.findall('Sequence') if s.get('ObjectUID')==new_uid);final.find('Name').text=sequence_name
    if hashlib.sha256(project.read_bytes()).hexdigest()!=source_hash:raise ValueError('Prepared project changed during build')
    if any(hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h for p,h in input_hashes.items()):raise ValueError('Builder inputs changed during construction')
    validate_aliases(built)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb') as f:f.write(gzip.compress(ET.tostring(built,encoding='utf-8',xml_declaration=True),mtime=0))
    receipt=dict(status='OFFLINE_BUILT_REQUIRES_PREMIERE_SAVE_REOPEN_AND_RENDER',target=str(output.resolve()),
        sequence_uid=new_uid,sequence_name=sequence_name,track_index=profile['track_index'],canvas=list(canvas),position_mode=mode,cards=receipts,insertion=insertion,style_review=style_review,
        inputs=[dict(path=str(Path(p).resolve()),sha256=hashlib.sha256(Path(p).read_bytes()).hexdigest()) for p in (project,profile_path,manifest_path)])
    if partial is not None:
        receipt['partial_revision']=partial
        receipt['inputs'].extend([partial['request'],*partial['inputs']])
    with receipt_path.open('x') as f:json.dump(receipt,f,indent=2)
    verify(output,receipt_path)
    return receipt

def verify(project,receipt_path):
    r=json.loads(Path(receipt_path).read_text());root=load(project);validate_aliases(root);shared=pool(root);ids=objects(root)
    seq,items=track_items(root,r['sequence_uid'],r['track_index'])
    if seq.findtext('Name')!=r['sequence_name'] or len(items)!=len(r['cards']):raise ValueError('Saved identity/count mismatch')
    canvas=sequence_canvas(root,r['sequence_uid'])
    if r.get('canvas') is not None and tuple(r['canvas'])!=tuple(canvas):raise ValueError('Saved sequence canvas differs from the built canvas')
    for item,want in zip(items,r['cards']):
        ci=item.find('ClipTrackItem');sub=ids[ci.find('SubClip').get('ObjectRef')];clip=ids[sub.find('Clip').get('ObjectRef')]
        timing=dict(start_ticks=ci.findtext('TrackItem/Start','0'),end_ticks=ci.findtext('TrackItem/End'),
                    source_in_ticks=clip.findtext('Clip/InPoint','0'),source_out_ticks=clip.findtext('Clip/OutPoint'))
        if any(timing[k]!=want['timing'][k] for k in timing):raise ValueError('Saved frame/source clock mismatch')
        runs=decode_runs(payload(text_node(root,item),shared));expected=want['expected_runs']
        if len(runs)!=len(expected):raise ValueError('Saved run count mismatch')
        for a,b in zip(runs,expected):
            for k in ('text','font_postscript','font_size_raw','fill_rgb_explicit','synthetic_italic_raw'):
                if a.get(k)!=b.get(k):raise ValueError('Saved run property mismatch: '+k)
        position=text_position(root,item)[0]
        if any(abs(a-b)>1e-6 for a,b in zip(position,want['expected_text_position'])):
            raise ValueError('Saved native text position mismatch')
        # Independent geometry: the saved box/media/position must land the text where the
        # profile intended on THIS sequence -- not merely where the builder wrote it.
        problems=geometry_problems(canvas=canvas,media=media_canvas(root,item),position=position,
                                   box=payload_box(payload(text_node(root,item),shared)),
                                   mode=r.get('position_mode','donor'),y_pct=want.get('y_pct'))
        if problems:raise ValueError('Saved caption geometry is wrong: '+'; '.join(problems))
    return dict(status='SAVED_FILE_READBACK_PASS_NOT_RENDER_APPROVAL',cards=len(items),sequence_uid=r['sequence_uid'])

def main():
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='command',required=True)
    b=s.add_parser('build')
    for name in ('project','profile','manifest','output','sequence-name'):b.add_argument('--'+name,required=True)
    b.add_argument('--revision',help='Opt-in hash-bound partial-build request; separate output copy only')
    v=s.add_parser('verify');v.add_argument('--project',required=True);v.add_argument('--receipt',required=True)
    a=p.parse_args()
    if a.command=='build':
        r=build(a.project,a.profile,a.manifest,a.output,a.sequence_name,revision_path=a.revision)
        print(json.dumps(dict(target=r['target'],sequence_uid=r['sequence_uid'],cards=len(r['cards']),status=r['status'])))
    else:print(json.dumps(verify(a.project,a.receipt)))

if __name__=='__main__':main()
