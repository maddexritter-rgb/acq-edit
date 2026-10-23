import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from filmcraft_caption_contract import prepare_cards,verify_native_layers,centered_text_position,centered_caption_opacity,centered_caption_position
from caption_profiles import preserve_first_person,capitalize_letter_names,load_profile
from filmcraft_caption_contract import profile_caption_motion
P={'allow_quote_italics':True,'caption_hold_through_seconds':.75,'caption_trailing_hold_seconds':.35}
def card(a,b,text='hello, world.',quote=False):return {'start_frame':a,'end_frame':b,'speech_end':b/24,'text':text,'quote':quote}
class ContractTests(unittest.TestCase):
 def test_profile_owned_motion_is_explicit(self):
  f=10594584000
  for profile in ['leila','sharran']:
   pos,opacity=profile_caption_motion(load_profile(profile),f,24)
   self.assertEqual(pos,{'value':{'Vec2':{'x':540.,'y':960.}}})
   self.assertEqual(opacity,{'value':{'Float':100.}})
  pos,_=profile_caption_motion(load_profile('alex'),f,24)
  self.assertIn('keyframes',pos)
  with self.assertRaisesRegex(ValueError,'Explicit supported'):
   profile_caption_motion({},f,24)

 def test_static_profile_plan_rejects_animated_native_layers(self):
  c=card(0,20,'hello world');c['animation_preset']='none';c['italic']=False
  item={'start':0,'duration':20,'effects':[
   {'effect':'graphic_text','params':{'text':{'value':{'Text':'hello world'}},'faux_italic':{'value':{'Bool':False}},'font_style':{'value':{'Text':'Regular'}}}},
   {'effect':'motion','params':{'position':{'value':{'Vec2':{'x':540,'y':960}},'keyframes':[{'time':0}]}}},
   {'effect':'opacity','params':{'opacity':{'value':{'Float':100.}}}}]}
  layers=[{'items':[item]} for _ in range(3)]
  with self.assertRaisesRegex(ValueError,'Profile forbids'):
   verify_native_layers(layers,[c],1)
  item['effects'][1]['params']['position'].pop('keyframes')
  self.assertEqual(verify_native_layers(layers,[c],1)['cards'],1)
 def test_letter_names_do_not_corrupt_contraction_suffixes(self):
  for text in ["unless it's that's what's let's account's", "unless it’s that’s what’s let’s account’s"]:
   self.assertEqual(capitalize_letter_names(text),text)
   self.assertEqual(prepare_cards([card(0,20,text)],P,24,48)[0]['text'],text)
  self.assertEqual(capitalize_letter_names("cross t's and dot i's"),"cross T's and dot i's")
  self.assertEqual(capitalize_letter_names('cross t’s'), 'cross T’s')
 def test_native_handoff_refuses_mangled_suffixes(self):
  for text in ["unless iT's", "thaT's", "whaT’s", "leT's", "accounT's"]:
   with self.assertRaisesRegex(ValueError,'Mixed-case contraction'):
    prepare_cards([card(0,20,text)],P,24,48)
 def test_live_guest_italic_without_quote_marks(self):
  c=card(0,20,'i have a business',False);c['role']='guest'
  x=prepare_cards([c],dict(P,guest_turn_italics=True),24,48)[0]
  self.assertEqual(x['text'],'I have a business');self.assertTrue(x['italic']);self.assertFalse(x['quote'])
  c['quote']=True
  self.assertEqual(prepare_cards([c],dict(P,guest_turn_italics=True),24,48)[0]['text'],'“I have a business”')
 def test_first_person_after_lowercase_pass(self):
  self.assertEqual(preserve_first_person("i i'm i've i'll i'd i’m inside mini"),"I I'm I've I'll I'd I’m inside mini")
 def test_center_uses_native_ink_not_baseline(self):
  self.assertEqual(centered_text_position([-200,-54,200,14]),[540.,980.])
 def test_measured_settle_matches_approved_preview(self):
  f=10594584000;p=centered_caption_position(f,24,source_in=5*f)
  self.assertAlmostEqual(p['value']['Vec2']['y'],953.884)
  self.assertEqual(p['keyframes'][1]['time'],6*f)
  self.assertAlmostEqual(p['keyframes'][1]['value']['Vec2']['y'],956.597)
  self.assertEqual(p['keyframes'][-1]['value']['Vec2']['y'],960.)
  self.assertEqual(p['keyframes'][-1]['time'],16*f)
 def test_continuation_does_not_replay_entrance(self):
  f=10594584000;p=centered_caption_position(f,24,source_in=7*f,elapsed_frames=2)
  self.assertAlmostEqual(p['value']['Vec2']['y'],957.562)
  self.assertEqual(p['keyframes'][-1]['time'],16*f)
  self.assertNotIn('keyframes',centered_caption_position(f,24,elapsed_frames=11))
  self.assertNotIn('keyframes',centered_caption_opacity(f,elapsed_frames=2))
 def test_short_cards_preserve_motion_speed(self):
  f=10594584000
  for n in [1,2,3,4]:
   self.assertEqual(centered_caption_position(f,n),centered_caption_position(f,24))
   self.assertEqual(centered_caption_opacity(f,card_frames=n),centered_caption_opacity(f,card_frames=24))
 def test_fps_changes_do_not_change_real_time_speed(self):
  f24=10594584000;f30=8475667200
  self.assertEqual(centered_caption_position(f24,24),centered_caption_position(f30,30))
  self.assertEqual(centered_caption_opacity(f24),centered_caption_opacity(f30))
  # A continuation between reference samples interpolates the current value.
  p=centered_caption_position(f30,30,elapsed_frames=1)
  self.assertAlmostEqual(p['value']['Vec2']['y'],953.884+.8*(956.597-953.884))
 def test_resolution_scales_travel_only(self):
  f=10594584000;p=centered_caption_position(f,24,center=(1080,1920),canvas_height=3840)
  self.assertAlmostEqual(p['value']['Vec2']['y'],1920-12.232)
 def test_animation_rejects_invalid_clocks(self):
  for args in [(0,10),(100,0)]:
   with self.assertRaises(ValueError):centered_caption_position(*args)
 def test_short_gap_closes_without_early_incoming(self):
  x=prepare_cards([card(0,20),card(22,40)],P,24,48)
  self.assertEqual(x[0]['end_frame'],22);self.assertEqual(x[1]['start_frame'],22)
 def test_long_pause_stays_clear(self):
  x=prepare_cards([card(0,20),card(60,70)],P,24,80);self.assertLess(x[0]['end_frame'],60)
 def test_completed_caption_stops_at_layout_cut(self):
  x=prepare_cards([card(0,20),card(30,40)],P,24,48,picture_cuts=[24]);self.assertEqual(x[0]['end_frame'],24)
 def test_omission_not_filled(self):
  x=prepare_cards([card(0,20),card(30,40)],P,24,48,omissions=[{'start':1.0,'end':1.1}]);self.assertEqual(x[0]['end_frame'],24)
 def test_quantity_and_qualification_are_not_filler(self):
  for word in ['$40','40','million','not','unless','probably']:
   with self.subTest(word=word),self.assertRaises(ValueError):
    prepare_cards([card(0,20)],P,24,48,omissions=[{'word':word,'start':1.,'end':1.1}])
 def test_actual_filler_is_allowed(self):
  x=prepare_cards([card(0,20)],P,24,48,omissions=[{'word':'um','start':1.,'end':1.1}]);self.assertTrue(x)
 def test_explicit_replacement_is_distinct_from_filler(self):
  x=prepare_cards([card(0,20)],P,24,48,omissions=[{'word':'$40','start':1.,'end':1.1,'purpose':'replacement','replacement_text':'[amount]'}]);self.assertTrue(x)
 def test_quote_and_lexical_punctuation(self):
  x=prepare_cards([card(0,20,"I don't owe $1,000.",True),card(22,40)],P,24,48)
  self.assertEqual(x[0]['text'],'“I don\'t owe $1,000”');self.assertTrue(x[0]['italic']);self.assertFalse(x[1]['italic']);self.assertEqual(x[1]['text'],'hello world')
 def test_quote_classification_required(self):
  c=card(0,20);del c['quote']
  with self.assertRaises(ValueError):prepare_cards([c],P,24,48)
 def test_native_style_or_clock_loss_fails(self):
  import copy
  cards=prepare_cards([card(0,20,'hello',True)],P,24,48)
  p={'text':{'value':{'Text':cards[0]['text']}},'faux_italic':{'value':{'Bool':True}},'font_style':{'value':{'Text':'Regular'}}}
  layer={'items':[{'start':0,'duration':cards[0]['end_frame'],'effects':[{'effect':'graphic_text','params':p}]}]}
  layers=[copy.deepcopy(layer) for _ in range(3)]
  verify_native_layers(layers,cards,1)
  layers[1]['items'][0]['effects'][0]['params']['faux_italic']['value']['Bool']=False
  with self.assertRaises(ValueError):verify_native_layers(layers,cards,1)
  layers=[copy.deepcopy(layer) for _ in range(3)];layers[0]['items'][0]['duration']-=1
  with self.assertRaises(ValueError):verify_native_layers(layers,cards,1)
if __name__=='__main__':unittest.main()
