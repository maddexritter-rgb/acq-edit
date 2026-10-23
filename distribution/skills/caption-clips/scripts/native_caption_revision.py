"""Optional scoped construction for the existing native Graphics builder.

Operates on its scratch XML graph only. All old graph objects remain; only the
owned track's references change. Native import/replacement is a separate route.
"""
import copy
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from plan_caption_revision import plan_revision
from premiere_stage_handoff import fingerprint


def checked(row):
    p=Path(row['path'])
    if not p.is_absolute() or not p.is_file():raise ValueError('Absolute existing revision input required')
    data=p.read_bytes()
    if hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValueError('Revision input changed')
    return json.loads(data)


def load_scope(project,profile,manifest,revision_path,old_items,verify):
    revision_path=Path(revision_path).resolve()
    blob=revision_path.read_bytes();request=json.loads(blob)
    if request.get('schema')!='edit.caption-partial-build/v1':raise ValueError('Explicit partial caption build request required')
    source_hash=hashlib.sha256(Path(project).read_bytes()).hexdigest()
    if request.get('source_project_sha256')!=source_hash:raise ValueError('Partial build source project changed')
    before,receipt,mapping,snapshot,plan=(checked(request[k]) for k in ('before_manifest','prior_receipt','native_map','snapshot','revision_plan'))
    if receipt['sequence_uid']!=profile['sequence_uid'] or receipt['track_index']!=profile['track_index']:raise ValueError('Prior caption receipt target differs from prepared profile')
    if not any(r['path']==request['before_manifest']['path'] and r['sha256']==request['before_manifest']['sha256'] for r in receipt['inputs']):raise ValueError('Prior receipt does not bind the original manifest')
    expected=plan_revision(before,manifest,mapping,snapshot,plan['target']['expected_revision'])
    if any(plan.get(k)!=v for k,v in expected.items()):raise ValueError('Revision scope no longer matches resolved manifests/native baseline')
    if expected['status']=='NO_CHANGE':raise ValueError('No caption change to rebuild')
    if expected['target']['sequence_id']!=profile['sequence_uid'] or mapping['track_index']!=profile['track_index']:raise ValueError('Revision native target differs from prepared source sequence')
    verify(project,request['prior_receipt']['path'])
    prior_cards=receipt['cards'];segments=before['render_segments']
    if len(prior_cards)!=len(old_items) or [c['id'] for c in prior_cards]!=[c['id'] for c in segments]:raise ValueError('Prior receipt/manifest/item order changed')
    retained={}
    for card,item,segment in zip(prior_cards,old_items,segments):
        if card['id'] not in expected['before_segment_ids']:
            revised=next((r for r in manifest['render_segments'] if r['id']==card['id']),None)
            if revised!=segment:raise ValueError('Unselected caption differs from its original resolved segment')
            record=copy.deepcopy(card);record['item_id']=item.get('ObjectID');retained[card['id']]=record
    if not manifest['render_segments']:raise ValueError('Empty caption lane requires a separately validated clear operation')
    return {'request':request,'request_artifact':{'path':str(revision_path),'sha256':hashlib.sha256(blob).hexdigest()},
            'plan':expected,'retained':retained,'source_project_sha256':source_hash}


def caption_track(root,profile):
    objects={n.get('ObjectID'):n for n in root if n.get('ObjectID')};uids={n.get('ObjectUID'):n for n in root if n.get('ObjectUID')}
    def resolve(ref):return objects[ref.get('ObjectRef')] if ref.get('ObjectRef') else uids[ref.get('ObjectURef')]
    seq=uids[profile['sequence_uid']];tracks=[]
    for ref in seq.findall('TrackGroups/TrackGroup/Second'):
        group=resolve(ref)
        if group.tag=='VideoTrackGroup':tracks.extend(resolve(t) for t in group.findall('TrackGroup/Tracks/Track') if t.get('Index')==str(profile['track_index']))
    if len(tracks)!=1:raise ValueError('Exact unique caption track required')
    return tracks[0]


def merge_scope(original,built,profile,scope,new_receipts,cards,insert_batch):
    """Reuse existing insert_batch validation, retaining unaffected item objects."""
    generated={r['id']:r for r in new_receipts}
    if len(generated)!=len(new_receipts) or set(generated)!=set(scope['plan']['after_segment_ids']):raise ValueError('Generated scope differs from revision plan')
    combined={**scope['retained'],**generated}
    if len(combined)!=len(cards) or set(combined)!={c['id'] for c in cards}:raise ValueError('Partial replacement cannot omit or invent caption segments')
    receipts=[combined[c['id']] for c in cards]
    track=caption_track(built,profile);container=track.find('ClipTrack/ClipItems/TrackItems')
    if container is None or any(e.tag!='TrackItem' for e in container) or [e.get('ObjectRef') for e in container]!=profile['expected_item_ids']:raise ValueError('Partial track precondition changed')
    # Scratch graph only. insert_batch validates unshared ownership and refuses
    # any retained item which has another consumer after this lane is detached.
    for ref in list(container):container.remove(ref)
    insertion=insert_batch(built,sequence_uid=profile['sequence_uid'],track_index=profile['track_index'],expected_old_item_ids=[],receipts=receipts)
    insertion.update(replaced_reference_count=len(scope['plan']['before_segment_ids']),inserted_count=len(new_receipts),retained_reference_count=len(scope['retained']),partial=True)
    return insertion,receipts


