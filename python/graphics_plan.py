"""Validate project-owned motion overlays before any native mutation.

Array order is back-to-front. Every asset gets its own native track, so
overlapping graphics never overwrite one another. Creative choices stay with
the owning skill; these checks only bind media, geometry and timing.
"""
import json,subprocess
from fractions import Fraction
from pathlib import Path
from common import inside,require,sha

def validate_graphics(project,spec,total_frames):
 assets=spec.get('graphics',[]);require(isinstance(assets,list),'Graphics must be an explicit array')
 for asset in assets:
  require(isinstance(asset,dict) and set(asset)=={'path','startFrame','frames','sha256'},'Unsupported graphic properties; do not silently discard placement or effects')
  require(type(asset['startFrame'])==int and type(asset['frames'])==int and asset['startFrame']>=0 and asset['frames']>0 and asset['startFrame']+asset['frames']<=total_frames,'Graphic timing must be integer frames inside the picture')
  media=inside(Path(project['root'])/'10_WORK',asset['path']);require(media.is_file(),'Project-owned graphic missing')
  require(sha(media)==asset['sha256'],'Graphic asset changed')
  info=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-show_streams','-of','json',str(media)]))
  streams=info.get('streams',[]);video=[s for s in streams if s.get('codec_type')=='video']
  require(len(video)==1 and not any(s.get('codec_type')=='audio' for s in streams),'Motion assets require one video stream and no audio; route sound through the audio owner')
  v=video[0]
  require(v.get('codec_name')=='prores' and v.get('profile') in ['4444','XQ'] and v.get('pix_fmt','').startswith('yuva444p'),'Motion overlays currently require ProRes 4444/4444 XQ with alpha')
  require(v.get('width')==spec['width'] and v.get('height')==spec['height'],'Graphic must match the timeline canvas; no implicit fit or crop')
  require(v.get('sample_aspect_ratio','1:1') in ['1:1','1/1'] and not any(s.get('rotation',0) for s in v.get('side_data_list',[])) and not float(v.get('tags',{}).get('rotate',0)),'Graphic requires square pixels and no rotation metadata')
  fps=Fraction(spec['fps']['numerator'],spec['fps']['denominator'])
  require(Fraction(v.get('avg_frame_rate','0/1'))==fps and Fraction(v.get('r_frame_rate','0/1'))==fps,'Graphic frame rate must match the timeline; no implicit retiming')
  require(int(v.get('nb_read_frames',-1))>=asset['frames'],'Graphic does not contain enough frames; no freeze or loop fallback')
  subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(media),'-map','0:v:0','-f','null','-'],check=True,capture_output=True)
  require(sha(media)==asset['sha256'],'Graphic changed during validation')
 return assets
