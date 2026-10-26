"""Explicit reproducible distribution-only fixes. Never mutate canonical source."""
import json,re,hashlib
from pathlib import Path

OVERRIDES = {'footage-fetch/SKILL.md', 'footage-fetch/scripts/gdrive_pull.sh', 'edit/scripts/cut_by_phrase.py', 'live-clip/scripts/live_ingest.py'}

def private_references(text):
 return re.findall(r'__ACQ_(?:LEGACY_HOME|EXTERNAL_VOLUME)__|\$(?:HOME|\{HOME\})/(?:Downloads/cluade|\.(?:agents|claude)/skills)',text)

def portable_distribution(text,relative):
 """Apply reviewed portable replacements after canonical paths are normalized."""
 changes=[]
 if relative=='assembly-design/scripts/seam_windows.py':
  old="'status': 'LOCALLY_INSPECTED'"
  if text.count(old)!=2:raise ValueError('Seam proposal status locations changed')
  text=text.replace(old,"'status': 'PROPOSED'")
  text=text.replace('(MFA end {olo:.3f})','(locator end {olo:.3f})').replace('(MFA start {ihi:.3f})','(locator start {ihi:.3f})')
  changes.append({'patch':'seam-proposals-never-claim-inspection'})
 if relative=='_shared/gemini_audio.py':
  start=text.index("def credential(slot='paid'):")
  end=text.index('\n\ndef encode_mp3(',start)
  text=text[:start]+'''def credential(slot='paid'):
    import os
    names = {'paid': 'GEMINI_API_KEY', 'fallback': 'GEMINI_FALLBACK_API_KEY'}
    if slot not in names:
        raise ValueError('Unknown Gemini credential slot')
    key = os.environ.get(names[slot], '').strip()
    if not key:
        raise ValueError('Configure '+names[slot]+' through toolkit credentials')
    return key
'''+text[end:]
  changes.append({'patch':'toolkit-gemini-listener-credentials'})
 if relative in ('_shared/premiere_bridge.py','edit/scripts/premiere_agent.py'):
  old="'lab_import_prepared_caption_sequence'"
  if text.count(old)!=1:raise ValueError('Graphic asset scope insertion changed')
  text=text.replace(old,old+",'lab_place_graphic_asset'",1)
  changes.append({'patch':'bounded-native-graphic-asset-scope'})
 if relative=='music/scripts/apply_native_music.py':
  snippet=Path(__file__).with_name('portable_snippets')/'music_project_source.py'
  raw=snippet.read_bytes()
  old='    return candidate, evidence\n\n\ndef make_plan('
  if text.count(old)!=1:raise ValueError('Music source binding location changed')
  text=text.replace(old,'    return project_source_candidate(selection, candidate, evidence)\n\n\n'+raw.decode()+'\n\ndef make_plan(',1)
  changes.append({'patch':'verified-project-owned-music-source','snippet':'scripts/portable_snippets/music_project_source.py','snippetSha256':hashlib.sha256(raw).hexdigest()})
 if relative=='edit/scripts/pp_export_clips.py':
  old="    if end<=start or start%frame_ticks or end%frame_ticks:raise ValueError('Frame-aligned nonempty export range required')\n    sample=TICKS//sample_rate\n    if start%sample or end%sample:raise ValueError('Export boundaries must be on supported audio sample grid')\n    for name in ['in_ticks','out_ticks']:\n        if exact(baseline[name])%sample:raise ValueError('Original marks cannot be restored on this sample grid')\n    if not Path(preset).is_absolute() or not Path(output).is_absolute():raise ValueError('Absolute preset/output required')\n    # Compare bounded live state in host before mutation; no stale source plan replay.\n    q=json.dumps\n"
  new="    if end<=start or start%frame_ticks or end%frame_ticks:raise ValueError('Frame-aligned nonempty export range required')\n    sample=TICKS//sample_rate\n    if start%sample or end%sample:raise ValueError('Export boundaries must be on supported audio sample grid')\n    # Premiere's exact unset sentinel is not a negative export boundary.\n    unset='-101606400000000000'\n    whole=baseline['in_ticks']==unset and baseline['out_ticks']==unset\n    if whole and start!=0:raise ValueError('Unset marks support only a complete sequence export')\n    if not whole:\n        for name in ['in_ticks','out_ticks']:\n            if exact(baseline[name])%sample:raise ValueError('Original marks cannot be restored on this sample grid')\n    if not Path(preset).is_absolute() or not Path(output).is_absolute():raise ValueError('Absolute preset/output required')\n    # Compare bounded live state in host before mutation; no stale source plan replay.\n    q=json.dumps\n"
  if text.count(old)!=1:raise ValueError("Native export source changed")
  text=text.replace(old,new,1)
  old=" if(read()!==ticks)set(seconds+1/('''+str(sample_rate)+'''*256));\n if(read()!==ticks)throw Error('RANGE_SET_MISMATCH_'+which);\n}\nvar result=null,problem=null,restoreErrors=[];\ntry{\n setExact('in','''+q(str(start))+''');setExact('out','''+q(str(end))+''');\n result=s.exportAsMediaDirect('''+q(output)+','+q(preset)+''',app.encoder.ENCODE_IN_TO_OUT);\n}catch(e){problem=String(e);}finally{\n try{setExact('in',oldIn);}catch(e){restoreErrors.push(String(e));}\n try{setExact('out',oldOut);}catch(e){restoreErrors.push(String(e));}\n}\nif(restoreErrors.length)throw Error('MARK_RESTORE_FAILED '+restoreErrors.join('; ')+' original='+problem);\nif(JSON.stringify(exportState(s))!==JSON.stringify(expected))throw Error('TIMELINE_CHANGED_AFTER_EXPORT');\nif(problem)throw Error(problem);\n"
  new=" if(read()!==ticks)set(seconds+1/('''+str(sample_rate)+'''*256));\n if(read()!==ticks)throw Error('RANGE_SET_MISMATCH_'+which);\n}\nvar wholeSequence='''+('true' if whole else 'false')+''';\nif(wholeSequence&&String(s.end)!=='''+q(str(end))+''')throw Error('WHOLE_SEQUENCE_DURATION_MISMATCH');\nvar result=null,problem=null,restoreErrors=[];\ntry{\n if(!wholeSequence){setExact('in','''+q(str(start))+''');setExact('out','''+q(str(end))+''');}\n result=s.exportAsMediaDirect('''+q(output)+','+q(preset)+''',wholeSequence?app.encoder.ENCODE_ENTIRE:app.encoder.ENCODE_IN_TO_OUT);\n}catch(e){problem=String(e);}finally{\n if(!wholeSequence){\n  try{setExact('in',oldIn);}catch(e){restoreErrors.push(String(e));}\n  try{setExact('out',oldOut);}catch(e){restoreErrors.push(String(e));}\n }\n}\nif(String(s.getInPointAsTime().ticks)!==oldIn||String(s.getOutPointAsTime().ticks)!==oldOut)restoreErrors.push('MARKS_CHANGED_AFTER_EXPORT');\nif(restoreErrors.length)throw Error('MARK_RESTORE_FAILED '+restoreErrors.join('; ')+' original='+problem);\nif(JSON.stringify(exportState(s))!==JSON.stringify(expected))throw Error('TIMELINE_CHANGED_AFTER_EXPORT');\nif(problem)throw Error(problem);\n"
  if text.count(old)!=1:raise ValueError("Native export source changed")
  text=text.replace(old,new,1)
  changes.append({'patch':'whole-sequence-export-preserves-unset-marks'})
 if relative=='assembly-design/scripts/apply_native_assembly.py':
  old="    spec=importlib.util.spec_from_file_location('selected_lab_assembly_validator',Path(profile.cwd)/'scripts/validate-assembly-import.py')"
  if text.count(old)!=1:raise ValueError('Native assembly validator loading source changed')
  text=text.replace(old,"    sys.path.insert(0,str(Path(profile.cwd)/'scripts'))\n"+old)
  changes.append({'patch':'selected-validator-bootstrap'})
 if relative=='assembly-design/scripts/apply_audio_edges.py':
  old="    if restore!=sid:operate('set_active_sequence',{'sequence_id':restore},'restore')"
  new="    # An initially empty project has no sequence to restore. Keep the newly\n    # constructed assembly active rather than submitting an invalid null ID.\n    if restore is not None and restore!=sid:operate('set_active_sequence',{'sequence_id':restore},'restore')"
  if text.count(old)!=1:raise ValueError('Audio selection restoration source changed')
  text=text.replace(old,new).replace("final['active_sequence_id']!=restore", "final['active_sequence_id']!=(restore if restore is not None else sid)")
  changes.append({'patch':'empty-selection-audio-finalization'})
 if relative=='music/scripts/pick_music.py':
  text=re.sub(r'DEFAULT_REVIEW = Path\([^\n]+\)\.expanduser\(\)', 'DEFAULT_REVIEW = ROOT / "music_review_decisions.json"', text)
  text=text.replace('  path=Path(track.get("path",key)); low=path.name.lower()', '  path=Path(track.get("path",key))\n  path=path if path.is_absolute() else ROOT/path\n  if not path.resolve().is_relative_to(ROOT.resolve()):raise ValueError("Music must belong to the installed asset bundle")\n  low=path.name.lower()')
  changes.append({'patch':'bundle-relative-music-catalog'})
 if relative=='live-clip/scripts/live_common.py':
  text=text.replace('import json, re, subprocess','import hashlib, json, re, subprocess')
  old='''    chunks = list_chunks(work)
    if (work / "chunks" / "INGEST_DONE").exists():
        return chunks
    return chunks[:-1]  # last one may still be written'''
  replacement='''    chunks = list_chunks(work)
    if [p.name for p in chunks] != [f'seg_{i:05d}.ts' for i in range(len(chunks))]:
        raise RuntimeError('Live chunk sequence is not contiguous; inspect the retained capture')
    marker = work / 'chunks' / 'INGEST_DONE'
    if marker.exists():
        receipt = json.loads(marker.read_text())
        state_bytes = (work / 'ingest-state.json').read_bytes()
        state = json.loads(state_bytes)
        if (receipt.get('schema') != 'acq-edit/live-completion-v1'
                or state.get('schema') != 'acq-edit/live-capture-v1'
                or state.get('status') != 'succeeded'
                or receipt.get('captureId') != state.get('id')
                or receipt.get('stateSha256') != hashlib.sha256(state_bytes).hexdigest()
                or any(p.is_symlink() or not p.is_file() or p.stat().st_size == 0 for p in chunks)
                or receipt.get('chunks') != [{'file': p.name, 'bytes': p.stat().st_size} for p in chunks]):
            raise RuntimeError('Live completion receipt differs; preserve the capture for inspection')
        return chunks
    return chunks[:-1]  # last one may still be written or truncated by a failed capture'''
  if text.count(old)!=1:raise ValueError('Live closed-chunk source changed')
  text=text.replace(old,replacement)
  changes.append({'patch':'live-capture-completion-receipt'})
 if relative=='edit/scripts/assembled_gate.py':
  old='''    print(f"\\n{'🛑 BLOCK — fix the openers/endings before any render or import'
            if bad else '✅ all assembled texts open and end clean'}")'''
  replacement='''    message = ('🛑 BLOCK — fix the openers/endings before any render or import'
               if bad else '✅ all assembled texts open and end clean')
    print('\\n' + message)'''
  if text.count(old)!=1:raise ValueError('Assembled-gate summary source changed')
  text=text.replace(old,replacement)
  changes.append({'patch':'python311-assembled-gate-summary'})
 if relative=='text-hook/scripts/render_hook.py':
  # Expose the owner's actual drawing coordinates; adapters must not reimplement
  # its font fitting, line spacing, padding or placement decisions.
  old="            first = line_specs[0] if line_specs else {'foreground':'#000000','background':'#FFFFFF'}"
  addition='''            native_text = []
            for line, tx, ty, font, foreground in rows:
                native_text.append({'text': line, 'origin_px': [tx, ty],
                                    'baseline_px': [tx, ty+font.getmetrics()[0]],
                                    'ink_bounds': list(font.getbbox(line)),
                                    'font_family': font.getname()[0], 'font_style': font.getname()[1]})
            native_boxes = ([{'bounds': [0, 0, bw, bh], 'color': style['background'], 'radius_px': radius}]
                            if box_mode == 'unified' else
                            [{'bounds': box, 'color': (line_specs[index] if line_specs else {'background': '#FFFFFF'})['background'],
                              'radius_px': radius} for index, box in enumerate(line_box_bounds)])
'''
  if text.count(old)!=1:raise ValueError('Hook drawing source changed')
  text=text.replace(old,addition+old)
  old="                           'rendered_line_styles': resolved_lines,"
  if text.count(old)!=1:raise ValueError('Hook layout result changed')
  text=text.replace(old,old+"\n                           'native_text': native_text, 'native_boxes': native_boxes,")
  old="                                   'effective_safe_rect':geometry['effective_safe_rect'],'plate':filename})"
  if text.count(old)!=1:raise ValueError('Hook interval result changed')
  text=text.replace(old,"                                   'effective_safe_rect':geometry['effective_safe_rect'],\n                                   'native_text':geometry['native_text'], 'native_boxes':geometry['native_boxes'],\n                                   'rendered_line_styles':geometry['rendered_line_styles'], 'plate':filename})")
  old="               'native_verified': False, 'user_approved': False}"
  if text.count(old)!=1:raise ValueError('Hook receipt source changed')
  text=text.replace(old,"               'native_explicit_intervals': m.get('placement_intervals') is not None,\n"+old)
  changes.append({'patch':'native-hook-drawing-coordinates'})
 if relative in OVERRIDES:
  replacement=Path(__file__).with_name('portable_overrides')/relative
  raw=replacement.read_bytes();text=raw.decode()
  changes.append({'patch':'portable-execution-owner','replacement':'scripts/portable_overrides/'+relative,'replacementSha256':hashlib.sha256(raw).hexdigest()})
 if relative=='edit/assets/README.md':
  text=text.replace('__ACQ_LEGACY_HOME__/Downloads/editing assests for claude music anamtions presets everything ', '__ACQ_ASSETS__')
  text='> Optional asset catalog. Paths resolve under the configured asset-library root. These licensed assets are not bundled or guaranteed to be installed; inspect the configured profile and verify each selected asset before use.\n\n'+text
  changes.append({'patch':'configured-asset-catalog'})
 if relative=='edit/references/hard_won_lessons.md':
  text=text.replace('/System__ACQ_EXTERNAL_VOLUME__/Data', '"<project-root>"')
  changes.append({'patch':'project-storage-space-check'})
 if relative=='edit/RUNBOOK.md':
  start=text.index('## STEP 0 — Reuse the weekly project')
  end=text.index('- Verify source is horizontal',start)
  text=text[:start]+'''## STEP 0 — Reuse the toolkit project, ingest and preflight
Read `project.json` for the exact project root and fixed backend. For new work use
`node "__ACQ_TOOLKIT__/dist/cli.js" project "<title>"`; for existing work use
`projects` and `open PROJECT_ID`. Never create a competing weekly production project.
→ Use skill: footage-fetch for verified intake into this project's `00_SOURCE`.
Keep intermediates under `10_WORK` and immutable published exports under `20_DELIVER`.
Use the toolkit's clip registration and selected native adapter; the remaining
Premiere-specific mechanics below apply only to a scoped Premiere project.
→ Follow [native execution routing](__ACQ_TOOLKIT__/docs/AGENT_WORKFLOW.md#native-execution-routing).
\n'''+text[end:]
  changes.append({'patch':'toolkit-project-scaffolding'})
 if relative=='assembly-design/references/editorial-precedents.md':
  start=text.index('For workshop/event batches');end=text.index('Generalize the decisions:',start)
  text=text[:start]+'''For workshop/event batches and construction retries, inspect the exact
user-supplied calibration artifact when provided, including its selected-source
dialogue, plan and approval provenance. If those artifacts are absent, report that
evidence as unavailable; a private historical path is not a portable dependency.
\n'''+text[end:]
  start=text.index('Start with the handoff index:');end=text.index('Load a case only',start)
  text=text[:start]+'''Start with the project-owned evidence returned by restricted brain retrieval.
Use the returned confidence labels and source links; do not assume a private local
research index exists or that its earlier case counts describe current coverage.
\n'''+text[end:]
  text='> Retrieve current guidance through [the editorial brain contract](__ACQ_TOOLKIT__/docs/EDITORIAL_BRAIN.md). Private historical studies are not bundled. Use only returned evidence or explicitly supplied project-owned benchmarks; do not search a former workstation. Missing cited evidence is unavailable, not approved.\n\n'+text
  changes.append({'patch':'portable-precedent-evidence'})
 if relative=='assembly-design/references/CLIP_CUTTING_PLAYBOOK.md':
  old='Assemble via ffmpeg trim+concat. (Tooling: `cut_by_phrase.py` single-span / `recut.py` multi-span.)'
  if old not in text:raise ValueError('Phrase-locator playbook source changed')
  text=text.replace(old,'Use `edit/scripts/cut_by_phrase.py --transcript <words.json> --near <source-seconds> --hook "<exact words>" --payoff "<exact words>"` only to locate source words. It reports every matching candidate without choosing a cut or padding speech. Assembly Design owns source-word selection and compilation; construct and export through the selected toolkit native adapter.')
  changes.append({'patch':'phrase-locator-native-handoff'})
 if relative in {'edit/config/example_config.json','ad-edit/references/example_config.json','ad-edit/references/example_config_heavy_broll.json'}:
  data=json.loads(text)
  data['_portable_usage']='Example only. Resolve paths for the current project and configured licensed assets. Native composition/export uses the selected toolkit backend; legacy renderer examples do not authorize a different engine.'
  if relative.startswith('edit/'):
   data['project_root']='<project-root>';data['music_folder']='__ACQ_ASSETS__/music'
  else:
   data['font']='__ACQ_ASSETS__/fonts/<licensed-font>.ttf'
   data['source']='00_SOURCE/<registered-source>.mp4';data['transcript']='10_WORK/<clip-transcript>.json'
   data['out']='10_WORK/<preview>.mp4'
   if 'music' in data:data['music']='__ACQ_ASSETS__/music/<selected-track>.wav'
   for i,overlay in enumerate(data.get('overlays',[])):
    if '__ACQ_LEGACY_HOME__' in overlay['src']:overlay['src']=f'00_SOURCE/<registered-cutaway-{i+1}>.mp4'
    elif '__ACQ_SKILLS__' in overlay['src']:overlay['src']=f'10_WORK/graphics/<rendered-sequence-{i+1}>'
  text=json.dumps(data,indent=2)+'\n';changes.append({'patch':'explicit-project-and-licensed-asset-examples'})
 if relative=='ad-edit/scripts/make_graphics.py':
  old='FONT = sys.argv[2] if len(sys.argv) > 2 else \\\n    "__ACQ_LEGACY_HOME__/Library/Fonts/ProximaNova-Extrabold.ttf"'
  replacement='''if len(sys.argv) != 3:
    raise SystemExit("Usage: make_graphics.py OUTDIR LICENSED_FONT_FILE")
FONT = str(Path(sys.argv[2]).expanduser().resolve())
if not Path(FONT).is_file():
    raise SystemExit("Configured font file is missing; provide a licensed font explicitly")
ImageFont.truetype(FONT, 12)  # validate before creating any output
'''.rstrip()
  if old not in text:raise ValueError('Graphics font-default source changed')
  text=text.replace(old,replacement).replace('<outdir> [font.ttf]','<outdir> <licensed-font.ttf>');changes.append({'patch':'explicit-graphics-font'})
 if relative=='ad-edit/scripts/render_ad.py':
  old='FONT = CFG.get("font", "__ACQ_LEGACY_HOME__/Library/Fonts/ProximaNova-Extrabold.ttf")'
  replacement='''FONT = CFG.get("font")
if not isinstance(FONT, str) or not Path(FONT).expanduser().is_file():
    raise SystemExit("Config font must name an existing licensed font file")
FONT = str(Path(FONT).expanduser().resolve())
ImageFont.truetype(FONT, 12)  # validate before rendering or creating output'''
  if old not in text:raise ValueError('Ad renderer font-default source changed')
  text=text.replace(old,replacement);changes.append({'patch':'explicit-render-font'})
 return text,changes
