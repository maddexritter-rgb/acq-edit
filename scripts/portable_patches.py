"""Explicit reproducible distribution-only fixes. Never mutate canonical source."""
import re
def portable_text(text,relative):
 changes=[]
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
