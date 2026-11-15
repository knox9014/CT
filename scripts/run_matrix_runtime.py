"""Pinned original EXE under TEST-ONLY injected architecture metadata. Not production compatibility."""
import argparse
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import uuid
from run_matrix_kernels import build as build_parent,audit as audit_parent
from run_relaxed_nvcc import digest,verify_files,command,host_environment
from run_validation import source_fingerprint
from check_compatibility_profile import expected_exports
from matrix_runtime_check import SHAPES,SCOPE,exact,scope_valid,trace_valid,buffers_valid,expected_output

ROOT=Path(__file__).resolve().parents[1]
MODES=('baseline','positive','positive','noop_launch','noop_copy')
INPUTS=('tests/matrix_runtime_metadata.c','tests/matrix_runtime_trace.c',
        'scripts/run_matrix_runtime.py','scripts/matrix_runtime_check.py','tests/test_matrix_runtime.py')

def argv_for(bundle,shape):
    if shape not in SHAPES:raise ValueError('matrix shape')
    m,k,n=shape
    return [str(bundle/'matrixMul.exe'),'-device=0',f'-wA={k}',f'-hA={m}',f'-wB={n}',f'-hB={k}']

def payloads(files,mode):
    result={'matrixMul.exe':files['matrixMul.exe'],'ct_underlying.dll':files['ct_cuda.dll']}
    if mode=='baseline':
        result.update({'nvcuda.dll':files['ct_cuda.dll'],'cudart64_12.dll':files['matrix-runtime-original.dll']})
    else:
        result.update({'nvcuda.dll':files[mode+'.dll'],'cudart64_12.dll':files['metadata.dll'],
                       'ct_runtime.dll':files['matrix-runtime-original.dll']})
    return result

def check_run(folder,files,row):
    if type(row) is not dict or set(row)!={'mode','shape','bundle','command','payloads','observations','exit_code','numerically_valid'}:raise ValueError('matrix runtime run schema')
    mode=row['mode'];shape=tuple(row['shape'])
    if mode not in set(MODES) or type(row['shape']) is not list or any(type(v) is not int for v in row['shape']) or shape not in SHAPES:raise ValueError('matrix runtime mode/shape')
    if type(row['bundle']) is not str or Path(row['bundle']).is_absolute():raise ValueError('matrix runtime bundle')
    bundle=(folder/row['bundle']).resolve()
    if not bundle.is_relative_to(folder/'matrix-runtime-runs') or row['command']!=argv_for(bundle,shape):raise ValueError('matrix runtime command/escape')
    wanted=payloads(files,mode)
    if row['payloads']!=wanted:raise ValueError('matrix runtime identities')
    expected={'stdout.bin','stderr.bin'}
    if mode!='baseline':expected|={'input-a.bin','input-b.bin','output.bin','trace.json','metadata.json'}
    if set(row['observations'])!=expected or {p.name for p in bundle.iterdir()}!=set(wanted)|expected:raise ValueError('matrix runtime artifacts')
    verify_files(bundle,wanted);verify_files(bundle,row['observations'])
    if type(row['exit_code']) is not int:raise ValueError('matrix runtime exit type')
    stdout=(bundle/'stdout.bin').read_bytes();stderr=(bundle/'stderr.bin').read_bytes()
    if mode=='baseline':
        if row['exit_code']==0 or b'cudaErrorNotSupported' not in stderr or b'cudaDevAttrComputeCapabilityMajor' not in stderr or row['numerically_valid'] is not None:raise ValueError('baseline must expose CC rejection')
        return
    if row['exit_code']!=0 or stderr or b'Result = PASS' not in stdout:raise ValueError('matrix Runtime path did not complete')
    if not exact(json.loads((bundle/'metadata.json').read_bytes()),dict(major_queries=1,minor_queries=1,major=5,minor=2)):raise ValueError('injected metadata queries differ')
    if not trace_valid(json.loads((bundle/'trace.json').read_bytes()),mode):raise ValueError('matrix trace differs')
    a,b,c=((bundle/n).read_bytes() for n in ('input-a.bin','input-b.bin','output.bin'))
    valid=buffers_valid(shape,a,b,c)
    if type(row['numerically_valid']) is not bool or row['numerically_valid']!=valid or valid!=(mode=='positive'):raise ValueError('external matrix oracle differs')
    if mode!='positive':
        # Exact canonical NaN for no-launch; arithmetic may canonicalize NaN payload in no-copy.
        if len(c)!=shape[0]*shape[2]*4 or any((v[0]&0x7f800000)!=0x7f800000 or not(v[0]&0x7fffff) for v in struct.iter_unpack('<I',c)):raise ValueError('omission NaN signature differs')
        if mode=='noop_launch' and c!=struct.pack('<I',0x7fc00000)*(shape[0]*shape[2]):raise ValueError('no-launch poison changed')
        # Host input capture must still be the original deterministic recipe.
        if not buffers_valid(shape,a,b,expected_output(shape)):raise ValueError('omission inputs changed')

