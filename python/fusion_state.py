"""Parse declarative Fusion exports without executing Lua or trusting graph scripts.

Retain every field except qualified serialization/display/cache fields. Ordinary
table keys are unordered; ordered() tables retain their explicit order. Unknown
syntax fails closed instead of silently omitting a node, expression or input.
"""
import hashlib,json,re
from decimal import Decimal

SCHEMA='acq-edit/fusion-state-v2'
TOKEN=re.compile(r'\s+|--[^\n]*|"(?:\\.|[^"\\])*"|[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?|[A-Za-z_][A-Za-z_0-9]*|[{}\[\]=,();]')
IDENT=re.compile(r'[A-Za-z_][A-Za-z_0-9]*\Z')
NUMBER=re.compile(r'[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?\Z')

class FusionFormatError(RuntimeError):pass

class Parser:
 def __init__(self,text):
  if len(text)>16*1024*1024:raise FusionFormatError('Fusion export exceeds inspection bound')
  self.tokens=[];position=0
  while position<len(text):
   match=TOKEN.match(text,position)
   if not match:raise FusionFormatError(f'Unsupported Fusion export syntax at character {position}')
   token=match.group();position=match.end()
   if not token.isspace() and not token.startswith('--'):self.tokens.append(token)
  self.position=0
 def peek(self,offset=0):
  index=self.position+offset
  return self.tokens[index] if index<len(self.tokens) else None
 def pop(self,expected=None):
  token=self.peek()
  if token is None or expected is not None and token!=expected:raise FusionFormatError('Incomplete or unexpected Fusion export token')
  self.position+=1;return token
 def value(self,depth=0):
  if depth>128:raise FusionFormatError('Fusion export nesting exceeds inspection bound')
  token=self.peek()
  if token is None:raise FusionFormatError('Incomplete Fusion value')
  if token.startswith('"'):
   self.pop()
   try:return {'tag':'string','value':json.loads(token)}
   except ValueError as error:raise FusionFormatError('Unsupported Fusion string escape') from error
  if NUMBER.fullmatch(token):
   self.pop();return {'tag':'number','value':str(Decimal(token).normalize())}
  if token in ['true','false','nil']:
   self.pop();return {'tag':token}
  constructor=None
  if IDENT.fullmatch(token):
   constructor=self.pop()
   if constructor=='ordered':self.pop('(');self.pop(')')
  self.pop('{');entries=[];keys=set();implicit=1
  while self.peek()!='}':
   if self.peek()=='[':
    self.pop();key=self.value(depth+1);self.pop(']');self.pop('=')
    if key['tag'] not in ['string','number','true','false']:raise FusionFormatError('Unsupported Fusion table key')
   elif self.peek() and IDENT.fullmatch(self.peek()) and self.peek(1)=='=':
    key={'tag':'string','value':self.pop()};self.pop('=')
   else:
    key={'tag':'number','value':str(Decimal(implicit).normalize())};implicit+=1
   identity=json.dumps(key,sort_keys=True)
   if identity in keys:raise FusionFormatError('Duplicate Fusion table key')
   keys.add(identity);entries.append([key,self.value(depth+1)])
   if self.peek() in [',',';']:self.pop()
   elif self.peek()!='}':raise FusionFormatError('Missing Fusion table separator')
  self.pop('}')
  return {'tag':'table','constructor':constructor,'entries':entries}
 def parse(self):
  result=self.value()
  if self.peek() is not None or result.get('constructor')!='Composition':raise FusionFormatError('Expected one complete Fusion Composition')
  return result

def field(table,name):
 if not table or table.get('tag')!='table':return None
 return next((value for key,value in table['entries'] if key=={'tag':'string','value':name}),None)

def remove_field(table,name):
 table['entries']=[entry for entry in table['entries'] if entry[0]!={'tag':'string','value':name}]

def empty_table(value):
 return value=={'tag':'table','constructor':None,'entries':[]}

def canonical_fusion(text):
 root=Parser(text).parse()
 counter=field(root,'CurrentID')
 if counter is not None:
  if counter['tag']!='number':raise FusionFormatError('Unexpected Fusion CurrentID type')
  # Resolve reallocates this composition-wide ID counter on reopen. Actual node
  # identities, named graph edges and all tool-local IDs remain represented.
  remove_field(root,'CurrentID')
 prefs=field(root,'Prefs');preferences=field(prefs,'Comp')
 if prefs and prefs.get('constructor') is None and preferences and preferences.get('tag')=='table' and preferences.get('constructor') is None:
  # Resolve drops these exact empty UI preference placeholders after reopening.
  # Nonempty values and other views remain represented, including future fields.
  if empty_table(field(preferences,'SpellCheck')):remove_field(preferences,'SpellCheck')
  views=field(preferences,'Views')
  if views and views.get('tag')=='table' and views.get('constructor') is None and len(views['entries'])==1 and empty_table(field(views,'View1')):remove_field(preferences,'Views')
 tools=field(root,'Tools')
 if tools is None or tools.get('tag')!='table':raise FusionFormatError('Fusion Tools table absent')
 for _,tool in tools['entries']:
  if tool.get('constructor') not in ['Loader','MediaIn']:continue
  custom=field(tool,'CustomData');metadata=field(custom,'MediaProps')
  # The successful media-query marker is transient. Preserve other values and
  # identically named fields outside this exact source-metadata location.
  if custom and custom.get('constructor') is None and metadata and metadata.get('constructor') is None and field(metadata,'__Queried')=={'tag':'true'}:remove_field(metadata,'__Queried')
  tracks=field(metadata,'MEDIA_AUDIO_TRACKS_DESC')
  if tracks and tracks.get('tag')=='table':
   for _,track in tracks['entries']:
    identity=field(track,'MEDIA_AUDIO_TRACK_ID');label=field(track,'MEDIA_AUDIO_TRACK_NAME')
    if identity=={'tag':'string','value':'Timeline Audio'} and label is not None:
     if label['tag']!='string':raise FusionFormatError('Unexpected timeline audio display-label type')
     # Duplication retains the old display label until reopen. Preserve track ID,
     # routing, source names/paths and all audio properties; only this label drifts.
     remove_field(track,'MEDIA_AUDIO_TRACK_NAME')
 def order(value):
  if value['tag']!='table':return
  for _,child in value['entries']:order(child)
  if value['constructor']!='ordered':value['entries'].sort(key=lambda entry:json.dumps(entry[0],sort_keys=True))
 order(root)
 return {'schema':SCHEMA,'composition':root}

def fusion_hash(text):
 return hashlib.sha256(json.dumps(canonical_fusion(text),sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
