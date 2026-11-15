"""Source-bound fused-F32 nvcc/Intel diagnostic; no release claim."""
import argparse
import json
from pathlib import Path
import re
import secrets
import shutil
import subprocess
from run_uniform_control import build as build_parent
from run_runtime_attribute import ROOT
from run_relaxed_nvcc import command,host_environment,compiler_args,prepare_bundle,digest,verify_files,payload,ptx_tokens
from run_validation import source_fingerprint
from fma_check import validate_result,inspect_spirv,mutate_fma
from validate_spirv import run_validator

def require_ptx(text):
    entries=re.findall(r'\.entry\s+(\w+)\s*\([^)]*\)\s*\{([^}]*)\}',text)
    if len(entries)!=3 or len({n for n,_ in entries})!=3:raise ValueError('three genuine entries required')
    for index,(_,body) in enumerate(entries):
        expected=(1,0,0) if index<2 else (0,1,1)
        counts=tuple(len(re.findall(r'\b'+re.escape(op)+r'\s',body)) for op in ('fma.rn.f32','mul.rn.f32','add.rn.f32'))
        if counts!=expected or re.search(r'\bbra\b|@|\.shared',body):raise ValueError('genuine fused/split PTX differs')
    return [name for name,_ in entries]

def build(validator):
    parent=build_parent(validator);folder=parent.parent;fp=source_fingerprint(ROOT)
    if json.loads(parent.read_bytes())['source_fingerprint']!=fp:raise ValueError('source differs')
    producer=ROOT/'.cache/p09a2-producer/manifest.json';base,env=host_environment(producer,folder);commands={}
    def run(label,args):commands[label]=args;command(args,folder,env,label)
    shutil.copyfile(ROOT/'tests/fixtures/fma_runtime.cu',folder/'fma.cu');(folder/'keep-fma').mkdir()
    args=[('fma.cu' if x=='vector.cu' else 'fma.exe' if x=='default.exe' else 'keep-fma' if x=='keep' else x) for x in compiler_args(folder,producer.parent,base['host'])]
    run('fma-cuda',args)
    text=(folder/'keep-fma/fma.ptx').read_text();entries=require_ptx(text)
    if ptx_tokens(payload(folder/'keep-fma/fma.fatbin'))!=ptx_tokens(text.encode('ascii')):raise ValueError('producer fatbin differs')
    shutil.copyfile(folder/'translate-uniform.exe',folder/'translate-fma.exe')
    run('fma-translate',[str(folder/'translate-fma.exe'),str(folder/'keep-fma/fma.ptx'),str(folder/'fma.spv')])
    data=(folder/'fma.spv').read_bytes();structure=inspect_spirv(data)
    lock=next(t for t in json.loads((ROOT/'docs/compatibility/toolchain-lock-v1.json').read_bytes())['tools'] if t['id']=='spirv-val')
    positive=run_validator(folder/'fma.spv',validator,lock,required=True)
    if positive['status']!='pass':raise ValueError('positive validator failed')
    erased=folder/'bad-fma-mad.spv';erased.write_bytes(mutate_fma(data,semantic=True))
    try:inspect_spirv(erased.read_bytes())
    except ValueError:mad_rejected=True
    else:raise ValueError('mad substitution accepted')
    bad=folder/'bad-fma-import.spv';bad.write_bytes(mutate_fma(data,semantic=False))
    negative=run_validator(bad,validator,lock,required=True)
    if negative['status']!='fail' or negative['reason']!='validation_rejected':raise ValueError('validator negative not rejected')
    rejected=[];rejection_files=[]
    for index,op in enumerate(('fma.f32','fma.rz.f32','fma.rn.ftz.f32','fma.rn.sat.f32','fma.rn.f64')):
        body=op+' %f3,%f0,%f1,%f2;ret;'
        source=folder/('rejected-fma-'+str(index)+'.ptx');out=source.with_suffix('.spv')
        source.write_text('.version 8.0 .target sm_52 .address_size 64 .entry unsafe(){.reg .f32 %f<4>;mov.f32 %f0,0f3f800000;mov.f32 %f1,0f3f800000;mov.f32 %f2,0f00000000;'+body+'}')
        r=subprocess.run([str(folder/'translate-fma.exe'),str(source),str(out)],cwd=folder,capture_output=True,timeout=30)
        if r.returncode!=3 or r.stdout or not re.fullmatch(rb'line=\d+ category=unsupported\r?\n?',r.stderr) or out.exists():raise ValueError('unsupported FMA escaped rejection')
        source.with_suffix('.stderr').write_bytes(r.stderr);rejection_files.extend([source.name,source.with_suffix('.stderr').name])
        rejected.append(dict(input_sha256=digest(source),exit_code=r.returncode,stderr_sha256=digest(source.with_suffix('.stderr'))))
    files={n:digest(folder/n) for n in ['ct_cuda.dll','ct_cudart.dll','fma.cu','fma.exe','keep-fma/fma.ptx','keep-fma/fma.fatbin','translate-fma.exe','fma.spv','bad-fma-mad.spv','bad-fma-import.spv']+rejection_files}
    runs=[]
    for mode in ('positive','positive','noop_launch','noop_copy'):
        seed=secrets.randbelow(1000000)+1;provider={'positive':'ct_cuda.dll','noop_launch':'host-noop.dll','noop_copy':'copy-noop.dll'}[mode]
        bundle,_=prepare_bundle(folder/'fma.exe',folder/provider,[],folder/'fma-runs',runtime_dll=folder/'ct_cudart.dll')
        if mode!='positive':shutil.copyfile(folder/'ct_cuda.dll',bundle/'ct_underlying.dll')
        pins={p.name:digest(p) for p in bundle.iterdir() if p.is_file()}
        r=subprocess.run([str(bundle/'fma.exe'),str(seed)],cwd=bundle,capture_output=True,timeout=60)
        (bundle/'stdout.json').write_bytes(r.stdout);(bundle/'stderr.txt').write_bytes(r.stderr);verify_files(bundle,pins)
        if mode=='positive':
            if r.returncode or r.stderr or not validate_result(json.loads(r.stdout),seed):raise ValueError('FMA numerical check failed')
        elif r.returncode!=42 or r.stdout or r.stderr:raise ValueError('FMA omission not detected')
        runs.append(dict(mode=mode,seed=seed,exit_code=r.returncode,files=pins,bundle=bundle.relative_to(folder).as_posix(),stdout_sha256=digest(bundle/'stdout.json'),stderr_sha256=digest(bundle/'stderr.txt')))
    verify_files(folder,files);verify_files(folder,json.loads(parent.read_bytes())['files'])
    if source_fingerprint(ROOT)!=fp:raise ValueError('source changed')
    target=folder/'fma-manifest.json';target.write_text(json.dumps(dict(scope='diagnostic_fused_f32',release_claim=False,source_fingerprint=fp,parent_manifest_sha256=digest(parent),files=files,commands=commands,entries=entries,structure=structure,validator_positive=positive,validator_negative=negative,mad_mutation_rejected=mad_rejected,offline_rejections=rejected,runs=runs),indent=2)+'\n')
    (ROOT/'.cache/fma-latest.json').write_text(json.dumps(dict(manifest=target.relative_to(ROOT).as_posix()))+'\n');return target

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--validator',type=Path,default=ROOT/'.cache/universal-foundation/spirv-build/tools/Release/spirv-val.exe');a=p.parse_args()
    print(json.dumps(dict(status='pass',manifest=build(a.validator).relative_to(ROOT).as_posix(),release_claim=False)))
