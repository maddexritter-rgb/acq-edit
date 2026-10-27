#!/usr/bin/env python3
"""Replay a frozen editorial selection against verified same-clock native media.
The caller must provide the source-equivalence receipt and a fresh brain preflight.
Does not choose words, cuts, captions or framing.
"""
import argparse,copy,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'.local/skills/edit/scripts'),str(ROOT/'python')]
from compile_assembly import compile_design
import review_xml
from common import sha

def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('frozen-plan','project','source','brain','equivalence'):p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--clip',required=True);a=p.parse_args();read=lambda p:json.loads(Path(p).read_text());frozen=read(a.frozen_plan);project=read(a.project);source=read(a.source);brain=read(a.brain);eq=read(a.equivalence);w=Path(project['root'])/'10_WORK'
 if project['backend']!='premiere' or source['projectId']!=project['id'] or eq['status']!='verified' or source['sha256']!=eq['mediaSha256']:raise ValueError('Verified Premiere same-clock source required')
 if (w/'plan.json').exists():raise FileExistsError('Native plan already exists; preserve it and create a new variant project')
 old_sources={s['id']:s for s in frozen['sources']}
 if len(frozen['cuts'])!=1:raise ValueError('This bounded transport currently supports one frozen contiguous excerpt')
 cut=frozen['cuts'][0]
 if eq['pictureSha256']!=old_sources[cut['sourceId']]['sha256'] or eq['dialogueSha256']!=old_sources[cut['audioSourceId']]['sha256']:raise ValueError('Source equivalence differs from frozen plan')
 old=read(frozen['editorial']['selectionPath']);selection=copy.deepcopy(old);row=selection['clips'][0];row.update(id=a.clip,source_words=str(w/'words.json'),media=source['path'],brain_preflight=brain['receiptPath'])
 if sha(w/'words.json')!=row['source_words_sha256']:raise ValueError('Word data changed')
 def write(name,value):(w/name).write_text(json.dumps(value,indent=2))
 write('selection.json',selection);write('compiled.json',compile_design(w/'selection.json'))
 pairs=read(frozen['editorial']['execution']['decisionsPath']);pairs['selection']=str(w/'selection.json');pairs['outer_edge_evidence']['evidence']=[str(w/'boundaries/index.json')];write('paired-decisions.json',pairs)
 routing={'media':source['path'],'picture':source['path'],'stream':0,'channel':0,'sample_rate':48000,'source_clock_offset_samples':0,'evidence':{'path':str(a.equivalence.resolve()),'sha256':sha(a.equivalence)}};write('routing.json',routing)
 spec={k:copy.deepcopy(frozen[k]) for k in ('schema','title','fps','width','height','sampleRate')};spec.update(projectId=project['id'],backend=project['backend'],clipId=a.clip,sources=[source],brain=brain,cuts=[],captions=[],graphics=[],framing={},audio={})
 spec['editorial']={'selectionPath':str(w/'selection.json'),'sha256':sha(w/'selection.json'),'compiledPath':str(w/'compiled.json'),'compiledSha256':sha(w/'compiled.json'),'reviewed':True,'execution':{'decisionsPath':str(w/'paired-decisions.json'),'decisionsSha256':sha(w/'paired-decisions.json'),'routingPath':str(w/'routing.json'),'routingSha256':sha(w/'routing.json')}}
 write('template.json',spec);write('compile-packet.json',{'template':str(w/'template.json'),'output':str(w/'plan.json')})
 resolved={'schema':'edit.resolved-assembly/v1','compiled_path':str(w/'compiled.json'),'compiled_sha256':sha(w/'compiled.json'),'clips':[{'id':a.clip,'source_frames':[[pairs['first_source_frame'],pairs['last_source_frame']]],'status':'EDITOR_REVIEW','note':'Frozen editorial selection: exact picture and dialogue clocks preserved across native editors.'}]};write('resolved.json',resolved);review_xml.build([],spec['title'],w/'assembly.xml',gap_frames=0,assemblies_path=w/'resolved.json')
 write('assembly-audio.json',{'schema':'edit.assembly-audio-edges/v1','expected_sha256':sha(w/'assembly.expected.json'),'sample_rate':48000,'cuts':[{'assembly_item_index':0,'source_samples':[pairs['first_source_sample'],pairs['last_source_sample']],'reason':'Preserve frozen exact speech boundaries.','evidence':[str(w/'paired-decisions.json'),str(w/'boundaries/index.json')],'status':pairs['outer_edge_evidence']['status']}]})
 print(json.dumps({'projectId':project['id'],'compilePacket':str(w/'compile-packet.json'),'status':'prepared-native-execution-pending'}))
if __name__=='__main__':main()