def observe(folder,files,mode,shape):
    verify_files(folder,files)
    bundle=folder/'matrix-runtime-runs'/uuid.uuid4().hex;bundle.mkdir(parents=True)
    providers={'matrixMul.exe':'matrixMul.exe','ct_underlying.dll':'ct_cuda.dll'}
    if mode=='baseline':providers.update({'nvcuda.dll':'ct_cuda.dll','cudart64_12.dll':'matrix-runtime-original.dll'})
    else:providers.update({'nvcuda.dll':mode+'.dll','cudart64_12.dll':'metadata.dll','ct_runtime.dll':'matrix-runtime-original.dll'})
    for dst,src in providers.items():shutil.copyfile(folder/src,bundle/dst)
    wanted=payloads(files,mode);verify_files(bundle,wanted);argv=argv_for(bundle,shape)
    result=subprocess.run(argv,cwd=bundle,capture_output=True,timeout=60)
    (bundle/'stdout.bin').write_bytes(result.stdout);(bundle/'stderr.bin').write_bytes(result.stderr)
    row=dict(mode=mode,shape=list(shape),bundle=bundle.relative_to(folder).as_posix(),command=argv,payloads=wanted,
             observations={p.name:digest(p) for p in bundle.iterdir() if p.name not in wanted},exit_code=result.returncode,
             numerically_valid=None if mode=='baseline' else mode=='positive')
    # Save failed observation too: retained private evidence, never relabelled successful.
    (folder/'last-observation.json').write_text(json.dumps(row,indent=2)+'\n')
    check_run(folder,files,row);verify_files(folder,files);return row

def recipes(folder,producer,base):
    cl=base['host']['tools']['cl.exe']['path'];link=base['host']['tools']['link.exe']['path']
    rows={'importlib':[link,'/lib','/nologo','/machine:x64','/DEF:'+str(folder/'runtime-target.def'),'/OUT:'+str(folder/'runtime-target.lib')]}
    for mode in ('metadata','positive','noop_launch','noop_copy'):
        src='matrix_runtime_metadata.c' if mode=='metadata' else 'matrix_runtime_trace.c'
        argv=[cl,'/nologo','/utf-8','/W4','/WX','/LD','/D_CRT_SECURE_NO_WARNINGS','/I'+str(producer.parent/'toolkit/include')]
        if mode=='noop_launch':argv+=['/DMATRIX_NO_LAUNCH']
        if mode=='noop_copy':argv+=['/DMATRIX_NO_COPY']
        argv += [str(ROOT/'tests'/src),'/Fo'+str(folder/(mode+'.obj')),'/Fe'+str(folder/(mode+'.dll'))]
        if mode=='metadata':argv += [str(folder/'runtime-target.lib')]
        argv += ['/link','/DEF:'+str(folder/('metadata.def' if mode=='metadata' else 'matrix-trace.def'))]
        rows[mode]=argv
    return rows

def check_runs(folder,files,rows):
    if type(rows) is not list or len(rows)!=5 or [r['mode'] for r in rows]!=list(MODES) or [r['shape'] for r in rows]!=[list(SHAPES[0]),list(SHAPES[0]),list(SHAPES[1]),list(SHAPES[1]),list(SHAPES[1])]:raise ValueError('matrix runtime run set')
    for row in rows:check_run(folder,files,row)

def audit(path):
    path=Path(path).resolve();folder=path.parent;m=json.loads(path.read_bytes())
    if not folder.is_relative_to(ROOT/'.cache/runtime-attribute-runs') or set(m)!={'schema_version','scope','qualification','source_fingerprint','inputs','parent_sha256','commands','files','runs'} or type(m['schema_version']) is not int or m['schema_version']!=1 or m['scope']!='diagnostic_matrix_runtime_metadata_injected' or not scope_valid(m['qualification']):raise ValueError('matrix runtime scope')
    if m['source_fingerprint']!=source_fingerprint(ROOT) or m['inputs']!={n:digest(ROOT/n) for n in INPUTS}:raise ValueError('matrix runtime source drift')
    producer=ROOT/'.cache/p09a2-producer/manifest.json';base=json.loads(producer.read_bytes())
    if m['commands']!=recipes(folder,producer,base):raise ValueError('matrix runtime recipe drift')
    parent=folder/'matrix-kernel-manifest.json'
    if digest(parent)!=m['parent_sha256']:raise ValueError('matrix runtime parent drift')
    p=audit_parent(parent);triage=ROOT/p['references']['matrix']['path'];t=json.loads(triage.read_bytes())
    expected={'ct_cuda.dll','matrix-runtime-original.dll','matrixMul.exe','metadata.dll','positive.dll','noop_launch.dll','noop_copy.dll'}
    if set(m['files'])!=expected or m['files']['ct_cuda.dll']!=p['files']['ct_cuda.dll'] or m['files']['matrix-runtime-original.dll']!=t['reference']['files']['ct_cudart.dll'] or m['files']['matrixMul.exe']!=t['files']['matrixMul.exe']:raise ValueError('matrix runtime parent identities')
    verify_files(folder,m['files']);check_runs(folder,m['files'],m['runs']);return m

