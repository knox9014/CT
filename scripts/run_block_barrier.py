"""Uniform CTA barrier proof: actual validator, native nvcc work and controls."""
import argparse
import json
from pathlib import Path
import re
import secrets
import shutil
import struct
import subprocess
from run_profiler import build as build_parent
from run_runtime_attribute import ROOT
from run_relaxed_nvcc import command,host_environment,compiler_args,prepare_bundle,digest,verify_files,payload,ptx_tokens
from run_validation import source_fingerprint
from block_barrier_check import validate_result,inspect_spirv,invalid_execution_scope,decode
from validate_spirv import run_validator

def require_ptx(text):
    entries=re.findall(r'\.entry\s+(\w+)\s*\([^)]*\)\s*\{([^}]*)\}',text)
    if len(entries)!=2 or len({name for name,_ in entries})!=2:raise ValueError('expected distinct genuine entries')
    for _,body in entries:
        if len(re.findall(r'\bbar\.sync\s+0\s*;',body))!=3 or re.search(r'\bbra\b|\.shared|@',body):raise ValueError('nonlinear or unexpected barrier producer')
    return [name for name,_ in entries]

def build(validator):
    parent=build_parent();folder=parent.parent;fp=source_fingerprint(ROOT)
    if json.loads(parent.read_bytes())['source_fingerprint']!=fp:raise ValueError('source differs')
    producer=ROOT/'.cache/p09a2-producer/manifest.json';base,env=host_environment(producer,folder);commands={}
    def run(label,args,cwd=None,environment=env):commands[label]=args;command(args,folder,environment,label,cwd=cwd)
    shutil.copyfile(ROOT/'tests/fixtures/block_barrier_runtime.cu',folder/'barrier.cu');(folder/'keep-barrier').mkdir()
    args=[('barrier.cu' if x=='vector.cu' else 'barrier.exe' if x=='default.exe' else 'keep-barrier' if x=='keep' else x) for x in compiler_args(folder,producer.parent,base['host'])]
    run('barrier-cuda',args)
    text=(folder/'keep-barrier/barrier.ptx').read_text();entries=require_ptx(text)
    if ptx_tokens(payload(folder/'keep-barrier/barrier.fatbin'))!=ptx_tokens(text.encode('ascii')):raise ValueError('producer fatbin differs')
    import os
    run('barrier-translator',['cargo','build','--locked','-p','ct-codegen-spirv','--example','translate_module','--target-dir',str(folder/'translator-target')],ROOT,dict(os.environ,CARGO_INCREMENTAL='0'))
    translator=folder/'translator-target/debug/examples/translate_module.exe';shutil.copyfile(translator,folder/'translate-barrier.exe')
    run('barrier-translate',[str(folder/'translate-barrier.exe'),str(folder/'keep-barrier/barrier.ptx'),str(folder/'barrier.spv')])
    structure=inspect_spirv((folder/'barrier.spv').read_bytes())
    lock=next(t for t in json.loads((ROOT/'docs/compatibility/toolchain-lock-v1.json').read_bytes())['tools'] if t['id']=='spirv-val')
    positive=run_validator(folder/'barrier.spv',validator,lock,required=True)
    if positive['status']!='pass':raise ValueError('positive official validator failed')
    # A structurally accepted module can still have wrong CTA semantics. Never run mutations.
    semantic=folder/'bad-barrier-scope.spv';semantic.write_bytes(invalid_execution_scope((folder/'barrier.spv').read_bytes()))
    try:inspect_spirv(semantic.read_bytes())
    except ValueError:semantic_rejected=True
    else:raise ValueError('exact scope check did not reject mutation')
    words,ops=decode((folder/'barrier.spv').read_bytes());first=next(i for op,_,i in ops if op==224);words[first+1]=words[3]+17
    bad=folder/'undefined-barrier-scope.spv';bad.write_bytes(struct.pack('<'+'I'*len(words),*words))
    negative=run_validator(bad,validator,lock,required=True)
    if negative['status']!='fail' or negative['reason']!='validation_rejected':raise ValueError('official validator negative control failed')
    rejected=[]
    for index,body in enumerate(('bar.sync 1;ret;','bar.sync 0,64;ret;','.reg .pred %p;.reg .u32 %r;mov.u32 %r,%tid.x;setp.eq.u32 %p,%r,0;@%p bra.uni NEXT;bar.sync 0;NEXT:ret;')):
        source=folder/('rejected-barrier-'+str(index)+'.ptx');out=source.with_suffix('.spv');source.write_text('.version 8.0 .target sm_52 .address_size 64 .entry unsafe(){'+body+'}')
        r=subprocess.run([str(folder/'translate-barrier.exe'),str(source),str(out)],cwd=folder,capture_output=True,timeout=30)
        if r.returncode!=3 or r.stdout or not re.fullmatch(rb'line=\d+ category=unsupported\r?\n?',r.stderr) or out.exists():raise ValueError('unsafe barrier escaped offline rejection')
        (source.with_suffix('.stderr')).write_bytes(r.stderr);rejected.append(dict(input_sha256=digest(source),exit_code=r.returncode,stderr_sha256=digest(source.with_suffix('.stderr'))))
    files={n:digest(folder/n) for n in ['ct_cuda.dll','ct_cudart.dll','barrier.cu','barrier.exe','keep-barrier/barrier.ptx','keep-barrier/barrier.fatbin','translate-barrier.exe','barrier.spv','bad-barrier-scope.spv','undefined-barrier-scope.spv']}
    for index in range(3):
        for suffix in ('ptx','stderr'):
            name='rejected-barrier-'+str(index)+'.'+suffix;files[name]=digest(folder/name)
    runs=[]
    for mode in ('positive','positive','noop_launch','noop_copy'):
        seed=secrets.randbelow(1000000)+1;provider={'positive':'ct_cuda.dll','noop_launch':'host-noop.dll','noop_copy':'copy-noop.dll'}[mode]
        bundle,_=prepare_bundle(folder/'barrier.exe',folder/provider,[],folder/'barrier-runs',runtime_dll=folder/'ct_cudart.dll')
        if mode!='positive':shutil.copyfile(folder/'ct_cuda.dll',bundle/'ct_underlying.dll')
        pins={p.name:digest(p) for p in bundle.iterdir() if p.is_file()}
        r=subprocess.run([str(bundle/'barrier.exe'),str(seed)],cwd=bundle,capture_output=True,timeout=60)
        (bundle/'stdout.json').write_bytes(r.stdout);(bundle/'stderr.txt').write_bytes(r.stderr);verify_files(bundle,pins)
        if mode=='positive':
            if r.returncode or r.stderr or not validate_result(json.loads(r.stdout),seed):raise ValueError('barrier numerical check failed')
        elif r.returncode!=42 or r.stdout or r.stderr:raise ValueError('barrier launch/copy omission not detected')
        runs.append(dict(mode=mode,seed=seed,exit_code=r.returncode,files=pins,bundle=bundle.relative_to(folder).as_posix(),stdout_sha256=digest(bundle/'stdout.json'),stderr_sha256=digest(bundle/'stderr.txt')))
    verify_files(folder,files);verify_files(folder,json.loads(parent.read_bytes())['files'])
    if source_fingerprint(ROOT)!=fp:raise ValueError('source changed')
    target=folder/'block-barrier-manifest.json';target.write_text(json.dumps(dict(scope='diagnostic_uniform_block_barrier',release_claim=False,source_fingerprint=fp,parent_manifest_sha256=digest(parent),files=files,commands=commands,entries=entries,structure=structure,validator_positive=positive,validator_negative=negative,semantic_mutation_rejected=semantic_rejected,offline_rejections=rejected,runs=runs),indent=2)+'\n')
    (ROOT/'.cache/block-barrier-latest.json').write_text(json.dumps(dict(manifest=target.relative_to(ROOT).as_posix()))+'\n');return target

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--validator',type=Path,default=ROOT/'.cache/universal-foundation/spirv-build/tools/Release/spirv-val.exe');a=p.parse_args()
    print(json.dumps(dict(status='pass',manifest=build(a.validator).relative_to(ROOT).as_posix(),release_claim=False)))
