"""Source-bound static shared nvcc/Intel diagnostic, never a release claim."""
import argparse
import json
from pathlib import Path
import re
import secrets
import shutil
import struct
import subprocess
from run_block_barrier import build as build_parent
from run_runtime_attribute import ROOT
from run_relaxed_nvcc import command,host_environment,compiler_args,prepare_bundle,digest,verify_files,payload,ptx_tokens
from run_validation import source_fingerprint
from static_shared_check import validate_result,inspect_spirv,invalid_shared_alias
from block_barrier_check import decode
from validate_spirv import run_validator

def require_ptx(text):
    entries=re.findall(r'\.entry\s+(\w+)\s*\([^)]*\)\s*\{([^}]*)\}',text)
    if len(entries)!=2 or len({n for n,_ in entries})!=2:raise ValueError('two distinct genuine entries required')
    for _,body in entries:
        if (len(re.findall(r'\.shared\s+\.align\s+4\s+\.b8\s+\w+\[512\]',body))!=2
                or len(re.findall(r'\bbar\.sync\s+0\s*;',body))!=3 or re.search(r'\bbra\b|@',body)):raise ValueError('genuine shared shape differs')
    for suffix,(_,body) in zip(('u32','f32'),entries):
        for stem in ('ld','st'):
            if len(re.findall(r'\b'+stem+r'\.volatile\.shared\.'+suffix+r'\b',body))!=3:raise ValueError('genuine volatile shared accesses missing')
    return [name for name,_ in entries]

