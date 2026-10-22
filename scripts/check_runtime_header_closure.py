"""Verify actual vendor includes against the two independently pinned packages."""
import argparse
import hashlib
import json
from pathlib import Path
from prepare_runtime_headers import ROOT,PACKAGES
def check(dependencies,headers,lock):
    observed={folder:set() for folder,_,_ in PACKAGES}
    for name in dependencies['Data']['Includes']:
        path=Path(name).resolve()
        for folder,tool_id,_ in PACKAGES:
            base=(headers/folder).resolve()
            if path.is_relative_to(base):
                relative=path.relative_to(base).as_posix()
                if folder=='support':
                    if not relative.startswith('crt/'):return ['unrecognized support include']
                    relative=relative[4:]
                observed[folder].add(relative)
                tool=next(t for t in lock['tools'] if t['id']==tool_id)
                if relative not in tool['files'] or hashlib.sha256(path.read_bytes()).hexdigest()!=tool['files'][relative]:return ['unpinned or changed include']
    for folder,tool_id,_ in PACKAGES:
        tool=next(t for t in lock['tools'] if t['id']==tool_id)
        if observed[folder]!=set(tool['files']):return ['missing pinned include']
    return []
def main():
    p=argparse.ArgumentParser();p.add_argument('dependencies',type=Path);p.add_argument('headers',type=Path);args=p.parse_args()
    try: errors=check(json.loads(args.dependencies.read_text(encoding='utf-8-sig')),args.headers,json.loads((ROOT/'docs/compatibility/toolchain-lock-v1.json').read_text()))
    except (OSError,ValueError,KeyError,StopIteration):errors=['header closure unavailable']
    print('Runtime header closure verified' if not errors else 'Runtime header closure failed')
    return bool(errors)
if __name__=='__main__':raise SystemExit(main())
