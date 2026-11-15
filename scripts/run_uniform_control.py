"""Source-bound uniform shared-loop nvcc/Intel diagnostic; no release claim."""
import argparse
import json
from pathlib import Path
import re
import secrets
import shutil
import struct
import subprocess
from run_static_shared import build as build_parent
from run_runtime_attribute import ROOT
from run_relaxed_nvcc import command,host_environment,compiler_args,prepare_bundle,digest,verify_files,payload,ptx_tokens
from run_validation import source_fingerprint
from uniform_control_check import validate_result,inspect_spirv,erased_loop
from block_barrier_check import decode
from validate_spirv import run_validator

def require_ptx(text):
    entries=re.findall(r'\.entry\s+(\w+)\s*\([^)]*\)\s*\{([^}]*)\}',text)
    if len(entries)!=2 or len({n for n,_ in entries})!=2:raise ValueError('two distinct genuine entries required')
    for suffix,(_,body) in zip(('u32','f32'),entries):
        if (len(re.findall(r'\.shared\s+\.align\s+4\s+\.b8\s+\w+\[512\]',body))!=2
                or len(re.findall(r'\bbar\.sync\s+0\s*;',body))!=3
                or len(re.findall(r'@%\w+\s+bra\s+',body))!=2 or '.pragma "nounroll";' not in body):raise ValueError('genuine uniform loop shape differs')
        for stem in ('ld','st'):
            if len(re.findall(r'\b'+stem+r'\.volatile\.shared\.'+suffix+r'\b',body))!=2:raise ValueError('genuine volatile shared accesses missing')
    return [name for name,_ in entries]

