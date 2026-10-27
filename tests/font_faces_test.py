import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from font_faces import exact_face,resolve_cards
class Faces(unittest.TestCase):
 def test_uses_postscript_metadata_not_guessed_italic_name(self):
  records=[{'postscript':'Fixture-BoldItalic','families':{'Fixture'},'styles':{'Bold It','Bold Italic'}}]
  self.assertEqual(exact_face('Fixture-BoldItalic','Fixture',[{'family':'Fixture','styles':['Bold','Bold It']}],records),'Bold It')
 def test_missing_or_ambiguous_face_stops(self):
  records=[{'postscript':'Fixture-BoldItalic','families':{'Fixture'},'styles':{'Bold It','Bold Italic'}}]
  for available in (['Bold'],['Bold It','Bold Italic']):
   with self.assertRaisesRegex(ValueError,'one exact'):exact_face('Fixture-BoldItalic','Fixture',[{'family':'Fixture','styles':available}],records)
if __name__=='__main__':unittest.main()
