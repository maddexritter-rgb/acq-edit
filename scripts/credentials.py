#!/usr/bin/env python3
import getpass,json,os,sys
from pathlib import Path
root=Path(sys.argv[1]);root.mkdir(parents=True,exist_ok=True,mode=0o700)
f=root/'credentials.json';data=json.loads(f.read_text()) if f.exists() else {}
for key in ['ASSEMBLYAI_API_KEY','GEMINI_API_KEY']:
 value=getpass.getpass(key+' (blank keeps current): ')
 if value:data[key]=value
fd=os.open(str(f)+'.new',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as out:json.dump(data,out)
os.replace(str(f)+'.new',f)
print('Keys saved locally with mode 0600. Values were not printed.')
