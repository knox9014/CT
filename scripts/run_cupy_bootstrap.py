"""Capture/recheck a blocked external CuPy bootstrap; never a support pass."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
import zipfile
import cupy_bootstrap_check as check
from run_validation import source_fingerprint

ROOT=Path(__file__).resolve().parents[1]
PINS=ROOT/'docs/compatibility/cupy-bootstrap-pins.json'
MODES=('cpu','prefix','observe','workload','observe_workload')


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def installed(environment,wheels):
    """Validate wheel identity and all installed payload bytes, not RECORD claims."""
    payload={}; roots=set()
    for pin in json.loads(PINS.read_bytes())['packages']:
        wheel=wheels/pin['filename']
        if digest(wheel)!=pin['sha256']:raise ValueError('wheel identity mismatch')
        with zipfile.ZipFile(wheel) as archive:
            for entry in archive.infolist():
                name=entry.filename
                if entry.is_dir() or name.split('/')[0].endswith('.data') or name.endswith('.dist-info/RECORD'):continue
                path=Path(name)
                if path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name:
                    raise ValueError('wheel payload path')
                target=environment/'Lib/site-packages'/path
                wanted=hashlib.sha256(archive.read(entry)).hexdigest()
                if not target.is_file() or digest(target)!=wanted:raise ValueError('installed payload drift')
                if name in payload:raise ValueError('overlapping wheel payload')
                payload[name]=wanted
                if '.dist-info/' not in name:roots.add(path.parts[0])
    site=environment/'Lib/site-packages'
    for name in roots:
        path=site/name
        for entry in ([path] if path.is_file() else path.rglob('*')):
            if entry.is_file() and '__pycache__' not in entry.parts:
                if entry.relative_to(site).as_posix() not in payload:raise ValueError('extra installed code/data')
    return dict(files=len(payload),sha256=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest())


def judge(folder,record):
    if record['source_fingerprint']!=source_fingerprint(ROOT) or record['pins_sha256']!=digest(PINS):
        raise ValueError('source/pin identity changed')
    if installed(Path(record['environment']),Path(record['wheels']))!=record['installed']:
        raise ValueError('environment identity changed')
    provider=folder/'driver-target/debug/ct_cuda.dll'
    if digest(provider)!=record['driver_sha256']:raise ValueError('provider changed')
    outcomes={}
    if [r['mode'] for r in record['runs']]!=list(MODES):raise ValueError('run scope/order')
    for row in record['runs']:
        mode=row['mode'];bundle=folder/mode
        if row['exit_code']!=0 or type(row['exit_code']) is not int:raise ValueError('child failed')
        if row['observations']!={n:digest(bundle/n) for n in ('stdout.json','stderr.txt')}:
            raise ValueError('observation changed')
        if mode!='cpu' and digest(bundle/'nvcuda.dll')!=record['driver_sha256']:
            raise ValueError('child provider changed')
        outcomes[mode]=json.loads((bundle/'stdout.json').read_bytes())
    if outcomes['cpu'].get('status')!='cpu_pass' or not check.numerical(outcomes['cpu'].get('words')):
        raise ValueError('CPU oracle mismatch')
    if not check.bootstrap_blocker(outcomes['prefix'],outcomes['observe']):
        raise ValueError('bootstrap observation not established')
    expected=dict(status='blocked',stage='input_creation',error_type='CUDARuntimeError',error_code=35)
    if outcomes['workload']!=expected:raise ValueError('workload changed first blocker')
    if not check.bootstrap_blocker(outcomes['workload'],outcomes['observe_workload'],stage='input_creation'):
        raise ValueError('actual workload bootstrap observation not established')
    trace=outcomes['observe']['trace']
    return dict(status='diagnostic_pass',application_supported=False,cuda_output_words=0,cpu_output_words=64,
                observed_failed_call='cuDriverGetVersion',driver_result=801,runtime_result=35,
                trace_rows=len(trace),workload_trace_rows=len(outcomes['observe_workload']['trace']),
                restored=True,sole_cause_proven=False)


def capture(environment,wheels):
    if sys.platform!='win32':raise ValueError('Windows-only diagnostic')
    environment=environment.resolve();wheels=wheels.resolve()
    identity=installed(environment,wheels)
    python=environment/'Scripts/python.exe'
    abi=subprocess.check_output([str(python),'-I','-S','-c','import sys,struct;print(str(sys.version_info[:2])+":"+str(struct.calcsize("P")))'],text=True).strip()
    if abi!='(3, 14):8':raise ValueError('wrong host ABI')
    folder=ROOT/'.cache/cupy-bootstrap-runs'/uuid.uuid4().hex;folder.mkdir(parents=True)
    fingerprint=source_fingerprint(ROOT)
    build=['cargo','build','--locked','-p','ct-cuda','--target-dir',str(folder/'driver-target')]
    with (folder/'build.log').open('wb') as log:
        subprocess.run(build,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180,
                       env=dict(os.environ,CARGO_INCREMENTAL='0'))
    if source_fingerprint(ROOT)!=fingerprint:raise ValueError('source changed during build')
    provider=folder/'driver-target/debug/ct_cuda.dll'
    record=dict(schema_version=1,source_fingerprint=fingerprint,pins_sha256=digest(PINS),
                environment=str(environment),wheels=str(wheels),installed=identity,
                python_sha256=digest(python),driver_sha256=digest(provider),build=build,runs=[])
    for mode in MODES:
        if source_fingerprint(ROOT)!=fingerprint or digest(provider)!=record['driver_sha256']:
            raise ValueError('source/provider changed before child')
        if mode in ('workload','observe_workload') and installed(environment,wheels)!=identity:
            raise ValueError('package changed before workload')
        bundle=folder/mode;bundle.mkdir()
        if mode!='cpu':shutil.copyfile(provider,bundle/'nvcuda.dll')
        env={k:v for k,v in os.environ.items() if not k.upper().startswith(('CUDA','CUPY','CT_','NVRTC','PYTHON'))}
        env.update(CUPY_CACHE_DIR=str(bundle/'cupy-cache'),PYTHONDONTWRITEBYTECODE='1',
                   PYTHONPYCACHEPREFIX=str(bundle/'pycache'),CUDA_PATH=str(bundle))
        command=[str(python),'-I','-S','-B',str(ROOT/'scripts/cupy_bootstrap_worker.py'),
                 '--site',str(environment/'Lib/site-packages'),mode]
        run=subprocess.run(command,cwd=bundle,env=env,capture_output=True,timeout=60)
        (bundle/'stdout.json').write_bytes(run.stdout);(bundle/'stderr.txt').write_bytes(run.stderr)
        record['runs'].append(dict(mode=mode,exit_code=run.returncode,
            observations={n:digest(bundle/n) for n in ('stdout.json','stderr.txt')}))
        # Fail closed: a future provider must not silently advance to GPU launch.
        if mode=='prefix' and (run.returncode!=0 or json.loads(run.stdout)!=dict(status='blocked',stage='device_count',error_type='CUDARuntimeError',error_code=35)):
            raise ValueError('prefix changed; inspect before workload launch')
        if mode=='observe':
            nominal=json.loads((folder/'prefix/stdout.json').read_bytes())
            if run.returncode!=0 or not check.bootstrap_blocker(nominal,json.loads(run.stdout)):
                raise ValueError('observation changed; inspect before workload launch')
        if mode=='workload' and (run.returncode!=0 or json.loads(run.stdout)!=dict(
                status='blocked',stage='input_creation',error_type='CUDARuntimeError',error_code=35)):
            raise ValueError('workload changed; inspect before observed workload')
    if installed(environment,wheels)!=identity:raise ValueError('package changed during execution')
    record['summary']=judge(folder,record)
    (folder/'capture.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    return folder,record['summary']


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--environment',type=Path)
    parser.add_argument('--wheels',type=Path)
    parser.add_argument('--recheck',type=Path)
    args=parser.parse_args()
    if args.recheck:
        folder=args.recheck.resolve()
        if not folder.is_relative_to((ROOT/'.cache/cupy-bootstrap-runs').resolve()):raise ValueError('capture outside local runs')
        record=json.loads((folder/'capture.json').read_bytes())
        result=judge(folder,record)
        if result!=record['summary']:raise ValueError('summary drift')
        if digest(Path(record['environment'])/'Scripts/python.exe')!=record['python_sha256']:raise ValueError('interpreter drift')
        (folder/'recheck.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    else:
        if not args.environment or not args.wheels:parser.error('environment and wheels required')
        folder,result=capture(args.environment,args.wheels)
    print(json.dumps(dict(run=folder.name,**result)))
    return 0


if __name__=='__main__':raise SystemExit(main())
