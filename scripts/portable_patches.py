"""Explicit reproducible distribution-only fixes. Never mutate canonical source."""
import json,re
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
