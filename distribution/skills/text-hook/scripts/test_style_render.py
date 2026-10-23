import unittest
from pathlib import Path
from PIL import ImageFont
from render_hook import layout
class StyleRenderTests(unittest.TestCase):
 def test_color_case_and_source_preservation(self):
  m={'selected_text':'Useful words','display_lines':['Useful words'],'style_id':'test','existing_hook':'none','safe_rect':[64,64,592,1056],'caption_bottom_px':693,'protected_rects':[], 'style':{'id':'test','status':'approved','approval_evidence':'test fixture','font_path':str(Path.home()/'Library/Fonts/ArialNovaCond-Bold.ttf'),'case':'upper','foreground':'#FFFFFF','background':'#6836B8'}}
  plate,result=layout(m,720,1280)
  self.assertEqual(result['rendered_display_lines'],['USEFUL WORDS'])
  self.assertEqual(m['display_lines'],['Useful words'])
  self.assertIn((104,54,184,255),plate.get_flattened_data());self.assertIn((255,255,255,255),plate.get_flattened_data())
  m['style']['status']='candidate'
  with self.assertRaisesRegex(ValueError,'not user-approved'):layout(m,720,1280)
 def test_semantic_lines_use_distinct_card_treatments(self):
  font=str(Path.home()/'Library/Fonts/Poppins-Bold.ttf')
  m={'selected_text':'Want to sell more? Say less',
     'display_lines':['Want to sell more?','Say less'],
     'style_id':'split','existing_hook':'none','safe_rect':[64,64,592,1056],
     'caption_bottom_px':600,'protected_rects':[],
     'style':{'id':'split','status':'approved','approval_evidence':'fixture',
              'font_path':font,'case':'preserve','foreground':'#111111','background':'#FFFFFF',
              'line_styles':[{'foreground':'#111111','background':'#FFFFFF'},
                             {'foreground':'#FFFFFF','background':'#101010','case':'upper'}]}}
  plate,result=layout(m,720,1280)
  self.assertEqual(result['rendered_display_lines'],['Want to sell more?','SAY LESS'])
  self.assertEqual([x['background'] for x in result['rendered_line_styles']],['#FFFFFF','#101010'])
  self.assertIn((16,16,16,255),plate.get_flattened_data())
  self.assertEqual(m['display_lines'],['Want to sell more?','Say less'])
 def test_wrapped_second_beat_and_font_collection_index(self):
  font='/System/Library/Fonts/Supplemental/Rockwell.ttc'
  m={'selected_text':"Brutal truth: Good ideas won't make you rich",
     'display_lines':['Brutal truth:',"Good ideas won't",'make you rich'],
     'style_id':'serif','existing_hook':'none','safe_rect':[64,64,592,1056],
     'caption_bottom_px':550,'protected_rects':[],
     'style':{'id':'serif','status':'approved','approval_evidence':'fixture',
              'font_path':font,'font_index':2,'case':'preserve',
              'foreground':'#111111','background':'#FFFFFF',
              'line_styles':[{'background':'#FFFFFF'},
                             {'background':'#101010','foreground':'#FFFFFF'},
                             {'background':'#101010','foreground':'#FFFFFF'}]}}
  _,result=layout(m,720,1280)
  self.assertEqual(len(result['rendered_line_styles']),3)
  self.assertTrue(all(x['font_index']==2 for x in result['rendered_line_styles']))
 def test_unified_card_has_one_padded_background(self):
  font=str(Path.home()/'Library/Fonts/Poppins-Bold.ttf')
  m={'selected_text':'This is why plans fail',
     'display_lines':['This is why','plans fail'],
     'style_id':'single','existing_hook':'none','safe_rect':[64,64,592,1056],
     'caption_bottom_px':600,'protected_rects':[],
     'style':{'id':'single','status':'approved','approval_evidence':'fixture',
              'font_path':font,'case':'preserve','foreground':'#FFFFFF','background':'#101010',
              'box_mode':'unified','padding_x_px':42,'padding_y_px':24,'line_gap_px':6}}
  plate,result=layout(m,720,1280)
  self.assertEqual(result['box_mode'],'unified')
  self.assertEqual(plate.getpixel((5,plate.height*3//4)),(16,16,16,255))
  self.assertEqual(m['display_lines'],['This is why','plans fail'])
 def test_split_card_keeps_clearance_and_sizes_each_line(self):
  font=str(Path.home()/'Library/Fonts/Poppins-Bold.ttf')
  m={'selected_text':'Short line Longer answer','display_lines':['Short line','Longer answer'],
     'style_id':'split','existing_hook':'none','safe_rect':[65,269,950,979],
     'caption_bottom_px':1300,'protected_rects':[],
     'caption_strategy':'replace','replacement_hook_top_px':600,
     'style':{'id':'split','status':'approved','approval_evidence':'fixture',
              'font_path':font,'case':'preserve','foreground':'#111111','background':'#FFFFFF',
              'padding_y_px':15,'line_gap_px':-12,
              'line_styles':[{'foreground':'#111111','background':'#FFFFFF',
                              'size_multiplier':1.4,'transition_clearance_px':18},
                             {'foreground':'#FFFFFF','background':'#101010'}]}}
  plate,resolved=layout(m,1080,1920,forced_size=60)
  self.assertEqual([line['font_size_px'] for line in resolved['rendered_line_styles']],[84,60])
  m['style']['line_styles'][0]['transition_clearance_px']=0
  crowded,_=layout(m,1080,1920,forced_size=60)
  self.assertEqual(plate.height-crowded.height,15)
 def test_above_caption_can_lift_to_safe_edge(self):
  font=str(Path.home()/'Library/Fonts/Poppins-Bold.ttf')
  m={'selected_text':'Map the work','display_lines':['Map the work'],
     'style_id':'single','existing_hook':'none','safe_rect':[65,269,950,979],
     'caption_bottom_px':1450,'protected_rects':[[190,80,700,800]],
     'caption_strategy':'preserve',
     'style':{'id':'single','status':'approved','approval_evidence':'fixture',
              'font_path':font,'case':'preserve','foreground':'#111111',
              'background':'#FFFFFF','box_mode':'unified'}}
  _,resolved=layout(m,1080,1920,caption_bounds=[90,1280,900,170],forced_size=80)
  x,y,w,h=resolved['bounds']
  self.assertEqual(resolved['anchor_side'],'above')
  self.assertEqual(y+h,1248)
  self.assertGreaterEqual(1280-(y+h),24)
 def test_split_has_visible_stagger_and_no_open_seam(self):
  font=str(Path.home()/'Library/Fonts/Poppins-Bold.ttf')
  m={'selected_text':'Do the work Count your reps',
     'display_lines':['Do the work','Count your reps'],
     'style_id':'split','existing_hook':'none','safe_rect':[65,269,950,979],
     'caption_bottom_px':1400,'protected_rects':[],
     'caption_strategy':'replace','replacement_hook_top_px':700,
     'style':{'id':'split','status':'approved','approval_evidence':'fixture',
              'font_path':font,'case':'preserve','foreground':'#111111','background':'#FFFFFF',
              'padding_y_px':15,'line_gap_px':-12,'short_line_width_ratio':.90,
              'line_styles':[{'foreground':'#111111','background':'#FFFFFF',
                              'transition_clearance_px':20},
                             {'foreground':'#FFFFFF','background':'#101010'}]}}
  plate,result=layout(m,1080,1920,forced_size=60)
  first,second=result['rendered_line_boxes']
  self.assertNotEqual(first[2],second[2])
  self.assertLessEqual(second[1],first[1]+first[3])
  widths=[]
  for line in result['rendered_line_styles']:
   face=ImageFont.truetype(line['font_path'],line['font_size_px'],index=line['font_index'])
   widths.append(face.getlength(line['text']))
  self.assertGreaterEqual(min(widths)/max(widths),.875)
  self.assertLessEqual(min(widths)/max(widths),.925)
  self.assertEqual(plate.getpixel((plate.width//2,second[1]))[3],255)
if __name__=='__main__':unittest.main()