def build(validator):
    parent=build_parent(validator);folder=parent.parent;fp=source_fingerprint(ROOT)
    if json.loads(parent.read_bytes())['source_fingerprint']!=fp:raise ValueError('source differs')
    producer=ROOT/'.cache/p09a2-producer/manifest.json';base,env=host_environment(producer,folder);commands={}
    def run(label,args):commands[label]=args;command(args,folder,env,label)
    shutil.copyfile(ROOT/'tests/fixtures/uniform_control_runtime.cu',folder/'uniform.cu');(folder/'keep-uniform').mkdir()
    args=[('uniform.cu' if x=='vector.cu' else 'uniform.exe' if x=='default.exe' else 'keep-uniform' if x=='keep' else x) for x in compiler_args(folder,producer.parent,base['host'])]
    run('uniform-cuda',args)
    text=(folder/'keep-uniform/uniform.ptx').read_text();entries=require_ptx(text)
    if ptx_tokens(payload(folder/'keep-uniform/uniform.fatbin'))!=ptx_tokens(text.encode('ascii')):raise ValueError('producer fatbin differs')
    shutil.copyfile(folder/'translate-shared.exe',folder/'translate-uniform.exe')
    run('uniform-translate',[str(folder/'translate-uniform.exe'),str(folder/'keep-uniform/uniform.ptx'),str(folder/'uniform.spv')])
    data=(folder/'uniform.spv').read_bytes();structure=inspect_spirv(data)
    lock=next(t for t in json.loads((ROOT/'docs/compatibility/toolchain-lock-v1.json').read_bytes())['tools'] if t['id']=='spirv-val')
    positive=run_validator(folder/'uniform.spv',validator,lock,required=True)
    if positive['status']!='pass':raise ValueError('positive validator failed')
    erased=folder/'bad-uniform-loop.spv';erased.write_bytes(erased_loop(data))
    try:inspect_spirv(erased.read_bytes())
    except ValueError:loop_rejected=True
    else:raise ValueError('erased loop mutation accepted')
    words,ops=decode(data);first=next(i for op,a,i in ops if op==250);words[first+2]=words[3]+17
    bad=folder/'bad-uniform-target.spv';bad.write_bytes(struct.pack('<'+'I'*len(words),*words))
    negative=run_validator(bad,validator,lock,required=True)
    if negative['status']!='fail' or negative['reason']!='validation_rejected':raise ValueError('validator negative not rejected')
    rejected=[];rejection_files=[]
    for index,body in enumerate((
        'mov.u32 %r0,%tid.x;setp.eq.u32 %p0,%r0,0;@%p0 bra.uni END;bar.sync 0;END:ret;',
        'ld.shared.u32 %r0,[a];setp.eq.u32 %p0,%r0,0;@%p0 bra END;bar.sync 0;END:ret;',
        'mov.u32 %r0,%ntid.x;setp.eq.u32 %p0,%r0,0;@%p0 bra ALT;mov.u64 %rd0,a;bra JOIN;ALT:mov.u64 %rd0,0;JOIN:ld.global.u32 %r1,[%rd0];ret;',
        'mov.u32 %r0,0;LOOP:setp.eq.u32 %p0,%r0,0;@%p0 bra BODY;ret;BODY:bar.sync 0;mov.u32 %r0,%tid.x;bra LOOP;',
        'LOOP:bar.sync 0;bra.uni LOOP;')):
        source=folder/('rejected-uniform-'+str(index)+'.ptx');out=source.with_suffix('.spv')
        source.write_text('.version 8.0 .target sm_52 .address_size 64 .entry unsafe(){.reg .pred %p<2>;.reg .b32 %r<8>;.reg .b64 %rd<2>;.shared .align 4 .b8 a[512];'+body+'}')
        r=subprocess.run([str(folder/'translate-uniform.exe'),str(source),str(out)],cwd=folder,capture_output=True,timeout=30)
        if r.returncode!=3 or r.stdout or not re.fullmatch(rb'line=\d+ category=unsupported\r?\n?',r.stderr) or out.exists():raise ValueError('unsafe uniform escaped rejection')
        source.with_suffix('.stderr').write_bytes(r.stderr);rejection_files.extend([source.name,source.with_suffix('.stderr').name])
        rejected.append(dict(input_sha256=digest(source),exit_code=r.returncode,stderr_sha256=digest(source.with_suffix('.stderr'))))
    files={n:digest(folder/n) for n in ['ct_cuda.dll','ct_cudart.dll','uniform.cu','uniform.exe','keep-uniform/uniform.ptx','keep-uniform/uniform.fatbin','translate-uniform.exe','uniform.spv','bad-uniform-loop.spv','bad-uniform-target.spv']+rejection_files}
    runs=[]
    for mode in ('positive','positive','noop_launch','noop_copy'):
        seed=secrets.randbelow(1000000)+1;provider={'positive':'ct_cuda.dll','noop_launch':'host-noop.dll','noop_copy':'copy-noop.dll'}[mode]
        bundle,_=prepare_bundle(folder/'uniform.exe',folder/provider,[],folder/'uniform-runs',runtime_dll=folder/'ct_cudart.dll')
        if mode!='positive':shutil.copyfile(folder/'ct_cuda.dll',bundle/'ct_underlying.dll')
        pins={p.name:digest(p) for p in bundle.iterdir() if p.is_file()}
        r=subprocess.run([str(bundle/'uniform.exe'),str(seed)],cwd=bundle,capture_output=True,timeout=60)
        (bundle/'stdout.json').write_bytes(r.stdout);(bundle/'stderr.txt').write_bytes(r.stderr);verify_files(bundle,pins)
        if mode=='positive':
            if r.returncode or r.stderr or not validate_result(json.loads(r.stdout),seed):raise ValueError('uniform numerical check failed')
        elif r.returncode!=42 or r.stdout or r.stderr:raise ValueError('uniform omission not detected')
        runs.append(dict(mode=mode,seed=seed,exit_code=r.returncode,files=pins,bundle=bundle.relative_to(folder).as_posix(),stdout_sha256=digest(bundle/'stdout.json'),stderr_sha256=digest(bundle/'stderr.txt')))
    verify_files(folder,files);verify_files(folder,json.loads(parent.read_bytes())['files'])
    if source_fingerprint(ROOT)!=fp:raise ValueError('source changed')
    target=folder/'uniform-control-manifest.json';target.write_text(json.dumps(dict(scope='diagnostic_uniform_control_flow',release_claim=False,source_fingerprint=fp,parent_manifest_sha256=digest(parent),files=files,commands=commands,entries=entries,structure=structure,validator_positive=positive,validator_negative=negative,erased_loop_mutation_rejected=loop_rejected,offline_rejections=rejected,runs=runs),indent=2)+'\n')
    (ROOT/'.cache/uniform-control-latest.json').write_text(json.dumps(dict(manifest=target.relative_to(ROOT).as_posix()))+'\n');return target

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--validator',type=Path,default=ROOT/'.cache/universal-foundation/spirv-build/tools/Release/spirv-val.exe');a=p.parse_args()
    print(json.dumps(dict(status='pass',manifest=build(a.validator).relative_to(ROOT).as_posix(),release_claim=False)))
