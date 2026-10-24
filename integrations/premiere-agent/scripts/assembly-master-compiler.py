from acq_edit_runtime import skill_scripts
"""Mixed-source review adapter for the existing v2 assembly compiler.
Preserves original dialogue ranges. Picture alone conforms to the master grid.
No selection, listening approval, finishing, source processing or exports.
"""
from pathlib import Path
from fractions import Fraction
import sys,json,hashlib,tempfile,importlib.util,math
from xml.sax.saxutils import escape
from urllib.parse import quote
TPS=254016000000

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canonical():
 sys.dont_write_bytecode=True;s=skill_scripts();sys.path.insert(0,str(s));spec=importlib.util.spec_from_file_location('master_canonical_writer',s/'review_xml.py');w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
 probe=w.probe;audio=w.probe_audio;pc={};ac={};w.probe=lambda p:pc.setdefault(str(p),probe(p)) if str(p) not in pc else pc[str(p)];w.probe_audio=lambda p:ac.setdefault(str(p),audio(p)) if str(p) not in ac else ac[str(p)]
 return w,s

def rate(r):return f'<rate><timebase>{round(r)}</timebase><ntsc>{"TRUE" if r.denominator!=1 else "FALSE"}</ntsc></rate>'
def ticks(sec):
 t=sec*TPS
 if t.denominator!=1 or t<0 or t>9223372036854775807:raise ValueError('Exact safe native time required')
 return str(int(t))
def checked_pin(pin):
 p=Path(pin['path']).resolve(strict=True)
 if sha(p)!=pin['sha256']:raise ValueError('Changed original pin: '+str(p))
 return p

