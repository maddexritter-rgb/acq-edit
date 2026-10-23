#!/usr/bin/env python3
"""Internal typed export generator. Accepts data, never executable code."""
import json,sys
from pp_export_clips import inspection_script,export_script

def generate(request):
    kind=request['kind'];args=request['arguments']
    if kind=='inspect':return inspection_script(args['project_path'],args['sequence_id'])
    if kind=='export':
        return export_script(args['baseline'],{'start_ticks':args['start_ticks'],'end_ticks':args['end_ticks']},args['preset_path'],args['output_path'],args['sample_rate'],args['frame_ticks'])
    raise ValueError('Unknown typed export operation')
if __name__=='__main__':print(generate(json.load(sys.stdin)))
