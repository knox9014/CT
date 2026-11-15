"""Original pinned NVIDIA Runtime sample; diagnostic adjusted build, no release."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import uuid

from run_relaxed_nvcc import (command, verify_files, compiler_args, host_environment,
                              digest, payload, ptx_tokens, audit_probe,
                              source_fingerprint, prepare_bundle)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from upstream_vectoradd_oracle import validate_buffers, validate_trace, validate_inputs
from m3c_gpu_validation import Device

COMMIT = '2b689228b746248b7bb7d2778d5ea0701669f7d3'
PINS = {'vectorAdd.cu':'9a156c7c4f1ab0759d859af95c8dab55f2280d867edca7daee4546d63effb583',
        'Common/helper_cuda.h':'7c514aba698325bf53a26bf8e711eeb6efd354fac45ea011486c3d907eec62c7',
        'Common/helper_string.h':'616ac8b2588a6e73aed207f85faf0da5e617404390df1790f6637b1042dbcc94'}
INPUTS = ['scripts/run_upstream_vectoradd.py','tests/upstream_vectoradd_trace.c',
          'tests/upstream_vectoradd_oracle.py','tests/test_upstream_vectoradd.py',
          'scripts/run_relaxed_nvcc.py','scripts/prepare_nvcc_default.py',
          'scripts/prepare_nvcc_probe.py','scripts/ct.py','scripts/run_validation.py',
          'tests/p04a_noop_driver.c','tests/p09a_noop_driver.c','tests/p04a_driver_control.def',
          'include/ct_cuda.h','include/ct_cudart.h','tests/m3c_gpu_validation.py']
UPSTREAM = dict(repository='https://github.com/NVIDIA/cuda-samples',revision=COMMIT,sources=PINS)
MODES = ('nominal','trace','noop')
PROVIDERS = {'nominal':'ct_cuda.dll','trace':'trace.dll','noop':'trace_noop.dll'}
STDOUT = (b'[Vector addition of 50000 elements]\n'
          b'Copy input data from the host memory to the CUDA device\n'
          b'CUDA kernel launch with 196 blocks of 256 threads\n'
          b'Copy output data from the CUDA device to the host memory\n'
          b'Test PASSED\nDone\n')


def recipes(folder, producer, base):
    cuda = compiler_args(folder,producer.parent,base['host'])
    cuda = ['vectorAdd.cu' if a=='vector.cu' else 'vectorAdd.exe' if a=='default.exe' else a for a in cuda]
    cuda += ['-I',str(folder/'Common')]
    cl = base['host']['tools']['cl.exe']['path']
    rows = dict(cuda=cuda,driver=['cargo','build','--locked','-p','ct-cuda'],
                runtime=['cargo','build','--locked','--manifest-path','crates/ct-cudart/Cargo.toml'])
    for name in ('trace','trace_noop'):
        args = [cl,'/nologo','/W4','/WX','/LD','/D_CRT_SECURE_NO_WARNINGS']
        if name=='trace_noop':args+=['/DTRACE_NOOP']
        rows[name]=args+[str(ROOT/'tests/upstream_vectoradd_trace.c'),'/Fo'+str(folder/(name+'.obj')),
                         '/Fe'+str(folder/(name+'.dll')),'/link','/DEF:'+str(ROOT/'tests/p04a_driver_control.def')]
    return rows


def payloads(files, mode):
    wanted={'vectorAdd.exe':files['vectorAdd.exe'],'nvcuda.dll':files[PROVIDERS[mode]],
            'cudart64_12.dll':files['ct_cudart.dll']}
    if mode!='nominal':wanted['ct_underlying.dll']=files['ct_cuda.dll']
    return wanted


def check_run(folder, files, row):
    if (set(row)!={'mode','bundle','payloads','observations','exit_code'} or row['mode'] not in MODES
            or type(row['exit_code']) is not int or row['exit_code']!=0):
        raise ValueError('external execution schema/status')
    mode=row['mode'];bundle=(folder/row['bundle']).resolve()
    if not bundle.is_relative_to(folder/'runs') or row['payloads']!=payloads(files,mode):
        raise ValueError('external bundle role/escape')
    expected={'stdout.bin','stderr.bin'}
    if mode!='nominal':expected|={'input-a.bin','input-b.bin','output.bin','trace.json'}
    if set(row['observations'])!=expected or {p.name for p in bundle.iterdir()}!=set(row['payloads'])|expected:
        raise ValueError('external observation set')
    verify_files(bundle,row['payloads']);verify_files(bundle,row['observations'])
    if (bundle/'stderr.bin').read_bytes() or (bundle/'stdout.bin').read_bytes().replace(b'\r\n',b'\n')!=STDOUT:
        raise ValueError('external sample output differs')
    if mode!='nominal':
        if validate_trace(json.loads((bundle/'trace.json').read_bytes()),noop=mode=='noop'):
            raise ValueError('external observed calls differ')
        a,b,c=((bundle/n).read_bytes() for n in ('input-a.bin','input-b.bin','output.bin'))
        if validate_inputs(a,b):raise ValueError('external captured inputs invalid')
        problems=validate_buffers(a,b,c)
        if mode=='trace' and problems:raise ValueError('external full numerical check failed')
        if mode=='noop' and (not problems or c!=struct.pack('<I',0x7fc00000)*50000):
            raise ValueError('external noop did not expose rejected NaN false-pass')


def check_set(folder, files, rows):
    if type(rows) is not list or [v['mode'] for v in rows]!=list(MODES):
        raise ValueError('external modes absent')
    for row in rows:check_run(folder,files,row)
    for name in ('input-a.bin','input-b.bin'):
        if rows[1]['observations'][name]!=rows[2]['observations'][name]:
            raise ValueError('deterministic trace/control inputs differ')


def observe(folder, files, mode):
    bundle,_=prepare_bundle(folder/'vectorAdd.exe',folder/PROVIDERS[mode],[],folder/'runs',runtime_dll=folder/'ct_cudart.dll')
    if mode!='nominal':shutil.copyfile(folder/'ct_cuda.dll',bundle/'ct_underlying.dll')
    wanted=payloads(files,mode);verify_files(bundle,wanted)
    result=subprocess.run([str(bundle/'vectorAdd.exe')],cwd=bundle,capture_output=True,timeout=60)
    verify_files(bundle,wanted)
    (bundle/'stdout.bin').write_bytes(result.stdout);(bundle/'stderr.bin').write_bytes(result.stderr)
    observations={p.name:digest(p) for p in bundle.iterdir() if p.name not in wanted}
    row=dict(mode=mode,bundle=bundle.relative_to(folder).as_posix(),payloads=wanted,
             observations=observations,exit_code=result.returncode)
    check_run(folder,files,row)
    return row


def independent_driver(folder):
    if sys.flags.optimize:
        raise ValueError('independent Driver checks require unoptimized Python')
    source=(folder/'keep/vectorAdd.ptx').read_bytes()
    names=re.findall(rb'\.entry\s+([A-Za-z_$][\w$]*)\s*\(',source)
    if len(names)!=1:raise ValueError('external kernel entry set differs')
    device=Device(folder/'ct_cuda.dll')
    try:
        for n in (1,63,64,65,257,50000):device.run(source,names[0].decode(),n)
    finally:device.close()
    return dict(cases=6,elements=50450,guards=384,entry=names[0].decode())


def audit(path):
    folder=path.resolve().parent
    if not folder.is_relative_to(ROOT/'.cache/upstream-vectoradd-runs'):raise ValueError('external capture escape')
    m=json.loads(path.read_bytes())
    if (set(m)!={'schema_version','scope','tier','release_claim','source_fingerprint','inputs',
                 'upstream','producer_sha256','commands','files','runs','independent_driver'}
            or type(m['schema_version']) is not int or m['schema_version']!=1
            or m['scope']!='diagnostic_upstream_vectoradd' or m['tier']!='upstream_adjusted_build'
            or m['release_claim'] is not False or m['upstream']!=UPSTREAM):
        raise ValueError('external scope/schema')
    if m['source_fingerprint']!=source_fingerprint(ROOT) or m['inputs']!={p:digest(ROOT/p) for p in INPUTS}:
        raise ValueError('external source drift')
    producer=ROOT/'.cache/p09a2-producer/manifest.json'
    if m['producer_sha256']!=digest(producer) or audit_probe(producer):raise ValueError('external producer drift')
    base=json.loads(producer.read_bytes())
    if base['host']['profile']!='diagnostic' or m['commands']!=recipes(folder,producer,base):
        raise ValueError('external build recipe differs')
    required=set(PINS)|{'vectorAdd.exe','ct_cuda.dll','ct_cudart.dll','trace.dll','trace_noop.dll',
        'keep/vectorAdd.ptx','keep/vectorAdd.fatbin','keep/vectorAdd_dlink.fatbin',
        'keep/vectorAdd.cudafe1.stub.c','keep/vectorAdd_dlink.reg.c'}
    if not required<=set(m['files']):raise ValueError('external artifact absent')
    verify_files(folder,m['files'])
    if any(m['files'][n]!=sha for n,sha in PINS.items()):raise ValueError('upstream source was modified')
    if ptx_tokens(payload(folder/'keep/vectorAdd.fatbin'))!=ptx_tokens((folder/'keep/vectorAdd.ptx').read_bytes()):
        raise ValueError('external PTX/payload differs')
    exe=(folder/'vectorAdd.exe').read_bytes()
    if any((folder/'keep'/n).read_bytes() not in exe for n in ('vectorAdd.fatbin','vectorAdd_dlink.fatbin')):
        raise ValueError('external images not embedded')
    check_set(folder,m['files'],m['runs'])
    witness=m['independent_driver']
    entries=re.findall(rb'\.entry\s+([A-Za-z_$][\w$]*)\s*\(',(folder/'keep/vectorAdd.ptx').read_bytes())
    if (type(witness) is not dict or set(witness)!={'cases','elements','guards','entry'}
            or any(type(witness[k]) is not int for k in ('cases','elements','guards'))
            or (witness['cases'],witness['elements'],witness['guards'])!=(6,50450,384)
            or len(entries)!=1 or witness['entry']!=entries[0].decode()):
        raise ValueError('independent Driver record differs')
    return m


def build():
    if sys.flags.optimize:raise ValueError('independent Driver checks require unoptimized Python')
    folder=ROOT/'.cache/upstream-vectoradd-runs'/uuid.uuid4().hex;folder.mkdir(parents=True)
    source=ROOT/'.cache/upstream-sources'/COMMIT
    verify_files(source,PINS)
    for name in PINS:
        target=folder/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/name,target)
    producer=ROOT/'.cache/p09a2-producer/manifest.json';base,env=host_environment(producer,folder)
    if base['host']['profile']!='diagnostic':raise ValueError('diagnostic host required')
    fingerprint=source_fingerprint(ROOT);inputs={p:digest(ROOT/p) for p in INPUTS}
    (folder/'keep').mkdir();commands=recipes(folder,producer,base)
    for role in ('cuda','trace','trace_noop'):command(commands[role],folder,env,role)
    for role,dll in (('driver','ct_cuda.dll'),('runtime','ct_cudart.dll')):
        build_env=dict(os.environ,CARGO_INCREMENTAL='0',CARGO_TARGET_DIR=str(folder/(role+'-target')))
        command(commands[role],folder,build_env,role,cwd=ROOT)
        shutil.copyfile(folder/(role+'-target/debug')/dll,folder/dll)
    names=list(PINS)+['vectorAdd.exe','ct_cuda.dll','ct_cudart.dll','trace.dll','trace_noop.dll']
    names += [p.relative_to(folder).as_posix() for p in (folder/'keep').iterdir()
              if p.is_file() and (p.suffix in ('.ptx','.fatbin') or p.name.endswith(('.stub.c','.reg.c','.fatbin.c')))]
    files={n:digest(folder/n) for n in names}
    rows=[]
    for mode in MODES:verify_files(folder,files);rows.append(observe(folder,files,mode))
    check_set(folder,files,rows)
    m=dict(schema_version=1,scope='diagnostic_upstream_vectoradd',tier='upstream_adjusted_build',
           release_claim=False,source_fingerprint=fingerprint,inputs=inputs,upstream=UPSTREAM,
           producer_sha256=digest(producer),commands=commands,files=files,runs=rows,
           independent_driver=independent_driver(folder))
    path=folder/'manifest.json';path.write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8');audit(path)
    return path,m


def replay(path):
    if sys.flags.optimize:raise ValueError('independent Driver checks require unoptimized Python')
    m=audit(path);sha=digest(path);folder=path.resolve().parent
    rows=[]
    for mode in MODES:verify_files(folder,m['files']);rows.append(observe(folder,m['files'],mode))
    check_set(folder,m['files'],rows)
    for name in ('input-a.bin','input-b.bin'):
        if rows[1]['observations'][name]!=m['runs'][1]['observations'][name]:
            raise ValueError('deterministic replay inputs differ')
    driver=independent_driver(folder);verify_files(folder,m['files'])
    if digest(path)!=sha or source_fingerprint(ROOT)!=m['source_fingerprint']:raise ValueError('external replay input drift')
    report=dict(manifest_sha256=sha,release_claim=False,runs=rows,independent_driver=driver)
    saved=folder/('replay-'+uuid.uuid4().hex+'.json');saved.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return m,saved


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);modes=parser.add_mutually_exclusive_group()
    modes.add_argument('--audit',type=Path);modes.add_argument('--replay',type=Path);args=parser.parse_args()
    try:
        path=args.audit or args.replay;saved=None
        if args.audit:m=audit(path)
        elif args.replay:m,saved=replay(path)
        else:path,m=build()
        print(json.dumps(dict(status='pass',scope=m['scope'],tier=m['tier'],release_claim=False,
                              execution_performed=not bool(args.audit),manifest=path.resolve().relative_to(ROOT).as_posix(),
                              replay=None if saved is None else saved.relative_to(ROOT).as_posix(),
                              application_sha256=m['files']['vectorAdd.exe'])))
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError):
        print(json.dumps(dict(status='fail',reason='upstream_vectoradd_diagnostic_failed')));raise SystemExit(1)