def build(validator):
    parent=build_parent(validator);folder=parent.parent;fp=source_fingerprint(ROOT)
    if json.loads(parent.read_bytes())['source_fingerprint']!=fp:raise ValueError('source differs')
    producer=ROOT/'.cache/p09a2-producer/manifest.json';base,env=host_environment(producer,folder);commands={}
    def run(label,args):commands[label]=args;command(args,folder,env,label)
    shutil.copyfile(ROOT/'tests/fixtures/static_shared_runtime.cu',folder/'shared.cu');(folder/'keep-shared').mkdir()
    args=[('shared.cu' if x=='vector.cu' else 'shared.exe' if x=='default.exe' else 'keep-shared' if x=='keep' else x) for x in compiler_args(folder,producer.parent,base['host'])]
    run('shared-cuda',args)
    text=(folder/'keep-shared/shared.ptx').read_text();entries=require_ptx(text)
    if ptx_tokens(payload(folder/'keep-shared/shared.fatbin'))!=ptx_tokens(text.encode('ascii')):raise ValueError('producer fatbin differs')
    shutil.copyfile(folder/'translate-barrier.exe',folder/'translate-shared.exe')
    run('shared-translate',[str(folder/'translate-shared.exe'),str(folder/'keep-shared/shared.ptx'),str(folder/'shared.spv')])
    data=(folder/'shared.spv').read_bytes();structure=inspect_spirv(data)
    lock=next(t for t in json.loads((ROOT/'docs/compatibility/toolchain-lock-v1.json').read_bytes())['tools'] if t['id']=='spirv-val')
    positive=run_validator(folder/'shared.spv',validator,lock,required=True)
    if positive['status']!='pass':raise ValueError('positive validator failed')
    alias=folder/'bad-shared-alias.spv';alias.write_bytes(invalid_shared_alias(data))
    try:inspect_spirv(alias.read_bytes())
    except ValueError:alias_rejected=True
    else:raise ValueError('object alias mutation accepted')
    words,ops=decode(data);first=next(i for op,a,i in ops if op==59 and a[2]==4);words[first+3]=5
    bad=folder/'bad-shared-storage.spv';bad.write_bytes(struct.pack('<'+'I'*len(words),*words))
    negative=run_validator(bad,validator,lock,required=True)
    if negative['status']!='fail' or negative['reason']!='validation_rejected':raise ValueError('validator negative not rejected')
    rejected=[];rejection_files=[]
    for index,body in enumerate((
        '.shared .align 4 .b8 a[512];mov.u64 %rd0,a;ld.global.u32 %r0,[%rd0];ret;',
        '.shared .align 4 .b8 a[512];mov.u32 %r0,a;add.u32 %r1,%r0,1;ld.shared.u32 %r2,[%r1];ret;',
        '.extern .shared .align 4 .b8 a[];ret;',
        '.shared .align 4 .b8 a[512];.reg .pred %p;mov.u32 %r0,%tid.x;setp.eq.u32 %p,%r0,0;@%p bra.uni NEXT;bar.sync 0;NEXT:ret;',
        '.shared .align 4 .b8 a[512];mov.u64 %rd0,4294967296;cvt.u32.u64 %r0,%rd0;mov.u32 %r1,%tid.x;shl.b32 %r2,%r1,%r0;mov.u32 %r3,a;add.u32 %r4,%r3,%r2;ld.shared.u32 %r5,[%r4];ret;')):
        source=folder/('rejected-shared-'+str(index)+'.ptx');out=source.with_suffix('.spv')
        source.write_text('.version 8.0 .target sm_52 .address_size 64 .entry unsafe(){.reg .b32 %r<8>;.reg .b64 %rd<2>;'+body+'}')
        r=subprocess.run([str(folder/'translate-shared.exe'),str(source),str(out)],cwd=folder,capture_output=True,timeout=30)
        if r.returncode!=3 or r.stdout or not re.fullmatch(rb'line=\d+ category=unsupported\r?\n?',r.stderr) or out.exists():raise ValueError('unsafe shared escaped rejection')
        source.with_suffix('.stderr').write_bytes(r.stderr);rejection_files.extend([source.name,source.with_suffix('.stderr').name])
        rejected.append(dict(input_sha256=digest(source),exit_code=r.returncode,stderr_sha256=digest(source.with_suffix('.stderr'))))
    files={n:digest(folder/n) for n in ['ct_cuda.dll','ct_cudart.dll','shared.cu','shared.exe','keep-shared/shared.ptx','keep-shared/shared.fatbin','translate-shared.exe','shared.spv','bad-shared-alias.spv','bad-shared-storage.spv']+rejection_files}
    runs=[]
    for mode in ('positive','positive','noop_launch','noop_copy'):
        seed=secrets.randbelow(1000000)+1;provider={'positive':'ct_cuda.dll','noop_launch':'host-noop.dll','noop_copy':'copy-noop.dll'}[mode]
        bundle,_=prepare_bundle(folder/'shared.exe',folder/provider,[],folder/'shared-runs',runtime_dll=folder/'ct_cudart.dll')
        if mode!='positive':shutil.copyfile(folder/'ct_cuda.dll',bundle/'ct_underlying.dll')
        pins={p.name:digest(p) for p in bundle.iterdir() if p.is_file()}
        r=subprocess.run([str(bundle/'shared.exe'),str(seed)],cwd=bundle,capture_output=True,timeout=60)
        (bundle/'stdout.json').write_bytes(r.stdout);(bundle/'stderr.txt').write_bytes(r.stderr);verify_files(bundle,pins)
        if mode=='positive':
            if r.returncode or r.stderr or not validate_result(json.loads(r.stdout),seed):raise ValueError('shared numerical check failed')
        elif r.returncode!=42 or r.stdout or r.stderr:raise ValueError('shared omission not detected')
        runs.append(dict(mode=mode,seed=seed,exit_code=r.returncode,files=pins,bundle=bundle.relative_to(folder).as_posix(),stdout_sha256=digest(bundle/'stdout.json'),stderr_sha256=digest(bundle/'stderr.txt')))
    verify_files(folder,files);verify_files(folder,json.loads(parent.read_bytes())['files'])
    if source_fingerprint(ROOT)!=fp:raise ValueError('source changed')
    target=folder/'static-shared-manifest.json';target.write_text(json.dumps(dict(scope='diagnostic_static_shared_memory',release_claim=False,source_fingerprint=fp,parent_manifest_sha256=digest(parent),files=files,commands=commands,entries=entries,structure=structure,validator_positive=positive,validator_negative=negative,alias_mutation_rejected=alias_rejected,offline_rejections=rejected,runs=runs),indent=2)+'\n')
    (ROOT/'.cache/static-shared-latest.json').write_text(json.dumps(dict(manifest=target.relative_to(ROOT).as_posix()))+'\n');return target

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--validator',type=Path,default=ROOT/'.cache/universal-foundation/spirv-build/tools/Release/spirv-val.exe');a=p.parse_args()
    print(json.dumps(dict(status='pass',manifest=build(a.validator).relative_to(ROOT).as_posix(),release_claim=False)))
