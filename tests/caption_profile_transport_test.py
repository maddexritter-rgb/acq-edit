import copy
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'distribution/skills/caption-clips/scripts'))
import resolve_cards as owner

class CaptionProfileTransport(unittest.TestCase):
    def test_packaged_profile_keeps_guest_italics_without_mutating_overrides(self):
        profile=json.loads((ROOT/'distribution/skills/caption-clips/profiles/alex.json').read_text())
        overrides={'voices':{'host':{'italic':False},'guest':{'italic':False}}};before=copy.deepcopy(overrides)
        style=owner.style_from_profile(profile,overrides,target_canvas=(1080,1920))
        self.assertEqual(overrides,before);self.assertTrue(style['voices']['guest']['italic']);self.assertFalse(style['voices']['host']['italic'])
        self.assertEqual(style['font_size_px'],80)
        self.assertIn('filmcraft_caption_motion',owner.PROFILE_DESCRIPTIVE)
        self.assertIn('allow_quote_italics',owner.PROFILE_HONOURED)

if __name__=='__main__':unittest.main()
