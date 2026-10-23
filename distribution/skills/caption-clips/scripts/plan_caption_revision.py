#!/usr/bin/env python3
"""Compute a caption-owned revision scope; never group words or edit Premiere.

Consumes already resolved before/after manifests and the actual native card map.
Expands through semantic cards, shared source occurrences and changed cut frames.
The resulting plan still requires a fresh bridge guard and a validated partial
rebuild/replacement route. A plan is not native execution or visual acceptance.
"""
import argparse
import hashlib
import json
from fractions import Fraction
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'_shared'))
from premiere_stage_handoff import exact, fingerprint, inventory, merge_ranges, target, BridgeError


def index_manifest(manifest):
    rate=manifest['frame_rate'];fps=Fraction(rate['numerator'],rate['denominator'])
    step=Fraction(254016000000,1)/fps
    if fps<=0 or step.denominator!=1:raise BridgeError('Exact positive caption frame rate required')
    rows=manifest['render_segments']
    if not isinstance(rows,list) or len(rows)>10000:raise BridgeError('Bounded resolved render segments required')
    indexed={};groups={};words={};end=0;origins={}
    for row in rows:
        sid,cid=row.get('id'),row.get('semantic_card_id')
        if not isinstance(sid,str) or not sid or sid in indexed or not isinstance(cid,str) or not cid:raise BridgeError('Unique render and semantic card identities required')
        a,b,elapsed=(row.get(k) for k in ('start_frame','end_frame','animation_elapsed_frames'))
        if any(type(v)is not int for v in (a,b,elapsed)) or a<end or b<=a or elapsed<0 or elapsed>a:raise BridgeError('Ordered exact caption frame/animation clocks required')
        end=b;origin=a-elapsed
        if cid in origins and origins[cid]!=origin:raise BridgeError('Semantic reveal/continuation clock changed origin')
        origins[cid]=origin;indexed[sid]=row;groups.setdefault(cid,set()).add(sid)
        for word in row['words']:
            indices=word.get('source_indices')
            if not isinstance(indices,list) or not indices or any(type(i)is not int or i<0 for i in indices):raise BridgeError('Source occurrence IDs required for revision dependency checks')
            source=word.get('source_id')
            if source is not None and (not isinstance(source,str) or not source):raise BridgeError('Invalid source identity')
            for i in indices:words.setdefault((source,i),set()).add(cid)
    cuts=manifest.get('cut_frames',[])
    if not isinstance(cuts,list) or any(type(c)is not int or c<0 for c in cuts):raise BridgeError('Exact cut frames required')
    if any(row['start_frame']<cut<row['end_frame'] for row in rows for cut in cuts):raise BridgeError('Resolve render segments at every cut before revision planning')
    return indexed,groups,words,int(step),set(cuts)


