"""Resolve a profile's PostScript identity to an exact installed native face."""
from pathlib import Path

def metadata(folders):
    from fontTools.ttLib import TTFont, TTCollection
    rows=[]
    for folder in folders:
        for file in Path(folder).rglob('*'):
            if file.suffix.lower() not in ('.ttf','.otf','.ttc'):continue
            try:
                fonts=TTCollection(file).fonts if file.suffix.lower()=='.ttc' else [TTFont(file)]
                for font in fonts:
                    names={i:{r.toUnicode() for r in font['name'].names if r.nameID==i} for i in (1,2,6,16,17)}
                    for ps in names[6]:rows.append({'postscript':ps,'families':names[1]|names[16],'styles':names[2]|names[17],'file':str(file)})
                    font.close()
            except (OSError,ValueError):continue
    return rows

def exact_face(postscript,family,native_fonts,records):
    faces={x for row in native_fonts if row['family']==family for x in row['styles']}
    matches={style for row in records if row['postscript']==postscript and family in row['families'] for style in row['styles'] if style in faces}
    if len(matches)!=1:raise ValueError('Cannot resolve one exact installed face for '+str(postscript)+' in '+family+'. Inspect the selected profile and installed font metadata; do not guess style names.')
    return next(iter(matches))

def resolve_cards(cards,profile,native_fonts,records):
    import copy
    result=copy.deepcopy(cards)
    for card in result:
        style=card['style'];family=style['font']
        style['fontStyle']=exact_face(style.get('fontPostscript') or profile['body_font_postscript'],family,native_fonts,records)
        if card.get('italic') and not style.get('syntheticQuoteItalic'):
            style['italicStyle']=exact_face(style.get('italicPostscript') or profile['italic_font_postscript'],family,native_fonts,records)
        for run in style.get('emphasis',[]):
            ps=run.get('italicPostscript') if card.get('italic') else run.get('fontPostscript')
            run['fontStyle']=exact_face(ps,family,native_fonts,records)
    return result