DESCRIPTIONS={
 'footage-fetch':'Import local footage, YouTube videos or authenticated Google Drive files and folders into verified project-owned sources. Use for footage intake, download queues, checksum verification and interrupted-transfer recovery.',
 'render':'Render or revise clips through the selected native editor, preserving project recipes, reusable stage assets and immutable published versions. Use for rendering, exports, rerenders and dependent-layer updates after an approved edit.',
 'transcript-edit':'Prepare word-level revisions from an editable transcript and exact source words. Use for removing passages or filler words and applying transcript edits, with reviewed speech boundaries and dependent caption/framing updates.',
 'vertical-livestream-card':'Design a floating-card presentation for footage already shot vertically, with a blurred duplicate background, elevation shadow and headroom-aware crop. Use for native vertical livestream or phone footage; horizontal reframing belongs to horizontal-to-vertical.',
 'promo':'Create branded motion graphics and promo assets with Remotion, including animated explainers, product demos, chapter cards and growth curves. Use for a promo video, SaaS demo, presentation animation or an archive-based origin story.',
 'saas-animation-video':'Create a short vertical SaaS animation using Remotion text, glass-reveal and dashboard scenes. Use for a product demo, animated app introduction or a reusable SaaS motion asset.'
}
def portable_text(text,relative):
 changes=[]
 owner=relative.split('/')[0]
 if relative==owner+'/SKILL.md' and owner in DESCRIPTIONS:
  text,count=re.subn(r'(?ms)^description:.*?(?=^[A-Za-z_][A-Za-z0-9_-]*:|^---\s*$)',lambda _: 'description: '+json.dumps(DESCRIPTIONS[owner],ensure_ascii=False)+'\n',text,count=1)
  if not count:raise ValueError('Missing description in portable skill '+relative)
  changes.append({'patch':'portable-skill-description','owner':owner})
 patterns=[
  (r'Path\.home\(\)\s*/\s*([\"\'])\.(?:agents|claude)/skills([^\"\']*)\1',lambda m:'Path("__ACQ_SKILLS__'+m.group(2)+'")','joined-skill-root'),
  (r'Path\.home\(\)\s*/\s*[\"\']\.(?:agents|claude)[\"\']\s*/\s*[\"\']skills[\"\']','Path("__ACQ_SKILLS__")','split-skill-root'),
  (r'Path\.home\(\)\s*/\s*([\"\'])Downloads/cluade([^\"\']*)\1',lambda m:'Path("__ACQ_ASSETS__'+m.group(2)+'")','joined-assets-root'),
  (r'Path\.home\(\)\s*/\s*[\"\']Downloads[\"\']\s*/\s*[\"\']cluade[\"\']','Path("__ACQ_ASSETS__")','split-assets-root'),
 ]
 for pattern,replacement,label in patterns:
  text,count=re.subn(pattern,replacement,text)
  if count:changes.append({'patch':label,'count':count})
 if relative=='find-precedents/scripts/scoped_policy.py':
  text=text.replace("'/Volumes/BIG DAWG 4/ACQ_EDIT_PROJECTS'","str(Path.home() / 'Movies' / 'ACQ Edit')");changes.append({'patch':'configured-storage-default'})
 if relative=='_shared/profile.py':
  text=text.replace('Path.home() / ".claude" / "profile_log.jsonl"','Path.home() / ".config" / "acq-edit" / "profile.jsonl"');changes.append({'patch':'toolkit-profiler-location'})
 return text,changes
