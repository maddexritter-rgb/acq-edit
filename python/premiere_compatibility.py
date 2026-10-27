"""Installed versions are observations, never automatic qualification."""
import json
import plistlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def registry():return json.loads((ROOT/'compatibility/premiere.json').read_text())
def default_version():return registry()['defaultQualifiedVersion']
def report(version):
    data=registry();entry=data['versions'].get(version,{'executionAllowed':False,'status':'unknown-version','evidence':None})
    return {'observedVersion':version,**entry,'operations':{op:('existing-support' if entry['executionAllowed'] else 'unverified') for op in data['operations']},'repair':None if entry['executionAllowed'] else 'Use a qualified installed Premiere version or qualify this exact host with native fixtures. Do not edit the profile to bypass host guards.'}
def installed(applications=Path('/Applications')):
    result=[]
    for file in applications.glob('Adobe Premiere Pro*/*.app/Contents/Info.plist'):
        try:
            data=plistlib.loads(file.read_bytes());version=data.get('CFBundleShortVersionString')
            if version:result.append({'application':str(file.parents[1]),**report(version)})
        except (OSError,ValueError,plistlib.InvalidFileException):continue
    return result
if __name__=='__main__':print(json.dumps({'installed':installed()},indent=2))