def plan_revision(before,after,native_map,snapshot,revision):
    old,old_groups,old_words,step,old_cuts=index_manifest(before)
    new,new_groups,new_words,new_step,new_cuts=index_manifest(after)
    if step!=new_step or before.get('canvas_px')!=after.get('canvas_px'):raise BridgeError('Frame-rate/canvas changes require a separate retarget plan')
    if not isinstance(revision,str) or len(revision)!=64 or any(c not in '0123456789abcdef' for c in revision):raise BridgeError('Native snapshot revision required')
    identity=target(snapshot)
    if native_map.get('schema')!='edit.native-caption-map/v1' or {k:native_map.get(k) for k in identity}!=identity:raise BridgeError('Exact native caption map target required')
    tracks,items=inventory(snapshot)
    index=native_map['track_index'];lane={(native_id):entry for (kind,native_id),entry in items.items() if kind==0 and entry['track_index']==index}
    mapped={r['segment_id']:r for r in native_map['items']}
    if len(mapped)!=len(native_map['items']) or set(mapped)!=set(old) or len({r['native_item_id'] for r in mapped.values()})!=len(mapped) or {r['native_item_id'] for r in mapped.values()}!=set(lane):raise BridgeError('Native card mapping/lane inventory changed')
    for sid,row in mapped.items():
        segment=old[sid];item=lane[row['native_item_id']]['item']
        if row['semantic_card_id']!=segment['semantic_card_id'] or row['expected_text']!=segment['text']:raise BridgeError('Prior manifest differs from recorded native card map')
        if item.get('speed')!=1 or item.get('disabled') is not False or len([c for c in item.get('components',[]) if c.get('matchName')=='AE.ADBE Text'])!=1:raise BridgeError('Native Graphics playback/component changed')
        for field,key,frame in [('start','start_ticks','start_frame'),('end','end_ticks','end_frame')]:
            if exact(item[field])!=segment[frame]*step or item[field]!=row['timing'][key]:raise BridgeError('Native card timeline changed since mapping')
        if item['sourceId']!=row.get('native_source_id') or item['inPoint']!=row['timing']['source_in_ticks'] or item['outPoint']!=row['timing']['source_out_ticks']:raise BridgeError('Native card source identity/clock changed')
    reasons={};source_changes=set()
    def source_content(row):
        if row is None:return None
        return {k:v for k,v in row.items() if k in ('text','source_id','source_path','source_word_indices')} | {'words':[{k:v for k,v in w.items() if k in ('text','source_indices','source_id','source_path')} for w in row.get('words',[])]}
    def mark(cid,reason):reasons.setdefault(cid,set()).add(reason)
    for sid in old.keys()|new.keys():
        if fingerprint(old.get(sid))!=fingerprint(new.get(sid)):
            for rows in (old,new):
                if sid in rows:
                    mark(rows[sid]['semantic_card_id'],'changed_render_segment:'+sid)
                    if fingerprint(source_content(old.get(sid)))!=fingerprint(source_content(new.get(sid))):source_changes.add(rows[sid]['semantic_card_id'])
    if 'cards' in before or 'cards' in after:
        old_cards={c['id']:c for c in before.get('cards',[])};new_cards={c['id']:c for c in after.get('cards',[])}
        if len(old_cards)!=len(before.get('cards',[])) or len(new_cards)!=len(after.get('cards',[])):raise BridgeError('Ambiguous semantic card inventory')
        for cid in old_cards.keys()|new_cards.keys():
            if fingerprint(old_cards.get(cid))!=fingerprint(new_cards.get(cid)):
                if cid not in reasons:raise BridgeError('Semantic card changed without resolved render changes; rerun the existing resolver')
                mark(cid,'changed_semantic_card')
    # Style-review records/status are evidence metadata, not a renderer change.
    ignored={'render_segments','cards','cut_frames','style_review','status','fixture_scope'}
    old_global={k:v for k,v in before.items() if k not in ignored};new_global={k:v for k,v in after.items() if k not in ignored}
    if fingerprint(old_global)!=fingerprint(new_global):
        for cid in old_groups.keys()|new_groups.keys():mark(cid,'manifest_global_dependency_changed')
    changed_cuts=old_cuts^new_cuts
    for boundary in changed_cuts:
        for row in list(old.values())+list(new.values()):
            if row['start_frame']<=boundary<=row['end_frame']:mark(row['semantic_card_id'],'changed_cut_boundary:'+str(boundary))
    # A source occurrence may be repeated by reveal states or card boundaries.
    # Only an explicit source identity + index joins occurrences across cards.
    occurrences={}
    for catalog in (old_words,new_words):
        for key,cids in catalog.items():occurrences.setdefault(key,set()).update(cids)
    changed=True
    while changed:
        changed=False
        for cids in occurrences.values():
            if cids & source_changes:
                for cid in cids-source_changes:
                    mark(cid,'shared_source_occurrence_dependency');source_changes.add(cid);changed=True
    selected_old=[sid for sid,row in old.items() if row['semantic_card_id'] in reasons]
    selected_new=[sid for sid,row in new.items() if row['semantic_card_id'] in reasons]
    selected_ids={mapped[sid]['native_item_id'] for sid in selected_old}
    review_rows=[old[sid] for sid in selected_old]+[new[sid] for sid in selected_new]
    ranges=merge_ranges([(r['start_frame']*step,r['end_frame']*step) for r in review_rows])
    boundaries=changed_cuts|{r[k] for r in review_rows for k in ('start_frame','end_frame')}
    last_tick=max([exact(entry['item']['end']) for entry in items.values()]+[r['end_frame']*step for r in new.values()]+[0])
    frames=sorted({f for b in boundaries for f in (b-1,b,b+1) if 0<=f and f*step<last_tick})
    protected=[{'kind':kind,'native_item_id':nid,**entry} for (kind,nid),entry in items.items() if kind!=0 or nid not in selected_ids]
    return {'schema':'edit.caption-revision-plan/v1','status':'NO_CHANGE' if not reasons else 'DEPENDENCIES_RESOLVED_REBUILD_AND_NATIVE_ACCEPTANCE_REQUIRED',
            'target':{**identity,'expected_revision':revision},'before_manifest_sha256':fingerprint(before),'after_manifest_sha256':fingerprint(after),
            'native_map_sha256':fingerprint(native_map),'snapshot_sha256':fingerprint(snapshot),
            'affected_semantic_cards':[{'id':cid,'reasons':sorted(reasons[cid])} for cid in sorted(reasons)],
            'before_segment_ids':selected_old,'after_segment_ids':selected_new,'native_item_ids_to_replace':sorted(selected_ids),
            'protected_native_items':protected,'protected_native_items_sha256':fingerprint(protected),
            'review':{'picture_ranges':ranges,'boundary_frames':frames,'normal_final_review_required':True},
            'execution':'not_run','persistence':'not_run','rendered':'not_run',
            'limits':['Caller must re-read native state and bind a mutation guard immediately before writing.',
                      'Resolved manifests remain owned by the existing caption engine; this planner creates no text, timing or styles.',
                      'Partial rebuild/replacement requires its own validated transport; whole-sequence import does not prove it.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('before','after','native-map','snapshot','revision','output'):parser.add_argument('--'+key,required=True)
    args=parser.parse_args();paths=[Path(getattr(args,k)).resolve(strict=True) for k in ('before','after','native_map','snapshot')]
    blobs=[p.read_bytes() for p in paths];result=plan_revision(*(json.loads(b) for b in blobs),args.revision)
    result['input_artifacts']=[{'path':str(p),'sha256':hashlib.sha256(b).hexdigest()} for p,b in zip(paths,blobs)]
    if any(p.read_bytes()!=b for p,b in zip(paths,blobs)):raise BridgeError('Revision inputs changed during planning')
    with Path(args.output).open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps({'status':result['status'],'affected_cards':len(result['affected_semantic_cards']),'native_replacements':len(result['native_item_ids_to_replace'])}))


if __name__=='__main__':main()