def build(queue_path,xml_path,manifest_path):
 queue_path=Path(queue_path).resolve(strict=True);xml_path=Path(xml_path).resolve();manifest_path=Path(manifest_path).resolve();q=json.loads(queue_path.read_text());assert q['schema']=='edit.assembly-review-master-queue/v1' and q['canvas']==[1920,1080] and Fraction(q['fps'])==30 and q['dialogue_sample_rate']==48000 and q['clip_gap_frames']==30
 assert not xml_path.exists() and not manifest_path.exists();w,s=canonical();artifacts={str(queue_path):sha(queue_path)};medias={};clips=[];ids=set()
 # Original per-clip XML is reproduced with the unchanged canonical writer.
 with tempfile.TemporaryDirectory(prefix='master-original-proof-',dir=xml_path.parent) as tmp:
  for row in q['clips']:
   cid=row['clip_id'];assert cid not in ids;ids.add(cid)
   pins={k:checked_pin(row[k]) for k in ('design','compiled','source_words','original_expected')};expected=pins['original_expected'];old_xml=expected.parent/'assembly.xml';resolved=expected.parent/'resolved.provisional.v1.json'
   assert old_xml.is_file() and resolved.is_file();original=json.loads(expected.read_text());data=json.loads(resolved.read_text());assert data['compiled_path']==str(pins['compiled']);assert data['compiled_sha256']==row['compiled']['sha256'];design=json.loads(pins['design'].read_text());assert len(design['clips'])==1 and design['clips'][0]['id']==cid
   reproduced=Path(tmp)/(cid+'.xml');receipt=w.build([],original['sequence_name'],reproduced,gap_frames=0,assemblies_path=resolved);assert reproduced.read_bytes()==old_xml.read_bytes() and receipt==original
   c=w.designed_clips(resolved);assert len(c)==1 and c[0]['id']==cid and len(c[0]['frames'])==row['selected_spans'];c=c[0];c.update(title=design['clips'][0].get('title') or design['clips'][0].get('display_title') or row['title'],source_date=row['source_date']);width,height,r,d=w.probe(c['media']);ch,sr,depth=w.probe_audio(c['media']);assert sr==48000 and width*9==height*16 and r in (Fraction(24000,1001),Fraction(30),Fraction(30000,1001))
   info=Path(c['media']).stat();medias[str(c['media'])]={'path':str(c['media']),'size':str(info.st_size),'mtime_ns':str(info.st_mtime_ns),'width':width,'height':height,'fps':str(r),'duration':str(d),'channels':ch,'depth':depth}
   for p in [*pins.values(),old_xml,resolved]:artifacts[str(p)]=sha(p)
   clips.append(c)
   if len(clips)%25==0:print('Reproduced original compiler chain',len(clips),flush=True,file=sys.stderr)
 if 'frozen_manifest' in q:
  frozen=Path(q['frozen_manifest']).resolve(strict=True);f=json.loads(frozen.read_text());fids={z['clip_id'] for z in f.get('rows',f.get('clips',[]))} if isinstance(f.get('rows',f.get('clips',[])),list) else set()
  # Actual frozen ledger may use its explicit clip_ids field.
  fids=fids or set(f.get('clip_ids',[]));assert fids==ids,'Master must match the complete frozen batch';artifacts[str(frozen)]=sha(frozen)
 v=[];a=[];markers=[];items=[];index=[];cursor=0;written=set();fileids={p:'master-file-'+str(n) for n,p in enumerate(medias,1)};masterrate=rate(Fraction(30))
 def file_ref(p):
  fid=fileids[p]
  if p in written:return f'<file id="{fid}"/>'
  written.add(p);m=medias[p];r=Fraction(m['fps']);rs=rate(r)
  return f'<file id="{fid}"><name>{escape(Path(p).name)}</name><pathurl>file://localhost{quote(p,safe="/")}</pathurl><duration>{round(float(m["duration"])*r)}</duration>{rs}<media><video><samplecharacteristics><width>{m["width"]}</width><height>{m["height"]}</height>{rs}<anamorphic>FALSE</anamorphic><pixelaspectratio>square</pixelaspectratio><fielddominance>none</fielddominance></samplecharacteristics></video><audio><samplecharacteristics><depth>{m["depth"]}</depth><samplerate>48000</samplerate></samplecharacteristics><channelcount>{m["channels"]}</channelcount></audio></media></file>'
 for n,c in enumerate(clips):
  start=cursor;elapsed=Fraction(0);first=len(items);p=str(c['media']);r=c['fps'];total=sum((Fraction(y-x,1)/r for x,y in c['frames']),Fraction(0));last_end=cursor+math.ceil(total*30)
  for j,(sin,sout) in enumerate(c['frames']):
   dur=Fraction(sout-sin,1)/r;vs=cursor+round(elapsed*30);ve=last_end if j==len(c['frames'])-1 else cursor+round((elapsed+dur)*30);assert ve>vs
   vi=round(Fraction(sin,1)/r*30);vo=vi+ve-vs;ai=Fraction(sin,1)/r;ao=Fraction(sout,1)/r;audio_start=Fraction(cursor,30)+elapsed;audio_end=audio_start+dur;assert int(ai*48000)==ai*48000 and int(ao*48000)==ao*48000
   it={'clip_id':c['id'],'span_index':j,'media_path':p,'video':{'start_ticks':ticks(Fraction(vs,30)),'end_ticks':ticks(Fraction(ve,30)),'source_in_ticks':ticks(Fraction(vi,30)),'source_out_ticks':ticks(Fraction(vo,30))},'audio':{'start_ticks':ticks(audio_start),'end_ticks':ticks(audio_end),'source_in_ticks':ticks(ai),'source_out_ticks':ticks(ao)},'import_audio':{'start_ticks':ticks(Fraction(vs,30)),'end_ticks':ticks(Fraction(ve,30)),'source_in_ticks':ticks(ai),'source_out_ticks':ticks(ao)},'source_frames':[sin,sout],'source_fps':str(r),'scale':192000/medias[p]['width']}
   # Picture conform stays within one master frame of its original AV source offset.
   assert abs((Fraction(vs,30)-Fraction(vi,30))-(audio_start-ai))<=Fraction(1,30);assert Fraction(vo,30)<=Fraction(str(medias[p]['duration']))
   i=len(items)+1;vid=f'master-v-{i}';aid=f'master-a-{i}';links=f'<link><linkclipref>{vid}</linkclipref><mediatype>video</mediatype><trackindex>1</trackindex><clipindex>{i}</clipindex></link><link><linkclipref>{aid}</linkclipref><mediatype>audio</mediatype><trackindex>1</trackindex><clipindex>{i}</clipindex><groupindex>1</groupindex></link>';common=f'<name>{escape(c["id"]+"_"+str(j+1))}</name><enabled>TRUE</enabled>{masterrate}<start>{vs}</start><end>{ve}</end>'
   v.append(f'<clipitem id="{vid}">{common}<duration>{ve-vs}</duration><in>{vi}</in><out>{vo}</out>{file_ref(p)}{links}</clipitem>');a.append(f'<clipitem id="{aid}">{common}<duration>{ve-vs}</duration><in>{vi}</in><out>{vo}</out><pproTicksIn>{ticks(ai)}</pproTicksIn><pproTicksOut>{ticks(ao)}</pproTicksOut>{file_ref(p)}<sourcetrack><mediatype>audio</mediatype><trackindex>1</trackindex></sourcetrack>{links}</clipitem>');items.append(it);elapsed+=dur
  label=f'{c["id"]} | {c["title"]} | {c["source_date"]} | PROVISIONAL';comment='Original source-word assembly. Acoustic seams and full-clip listening remain unqualified; editor review required.';markers.append({'name':label,'comments':comment,'start_ticks':ticks(Fraction(start,30)),'end_ticks':ticks(Fraction(last_end,30))});index.append({'clip_id':c['id'],'title':c['title'],'source_date':c['source_date'],'start_frames':start,'end_frames':last_end,'start_ticks':ticks(Fraction(start,30)),'end_ticks':ticks(Fraction(last_end,30)),'first_item':first,'item_count':len(items)-first,'dialogue_duration_ticks':ticks(total)});cursor=last_end+(30 if n<len(clips)-1 else 0)
 assert len(items)*2<=10000 and len(markers)<=2000
 markerxml=''.join(f'<marker><name>{escape(m["name"])}</name><comment>{escape(m["comments"])}</comment><in>{int(m["start_ticks"])*30//TPS}</in><out>{int(m["end_ticks"])*30//TPS}</out></marker>' for m in markers)
 xml=f'<?xml version="1.0" encoding="UTF-8"?><xmeml version="4"><sequence id="assembly-review-master"><name>{escape(q["sequence_name"])}</name><duration>{cursor}</duration>{masterrate}<media><video><format><samplecharacteristics><width>1920</width><height>1080</height>{masterrate}<pixelaspectratio>square</pixelaspectratio><anamorphic>FALSE</anamorphic><fielddominance>none</fielddominance></samplecharacteristics></format><track>{"".join(v)}</track></video><audio><format><samplecharacteristics><depth>16</depth><samplerate>48000</samplerate></samplecharacteristics></format><track>{"".join(a)}</track></audio></media>{markerxml}</sequence></xmeml>'
 assert len(xml.encode())<=8000000;xml_path.write_text(xml)
 code=[s/name for name in ('review_xml.py','compile_assembly.py','assembly_job.py')]+[Path(__file__).resolve()]
 manifest={'schema':'edit.assembly-review-master-proof/v1','sequence_name':q['sequence_name'],'queue_path':str(queue_path),'queue_sha256':sha(queue_path),'xml_path':str(xml_path),'xml_sha256':sha(xml_path),'canvas':[1920,1080],'frame_ticks':str(TPS//30),'timeline_frames':cursor,'sample_rate':48000,'items':items,'markers':markers,'clip_index':index,'provenance':{'schema':'edit.assembly-master-compiler-provenance/v1','verification':'canonical_per_clip_v2_selections_and_original_XML_reproduced_then_mixed_picture_grid_conformed','artifacts':[{'path':p,'sha256':h} for p,h in sorted(artifacts.items())],'canonical_code':[{'path':str(p),'sha256':sha(p)} for p in code],'media':list(medias.values()),'audio_source_clock':'original_source_frames_and_original_duration_exact_48k_samples','picture_conform':'30fps_nearest_cumulative_boundaries_last_picture_ceil_AV_source_offset_within_one_master_frame','listening':'not_performed','status':'PROVISIONAL_REVIEW_ONLY'}}
 manifest_path.write_text(json.dumps(manifest,indent=2)+'\n');return manifest
if __name__=='__main__':
 m=build(*sys.argv[1:]);print(json.dumps({'clips':len(m['clip_index']),'items':len(m['items']),'xml_bytes':Path(m['xml_path']).stat().st_size,'manifest_path':sys.argv[3]}))