def assert_protected_graph(original,built,profile):
    """Byte-equivalent old object subtrees except the exact owned track refs.

    Executed before the builder's existing new sequence UUID/name rewrite.
    Persistence can renumber objects; this is offline construction proof only.
    """
    old_track=caption_track(original,profile);new_track=caption_track(built,profile)
    if len(built)<len(original):raise ValueError('Partial build removed pre-existing graph objects')
    digest=hashlib.sha256();count=0
    for old,new in zip(original,built):
        if old is old_track:
            if new is not new_track:raise ValueError('Caption track object order changed')
            a,b=copy.deepcopy(old),copy.deepcopy(new)
            for node in (a,b):
                container=node.find('ClipTrack/ClipItems/TrackItems')
                if container is not None:
                    for ref in list(container):container.remove(ref)
            left,right=ET.tostring(a),ET.tostring(b)
        else:left,right=ET.tostring(old),ET.tostring(new)
        if left!=right:raise ValueError('Partial build changed a protected existing graph object')
        digest.update(len(left).to_bytes(8,'big'));digest.update(left);count+=1
    return {'status':'OFFLINE_EXISTING_OBJECTS_PRESERVED_EXCEPT_OWNED_TRACK_REFERENCES','protected_objects':count,
            'normalized_graph_sha256':digest.hexdigest(),'sequence_identity_rewrite':'separate_existing_builder_step','native_persistence':'not_verified'}


def verify_inputs(scope):
    checked(scope['request_artifact'])
    for key in ('before_manifest','prior_receipt','native_map','snapshot','revision_plan'):checked(scope['request'][key])


def receipt_scope(scope,proof):
    return {'schema':'edit.caption-partial-build-evidence/v1','request':scope['request_artifact'],
            'inputs':[scope['request'][k] for k in ('before_manifest','prior_receipt','native_map','snapshot','revision_plan')],
            'source_project_sha256':scope['source_project_sha256'],'revision_plan_sha256':fingerprint(scope['plan']),
            'rebuilt_segments':scope['plan']['after_segment_ids'],'removed_or_replaced_segments':scope['plan']['before_segment_ids'],
            'retained_segments':list(scope['retained']),'protected_graph':proof,'live_replacement':'not_run'}


def transfer_precondition(receipt,manifest):
    """Carry a partial build's source baseline into the existing import guard.

    This only permits importing a separate revised sequence. It does not replace
    the source sequence, attest a saved file to current host state, or prove an
    in-place caption edit. The import's whole-project guard closes the interval
    between the caller's fresh read and dispatch.
    """
    evidence=receipt.get('partial_revision')
    if evidence is None:return None
    if evidence.get('schema')!='edit.caption-partial-build-evidence/v1':raise ValueError('Unknown partial caption evidence')
    request=checked(evidence['request'])
    if request.get('schema')!='edit.caption-partial-build/v1':raise ValueError('Unknown partial caption request')
    keys=('before_manifest','prior_receipt','native_map','snapshot','revision_plan')
    artifacts=[evidence['request']]+[request[k] for k in keys]
    if evidence['inputs']!=artifacts[1:] or any(a not in receipt['inputs'] for a in artifacts):raise ValueError('Partial dependency is not bound by the builder receipt')
    before,prior,mapping,snapshot,plan=(checked(request[k]) for k in keys)
    if not any(a.get('sha256')==request['source_project_sha256'] for a in receipt['inputs']) or evidence['source_project_sha256']!=request['source_project_sha256']:
        raise ValueError('Partial source hash does not match builder inputs')
    expected=plan_revision(before,manifest,mapping,snapshot,plan['target']['expected_revision'])
    if any(plan.get(k)!=v for k,v in expected.items()) or fingerprint(expected)!=evidence['revision_plan_sha256']:
        raise ValueError('Prepared partial dependency plan changed')
    if prior['sequence_uid']!=expected['target']['sequence_id'] or prior['track_index']!=receipt['track_index'] or mapping['track_index']!=receipt['track_index']:
        raise ValueError('Prepared partial source identity differs')
    retained=[r['id'] for r in before['render_segments'] if r['id'] not in expected['before_segment_ids']]
    if evidence['rebuilt_segments']!=expected['after_segment_ids'] or evidence['removed_or_replaced_segments']!=expected['before_segment_ids'] or evidence['retained_segments']!=retained:
        raise ValueError('Prepared partial scope differs from resolved dependency plan')
    if receipt['sequence_uid']==expected['target']['sequence_id']:raise ValueError('Prepared revision must have a separate new sequence identity')
    return {'schema':'edit.caption-revision-precondition/v1','target':expected['target'],
            'source_snapshot':snapshot,'source_snapshot_sha256':fingerprint(snapshot),
            'revision_plan_sha256':fingerprint(expected),'artifacts':artifacts,
            'review':expected['review'],'route':'separate_sequence_import_not_in_place_replacement'}


def assert_transfer_baseline(precondition,project):
    """Refuse a historical replay when the actual source sequence has drifted."""
    if precondition is None:return
    if precondition.get('schema')!='edit.caption-revision-precondition/v1':raise ValueError('Unknown caption revision precondition')
    for artifact in precondition['artifacts']:checked(artifact)
    identity=precondition['target']
    rows=[s for s in project['sequences'] if s['sequence_id']==identity['sequence_id']]
    if project['project_path']!=identity['project_path'] or len(rows)!=1:raise ValueError('Partial revision source project/sequence is not the current target')
    snapshot=rows[0]['snapshot']
    if snapshot!=precondition['source_snapshot'] or fingerprint(snapshot)!=precondition['source_snapshot_sha256']:
        raise ValueError('Partial revision source changed since planning; inspect and rebuild from fresh state')
