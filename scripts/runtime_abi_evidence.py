"""Capture real ABI probe output and bind it to its executable and source."""
import hashlib
import json
from pathlib import Path
import subprocess
from run_validation import source_fingerprint
ROOT=Path(__file__).resolve().parents[1]
EXPECTED=b'ABI 14 4 4 8 8\n0 1 2 3 4\n0 1 2 3 21 35 49 100 101 709 801 999\n'
def file(root,name):
    p=(root/name).resolve()
    if not p.is_relative_to(root/'.cache/p09a-build'):raise ValueError('ABI artifact escape')
    return p
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def audit(path,root=ROOT):
    try:
        value=json.loads(Path(path).read_text())
        if set(value)!={'case_id','source_tree','probes'} or value['case_id']!='arc.runtime_abi' or value['source_tree']!=source_fingerprint(root):return ['ABI identity mismatch']
        if set(value['probes'])!={'runtime_reference_abi','runtime_declared_abi'}:return ['missing ABI probes']
        for name,item in value['probes'].items():
            if set(item)!={'binary','binary_sha256','output','output_sha256'}:return ['invalid ABI observation']
            binary=file(root,item['binary']);output=file(root,item['output'])
            if binary.name!=name+'.exe' or digest(binary)!=item['binary_sha256'] or digest(output)!=item['output_sha256']:return ['ABI artifact changed']
            if output.read_bytes().replace(b'\r\n',b'\n')!=EXPECTED:return ['ABI mismatch']
        return []
    except (OSError,ValueError,TypeError,KeyError):return ['ABI evidence unavailable']
def capture(folder):
    value=dict(case_id='arc.runtime_abi',source_tree=source_fingerprint(ROOT),probes={})
    for name in ('runtime_reference_abi','runtime_declared_abi'):
        binary=folder/(name+'.exe');output=folder/(name+'.stdout')
        run=subprocess.run([str(binary)],capture_output=True,timeout=30)
        if run.returncode!=0 or run.stdout.replace(b'\r\n',b'\n')!=EXPECTED:raise ValueError('ABI probe failed')
        output.write_bytes(run.stdout)
        value['probes'][name]=dict(binary=binary.relative_to(ROOT).as_posix(),binary_sha256=digest(binary),output=output.relative_to(ROOT).as_posix(),output_sha256=digest(output))
    path=folder/'abi-manifest.json';path.write_text(json.dumps(value,indent=2)+'\n')
    if audit(path):raise ValueError('ABI audit failed')
    (ROOT/'.cache/p09a-abi-latest.json').write_text(json.dumps({'manifest':path.relative_to(ROOT).as_posix()}))
if __name__=='__main__':
    import sys
    capture(Path(sys.argv[1]).resolve())
