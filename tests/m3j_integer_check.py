"""Runtime-seeded integer probes with independent Python bit arithmetic oracle."""
import ctypes as c
import hashlib
import itertools
import json
import subprocess
import sys
from pathlib import Path

from m3c_gpu_validation import Device,P,U32,U64,REPO
from m3d_fatbin_check import Producer
from m3f_selection_check import load_code
from m3g_modules_check import module,function

FIXTURE=REPO/'tests/fixtures/integer_bits.ptx'

def patterns(width):
    return [0,1,(1<<(width-1))-1,1<<(width-1),(1<<width)-1,int('a5'*(width//8),16)]

def cases():
    output=[]
    for dst,src in itertools.product(('s32','u32','s64','u64'),repeat=2):
        width=int(src[1:])
        for a in patterns(width): output.append((f'cvt.{dst}.{src}',width,int(dst[1:]),src[0]=='s',a,0))
    for width in (32,64):
        for name in ('and','or','xor','not'):
            for a in patterns(width):
                for b in ([0] if name=='not' else [0,(1<<width)-1,int('55'*(width//8),16)]):
                    output.append((f'{name}.b{width}',width,width,False,a,b))
        for name in ('shl.b','shr.b','shr.u','shr.s'):
            for a in patterns(width):
                for b in (0,1,width-1,width,width+1,0xffffffff):
                    output.append((f'{name}{width}',width,width,name=='shr.s',a,b))
    return output

def oracle(case,seed):
    op,width,target,signed,a,b=case
    mask=(1<<width)-1;a=(a+seed)&mask
    if op.startswith('cvt.'):
        if signed and a&(1<<(width-1)):a-=1<<width
        return a&((1<<target)-1)
    if op.startswith('not.'):return (~a)&mask
    if op.startswith('and.'):return a&b
    if op.startswith('or.'):return a|b
    if op.startswith('xor.'):return a^b
    count=(b+seed)&0xffffffff
    if op.startswith('shl.'):return ((a<<count)&mask) if count<width else 0
    if signed:
        if a&(1<<(width-1)):a-=1<<width
        return (a>>min(count,width))&mask
    return a>>count if count<width else 0

def source(batch,seed=0,profile=7):
    # The pinned producer strips its first source line; preserve the version
    # directive by using the same leading-comment convention as other fixtures.
    text=f'''// Synthetic runtime-seeded integer oracle probe.
.version {profile}.0
.target sm_{50 if profile==7 else 52}
.address_size 64
.visible .entry integer_checks(
    .param .u64 .ptr .global .align 4 output,
    .param .u32 seed
) {{
    .reg .b32 %r<4>;
    .reg .b64 %d<4>;
    .reg .pred %p;
    .reg .f32 %f;
    ld.param.u64 %d0, [output];
    ld.param.u32 %r0, [seed];
'''
    for index,case in enumerate(batch):
        op,width,target,signed,a,b=case
        if width==32:
            text+=f'    add.u32 %r1, %r0, 0x{a:x};\n';arg='%r1'
        else:
            text+=f'    mul.wide.u32 %d1, %r0, 1;\n    add.u64 %d1, %d1, 0x{a:x};\n';arg='%d1'
        dst='%r3' if target==32 else '%d3'
        if op.startswith('cvt.') or op.startswith('not.'):
            text+=f'    {op} {dst}, {arg};\n'
        elif op.startswith(('shl.','shr.')):
            text+=f'    add.u32 %r2, %r0, 0x{b:x};\n    {op} {dst}, {arg}, %r2;\n'
        else:text+=f'    {op} {dst}, {arg}, 0x{b:x};\n'
        expected=oracle(case,seed)
        text+=f'    setp.eq.u{target} %p, {dst}, 0x{expected:x};\n    selp.f32 %f, 0f3f800000, 0f00000000, %p;\n    st.global.f32 [%d0+{index*4}], %f;\n'
    return (text+'    ret;\n}\n').encode()

def fixture_cases():
    # All32 accepted spellings, one high-bit example each in the C consumer.
    chosen={}
    for case in cases():
        if case[4]==(1<<(case[1]-1)) and (not case[0].startswith(('shl.','shr.')) or case[5]==case[1]):
            chosen.setdefault(case[0],case)
    assert len(chosen)==32
    return list(chosen.values())

def execute(device,image,n,seed):
    owner=module(device,image);address=U64()
    output=(c.c_float*(n+64))(*([float('nan')]*n+[-12345.25]*64))
    try:
        handle=function(device,owner,'integer_checks')
        device.call('cuMemAlloc_v2',c.byref(address),c.sizeof(output))
        device.call('cuMemcpyHtoD_v2',address,c.cast(output,P),c.sizeof(output))
        value=U32(seed);args=(P*2)(c.cast(c.pointer(address),P),c.cast(c.pointer(value),P))
        device.call('cuLaunchKernel',handle,1,1,1,1,1,1,0,None,args,None)
        device.call('cuMemcpyDtoH_v2',c.cast(output,P),address,c.sizeof(output))
        for i in range(n):
            if output[i]!=1.0:raise RuntimeError(f'integer CPU oracle mismatch at batch index {i}')
        if any(v!=-12345.25 for v in output[n:]):raise RuntimeError('integer output guard modified')
    finally:
        if address.value:device.call('cuMemFree_v2',address)
        device.call('cuModuleUnload',owner)

def application_check(build,asset):
    sys.path.insert(0,str(REPO/'scripts'))
    from ct import digest,prepare_bundle
    folder=(REPO/build).resolve()
    if not folder.is_relative_to(REPO/'.cache/m3j-build'):raise RuntimeError('unexpected application build directory')
    app=folder/'m3j_cuda_app.exe';original=digest(app.read_bytes());asset_hash=digest(asset.read_bytes())
    bundle,report=prepare_bundle(app,REPO/'target/debug/ct_cuda.dll',[asset],REPO/'.cache/runs')
    child=subprocess.run([str(bundle/app.name),asset.name],cwd=bundle,capture_output=True,timeout=60)
    if child.returncode:raise RuntimeError('independent integer CUDA app failed')
    result=json.loads(child.stdout)
    if result!={'status':'pass','results':32,'guards':64}:raise RuntimeError('unexpected integer application results')
    if report['application_sha256']!=original or (bundle/asset.name).read_bytes()!=asset.read_bytes():raise RuntimeError('staging changed bytes')
    cli=subprocess.run([sys.executable,str(REPO/'scripts/ct.py'),'run','--ct-dll',str(REPO/'target/debug/ct_cuda.dll'),'--ptx',str(asset),str(app),'--',asset.name],cwd=REPO,capture_output=True,timeout=60)
    if cli.returncode:raise RuntimeError('public integer CLI consumer failed')
    lines=cli.stdout.splitlines();report=json.loads(lines[0])
    if report['application_sha256']!=original or report['assets_sha256']!=[asset_hash] or json.loads(lines[-1])!=result:raise RuntimeError('CLI byte/result mismatch')
    if digest(app.read_bytes())!=original:raise RuntimeError('original app changed')
    return dict(**result,application_sha256=original,asset_sha256=asset_hash,public_cli_passed=True,bytes_preserved=True)

def main(build=None):
    all_cases=cases();producer=Producer();baseline=REPO/'.cache/m3j-baseline/ct_cuda.dll'
    expected=(baseline.parent/'sha256.txt').read_text(encoding='utf-8-sig').strip().lower()
    if hashlib.sha256(baseline.read_bytes()).hexdigest()!=expected:raise RuntimeError('baseline hash mismatch')
    original=FIXTURE.read_bytes()
    if original!=source(fixture_cases()):raise RuntimeError('public fixture differs from independent generator')
    old=Device(baseline)
    try:
        code,handle=load_code(old,original)
        if code not in (218,801) or handle.value is not None:raise RuntimeError('baseline accepted integer extension')
    finally:old.close()
    cache=REPO/'.cache/reference/m3j';cache.mkdir(parents=True,exist_ok=True)
    asset=cache/'integer_bits.fatbin';asset.write_bytes(producer.make(original,'compressed',b'50'))
    device=Device();images=results=guards=0
    try:
        for seed in (0,1):
            for start in range(0,len(all_cases),24):
                batch=all_cases[start:start+24]
                for profile in (7,8):
                    raw=source(batch,seed,profile)
                    for image in (raw,producer.make(raw,'compressed',b'50' if profile==7 else b'52')):
                        try:execute(device,image,len(batch),seed)
                        except RuntimeError as error:
                            (cache/'failed-probe.ptx').write_bytes(raw)
                            raise RuntimeError(f'integer probe seed={seed} offset={start} profile={profile}: {error}') from None
                        images+=1;results+=len(batch);guards+=64
        invalid=[original.replace(b'cvt.s32.s32',b'cvt.sat.s32.s32',1),original.replace(b'shl.b64 %d3, %d1, %r2',b'shl.b64 %d3, %d1, %d1',1)]
        for image in invalid:
            code,handle=load_code(device,image)
            if code not in (218,801) or handle.value is not None:raise RuntimeError('invalid integer input accepted')
        execute(device,asset.read_bytes(),32,0)
    finally:device.close()
    report=dict(status='pass',operations=32,oracle_cases=len(all_cases),seeds=2,images=images,results=results,guards=guards,negative_cases=len(invalid),recovery_passed=True,baseline_rejected=True)
    if build:report['independent_application']=application_check(build,asset)
    print(json.dumps(report))

if __name__=='__main__':main(sys.argv[1] if len(sys.argv)>1 else None)
