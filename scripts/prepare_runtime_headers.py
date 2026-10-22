"""Extract authenticated header packages locally and verify the pinned closure."""
import hashlib
import json
from pathlib import Path
import zipfile
ROOT=Path(__file__).resolve().parents[1]
PACKAGES=[('runtime','cuda-runtime-headers','nvidia_cuda_runtime_cu12-12.0.107-py3-none-win_amd64.whl'),
          ('support','cuda-nvcc-support-headers','nvidia_cuda_nvcc_cu12-12.0.76-py3-none-win_amd64.whl')]
def prepare(destination):
    lock=json.loads((ROOT/'docs/compatibility/toolchain-lock-v1.json').read_text())
    for folder,tool_id,name in PACKAGES:
        tool=next(t for t in lock['tools'] if t['id']==tool_id)
        package=ROOT/'.cache/reference'/name
        if hashlib.sha256(package.read_bytes()).hexdigest()!=tool['artifact_sha256']:raise ValueError('package mismatch')
        with zipfile.ZipFile(package) as z:
            for member in z.namelist():
                if '/include/' in member and member.endswith('.h'):
                    relative=member.split('/include/',1)[1]
                    if '..' in Path(relative).parts:raise ValueError('header escape')
                    out=destination/folder/relative;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(z.read(member))
        for relative,expected in tool['files'].items():
            file=destination/folder/('crt/'+relative if folder=='support' else relative)
            if hashlib.sha256(file.read_bytes()).hexdigest()!=expected:raise ValueError('header mismatch')
if __name__=='__main__':
    import sys
    prepare(Path(sys.argv[1]))