def build(validator):
    parent=build_parent(validator);folder=parent.parent;fp=source_fingerprint(ROOT)
    p=audit_parent(parent);triage=ROOT/p['references']['matrix']['path'];t=json.loads(triage.read_bytes());v=ROOT/t['reference']['path']
    shutil.copyfile(triage.parent/'matrixMul.exe',folder/'matrixMul.exe');shutil.copyfile(v/'ct_cudart.dll',folder/'matrix-runtime-original.dll')
    producer=ROOT/'.cache/p09a2-producer/manifest.json';base,env=host_environment(producer,folder)
    runtime=json.loads((ROOT/'docs/compatibility/runtime-profile-v1.json').read_bytes())
    names=[r['symbol'] for r in runtime['exports']]
    if len(names)!=40 or len(set(names))!=40:raise ValueError('runtime export set changed')
    (folder/'metadata.def').write_text('EXPORTS\n'+'\n'.join(n if n=='cudaDeviceGetAttribute' else n+'=ct_runtime.'+n for n in names)+'\n')
    (folder/'runtime-target.def').write_text('LIBRARY ct_runtime.dll\nEXPORTS\n'+'\n'.join(names)+'\n')
    (folder/'matrix-trace.def').write_text('EXPORTS\n'+'\n'.join(sorted(expected_exports(ROOT)))+'\n')
    commands=recipes(folder,producer,base)
    for mode,argv in commands.items():command(argv,folder,env,mode)
    files={n:digest(folder/n) for n in ('ct_cuda.dll','matrix-runtime-original.dll','matrixMul.exe','metadata.dll','positive.dll','noop_launch.dll','noop_copy.dll')}
    rows=[observe(folder,files,mode,SHAPES[0] if i<2 else SHAPES[1]) for i,mode in enumerate(MODES)]
    if fp!=source_fingerprint(ROOT):raise ValueError('matrix runtime source changed')
    path=folder/'matrix-runtime-manifest.json';path.write_text(json.dumps(dict(schema_version=1,scope='diagnostic_matrix_runtime_metadata_injected',qualification=SCOPE,source_fingerprint=fp,inputs={n:digest(ROOT/n) for n in INPUTS},parent_sha256=digest(parent),commands=commands,files=files,runs=rows),indent=2)+'\n')
    audit(path);(ROOT/'.cache/matrix-runtime-latest.json').write_text(json.dumps(dict(manifest=path.relative_to(ROOT).as_posix()))+'\n');return path

def replay(path):
    m=audit(path);folder=path.resolve().parent;sha=digest(path)
    rows=[observe(folder,m['files'],r['mode'],tuple(r['shape'])) for r in m['runs']];check_runs(folder,m['files'],rows)
    for old,new in zip(m['runs'],rows):
        for n in ('input-a.bin','input-b.bin','output.bin','trace.json','metadata.json') if old['mode']!='baseline' else ():
            if old['observations'][n]!=new['observations'][n]:raise ValueError('matrix runtime deterministic replay differs')
    audit(path)
    if digest(path)!=sha:raise ValueError('manifest changed during replay')
    saved=folder/('matrix-runtime-replay-'+uuid.uuid4().hex+'.json');saved.write_text(json.dumps(dict(manifest_sha256=sha,qualification=SCOPE,runs=rows),indent=2)+'\n');return saved

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group();g.add_argument('--audit',type=Path);g.add_argument('--replay',type=Path)
    p.add_argument('--validator',type=Path,default=ROOT/'.cache/universal-foundation/spirv-build/tools/Release/spirv-val.exe');args=p.parse_args()
    if sys.flags.optimize:raise ValueError('unoptimized verification required')
    if args.audit:path=args.audit;audit(path)
    elif args.replay:path=replay(args.replay)
    else:path=build(args.validator)
    print(json.dumps(dict(status='pass',record=path.resolve().relative_to(ROOT).as_posix(),qualification=SCOPE)))
