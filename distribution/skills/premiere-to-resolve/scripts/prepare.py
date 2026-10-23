#!/usr/bin/env python3
"""Prepare self-contained per-sequence FCP7 XML and a media/verification manifest."""
import argparse, copy, hashlib, json, pathlib, re
import xml.etree.ElementTree as ET
from urllib.parse import unquote, urlparse
from fractions import Fraction

def sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()

def boolean(value, default=True):
    """XML booleans are strict; an unknown flag must not become enabled silently."""
    if value is None:
        return default
    v = value.strip().lower()
    if v not in ('true', 'false', '1', '0'):
        raise ValueError('Invalid enabled/muted flag: ' + repr(value))
    return v in ('true', '1')


def validate_manifest(manifest):
    if manifest.get('schema') != 'premiere-to-resolve/v2':
        raise ValueError('Re-run prepare.py: v2 track-state manifest required')
    if not manifest.get('sequences'):
        raise ValueError('No timelines in XML')
    names = [s['name'] for s in manifest['sequences']]
    if len(set(names)) != len(names):
        raise ValueError('Duplicate timeline names')
    for s in manifest['sequences']:
        if min(s['width'], s['height']) <= 0:
            raise ValueError('Invalid timeline resolution')
        for kind in ('video', 'audio'):
            meta = s.get('track_settings', {}).get(kind)
            if meta is None or len(meta) != len(s['tracks'][kind]):
                raise ValueError('Missing track state: ' + s['name'] + ' ' + kind)
            if any(type(t.get('enabled')) is not bool or
                   (t.get('name') is not None and not isinstance(t['name'], str)) for t in meta):
                raise ValueError('Invalid track state')
            for clips in s['tracks'][kind]:
                if any(type(c.get('enabled')) is not bool for c in clips):
                    raise ValueError('Missing clip enabled state')


def rate(node):
    n=int(node.findtext('rate/timebase'))
    return Fraction(n*1000,1001) if node.findtext('rate/ntsc')=='TRUE' else Fraction(n)

def path_from_url(value):
    u=urlparse(value)
    if u.scheme!='file': raise ValueError('Only local file media URLs are supported: '+value)
    if u.netloc not in ('','localhost'): raise ValueError('Resolve network media path explicitly: '+value)
    return unquote(u.path)

def sequences(root):
    result=[]
    def visit(node,bins):
        if node.tag=='bin': bins=bins+[node.findtext('name')]
        if node.tag=='sequence' and node.find('name') is not None:
            result.append((node,bins));return
        for child in node: visit(child,bins)
    visit(root,[]);return result

def value(node):
    if node is None:return None
    if len(node):return {c.tag:value(c) for c in node}
    try:return float(node.text)
    except (ValueError,TypeError):return node.text

def motion(clip):
    result={}
    for e in clip.findall('filter/effect'):
        eid=e.findtext('effectid')
        result[eid]={p.findtext('parameterid'):{'value':value(p.find('value')),'keys':[(int(k.findtext('when')),value(k.find('value'))) for k in p.findall('keyframe')]} for p in e.findall('parameter')}
    return result

def prepare(xml_path,out,path_map=None):
    out=pathlib.Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    root=ET.parse(xml_path).getroot()
    if root.tag!='xmeml':raise ValueError('Requires Premiere Final Cut Pro XML (xmeml), not FCPXML')
    defs={(x.tag,x.get('id')):x for x in root.iter() if x.get('id') and len(x)}
    seqs=sequences(root);names=[s.findtext('name') for s,_ in seqs]
    if not seqs:raise ValueError('No timelines in XML')
    if len(names)!=len(set(names)):raise ValueError('Duplicate sequence names must be resolved explicitly')
    manifest={'schema':'premiere-to-resolve/v2','source_xml':str(pathlib.Path(xml_path).resolve()),'source_sha256':sha(xml_path),'sequences':[],'media':{},'warnings':[]}
    for number,(original,bins) in enumerate(seqs,1):
        s=copy.deepcopy(original);name=s.findtext('name')
        if s.findall('.//sequence') or s.findall('.//multiclip'):raise ValueError('Nested sequence needs an explicit conversion plan: '+name)
        for parent in list(s.iter()):
            for index,c in enumerate(list(parent)):
                if c.tag=='file' and not len(c):
                    definition=defs.get(('file',c.get('id')))
                    if definition is None:raise ValueError('Unresolved file ID: '+str(c.get('id')))
                    parent.remove(c);parent.insert(index,copy.deepcopy(definition))
        for f in s.findall('.//file'):
            url=f.find('pathurl')
            if url is None:raise ValueError('Offline/generated media requires review: '+str(f.get('id')))
            old=path_from_url(url.text);new=(path_map or {}).get(old,old);p=pathlib.Path(new).resolve()
            if not p.is_file():raise FileNotFoundError(str(p))
            url.text=p.as_uri();manifest['media'][str(p)]={'original_path':old,'bytes':p.stat().st_size}
        sc=s.find('media/video/format/samplecharacteristics')
        if sc is None:raise ValueError('Video timeline settings required')
        entry={'name':name,'bins':bins,'rate':str(rate(s)),'width':int(sc.findtext('width')),'height':int(sc.findtext('height')),'duration':int(s.findtext('duration')),'tracks':{},'track_settings':{},'markers':[{'frame':int(m.findtext('in')),'name':m.findtext('name') or '', 'note':m.findtext('comment') or ''} for m in s.findall('marker')]}
        for kind in ('video','audio'):
            entry['tracks'][kind]=[]
            entry['track_settings'][kind]=[]
            for track in s.findall('media/'+kind+'/track'):
                clips=[]
                entry['track_settings'][kind].append({'enabled':boolean(track.findtext('enabled')), 'name':track.findtext('name') or None})
                if track.findall('transitionitem'):raise ValueError('Transition mapping needs separate validation: '+name)
                for c in track.findall('clipitem'):
                    item={k:int(c.findtext(k)) for k in ('start','end','in','out')}
                    if min(item.values())<0:raise ValueError('Transition/sentinel timing unsupported: '+name)
                    if rate(c)!=rate(s):raise ValueError('Mixed source/timeline rates need separate validation: '+name)
                    if item['end']-item['start']!=item['out']-item['in']:raise ValueError('Retime needs separate validation: '+name)
                    item.update(name=c.findtext('name'),path=path_from_url(c.findtext('file/pathurl')),enabled=boolean(c.findtext('enabled')),effects=motion(c),links=[l.findtext('linkclipref') for l in c.findall('link')],id=c.get('id'))
                    unknown=set(item['effects'])-{'basic','audiolevels','opacity'}
                    if unknown:manifest['warnings'].append({'sequence':name,'clip':item['name'],'unverified_effects':sorted(unknown)})
                    clips.append(item)
                entry['tracks'][kind].append(clips)
        filename=f'{number:02d}_'+re.sub(r'[^\w.-]+','_',name)+'.xml'
        x=ET.Element('xmeml',version='4');x.append(s);ET.ElementTree(x).write(out/filename,encoding='utf-8',xml_declaration=True)
        entry['xml']=filename;entry['sha256']=sha(out/filename);manifest['sequences'].append(entry)
    validate_manifest(manifest)
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    return out/'manifest.json'

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('xml');ap.add_argument('output');ap.add_argument('--path-map',help='JSON exact original path to verified local path mapping')
    a=ap.parse_args();print(prepare(a.xml,a.output,json.loads(pathlib.Path(a.path_map).read_text()) if a.path_map else None))
