#!/usr/bin/env python3
"""Prepare separate native headline text lanes using the caption owner's graph.

Only a fresh offline project is written. Rounded background artwork is a separate
parameterized source asset, never a flattened headline or finished video. Import,
background placement, native readback and rendered geometry are still required.
"""
import argparse
import base64
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import uuid
import xml.etree.ElementTree as ET


def write(path, data):
    with Path(path).open('x') as f:
        json.dump(data, f, indent=2)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(args):
    sys.path.insert(0, str(args.skills/'caption-clips/scripts'))
    sys.path.insert(0, str(args.skills/'_shared'))
    import premiere_native_cards as native
    import premiere_graph_integrity as integrity
    from retarget_native_donor import retarget
    from prepare_premiere_caption_template import graft
    # New fill transport stays with the caption owner in this pinned repository.
    source=Path(__file__).resolve().parents[1]/'distribution/skills/caption-clips/scripts/native_graphics/native_text_fill.py'
    spec=importlib.util.spec_from_file_location('native_graphics.native_text_fill',source)
    fill=importlib.util.module_from_spec(spec);spec.loader.exec_module(fill)
    from PIL import Image, ImageDraw
    recipe=json.loads(args.recipe.read_text())
    if recipe['canvas'] != [1080,1920] or recipe['animation'] != 'none':
        raise ValueError('This preparation requires the measured static vertical recipe')
    intervals=recipe['placement_intervals']
    if len(intervals)!=1 or intervals[0]['start_seconds']!=0:
        raise ValueError('One opening interval required')
    interval=intervals[0]; texts=interval['native_text']; styles=interval['rendered_line_styles']
    if not texts or len(texts)!=len(styles) or [t['text'] for t in texts]!=recipe['display_lines']:
        raise ValueError('Recipe lines and native treatments differ')
    if any(s['foreground']!='#000000' for s in styles):
        raise ValueError('Explicit black headline recipe required')
    source_hash=sha(args.project);args.output.mkdir()
    plate=Image.new('RGBA', tuple(recipe['canvas']), (0,0,0,0));draw=ImageDraw.Draw(plate)
    bx,by,_,_=interval['hook_bounds']
    for box in interval['native_boxes']:
        x,y,w,h=box['bounds']
        draw.rounded_rectangle((bx+x,by+y,bx+x+w-1,by+y+h-1),radius=box['radius_px'],fill=box['color'])
    plate_path=args.output/'headline-background.png';plate.save(plate_path)
    current=args.project;uid=args.sequence_uid;receipts=[]
    for i,(text,style) in enumerate(zip(texts,styles)):
        folder=args.output/f'line-{i+1}';folder.mkdir()
        prep=folder/'graft.prproj';profile_path=folder/'graft-profile.json'
        graft(current,args.asset,uid,prep,profile_path,native,integrity)
        retargeted=folder/'retarget.prproj';retarget_profile=folder/'retarget-profile.json'
        retarget(prep,profile_path,retargeted,retarget_profile,normalize_generated_aliases=True)
        profile=json.loads(retarget_profile.read_text());root=native.load(retargeted)
        pool=native.pool(root);ids=native.objects(root)
        for donor in profile['donors'].values():
            node=native.text_node(root,ids[donor['item_id']])
            raw=fill.recolor_runs(native.payload(node,pool),[0,0,0])
            node.set('Encoding','base64');node.set('BinaryHash',str(uuid.uuid4()));node.text=base64.b64encode(raw).decode()
            donor['color']='000000'
        styled=folder/'black-donor.prproj'
        with styled.open('xb') as f:f.write(gzip.compress(ET.tostring(root,encoding='utf-8',xml_declaration=True),mtime=0))
        profile['project_sha256']=sha(styled)
        # Native point/paragraph convention is retained; render calibration is required.
        y_pct=(by+text['baseline_px'][1]-style['font_size_px']/2)/1920*100
        identity=f'headline-line-{i+1}'
        profile['position_adapter']={'schema':'native-text-position-offset/v1','segment_y_pct':{identity:y_pct}}
        styled_profile=folder/'black-profile.json';write(styled_profile,profile)
        card={'id':identity,'semantic_card_id':identity,'start_frame':0,'end_frame':round(interval['end_seconds']*30),
              'animation_elapsed_frames':30,'speaker':'host','text':text['text'],'y_pct':y_pct,
              'font_size_px':style['font_size_px'],'words':[{'text':w,'weight':'strong','italic':False,'font_postscript':'ProximaNova-Bold','color':'000000'} for w in text['text'].split()]}
        review={'mode':'editorial','reviewed':True,'segment_ids':[identity],
                'weight':{'status':'applied','reason':'Match the frozen bold opening headline.',
                          'targets':[{'segment_id':identity,'word_index':0,'text':card['words'][0]['text'],'value':'strong'}]},
                'size':{'status':'not_applicable','reason':'Use the measured recipe size without additional emphasis.'},
                'italic':{'status':'not_applicable','reason':'Frozen headline uses upright bold lettering.'}}
        manifest=folder/'manifest.json';write(manifest,{'frame_rate':{'numerator':30,'denominator':1},'canvas_px':[1080,1920],'render_segments':[card],'style_review':review})
        built=folder/'built.prproj'
        receipt=native.build(styled,styled_profile,manifest,built,args.sequence_name)
        receipts.append({'receipt':str(built.with_suffix('.receipt.json')),'track_index':receipt['track_index'],'text':text['text']})
        current=built;uid=receipt['sequence_uid']
    if sha(args.project)!=source_hash:raise ValueError('Source project changed during preparation')
    result={'schema':'acq-edit/premiere-hook-preparation-v1','status':'OFFLINE_ONLY_NATIVE_IMPORT_AND_BACKGROUND_PLACEMENT_REQUIRED',
            'source':{'path':str(args.project),'sha256':source_hash},'recipe':{'path':str(args.recipe),'sha256':sha(args.recipe)},
            'prepared':{'path':str(current),'sha256':sha(current)},'sequence_uid':uid,'lines':receipts,
            'background':{'path':str(plate_path),'sha256':sha(plate_path),'placement':'full_canvas_below_headline_text','start_frame':0,'end_frame':card['end_frame']},
            'limitations':['Text position and lack of inherited entrance/shadow require native render inspection.','Background artwork remains parameterized source media; headline text remains native editable Graphics.']}
    write(args.output/'preparation.json',result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('skills','project','asset','recipe','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--sequence-uid',required=True);p.add_argument('--sequence-name',required=True)
    print(json.dumps(run(p.parse_args()),indent=2))
