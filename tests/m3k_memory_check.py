"""Exact integer-buffer and scalar ABI checks on real CUDA/CT calls."""
import ctypes as c
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

from m3c_gpu_validation import Device,P,U32,U64,REPO
from m3d_fatbin_check import Producer
from m3f_selection_check import load_code
from m3g_modules_check import module,function

FIXTURE=REPO/'tests/fixtures/integer_memory.ptx'
SIZES=(1,63,64,65,257,50000)
VALUES=(0,1,0x80000000fedcba98,0xffffffffffffffff)

def args(values):return (P*len(values))(*(c.cast(c.pointer(v),P) for v in values))
def allocate(device,data):
    p=U64();device.call('cuMemAlloc_v2',c.byref(p),c.sizeof(data));device.call('cuMemcpyHtoD_v2',p,c.cast(data,P),c.sizeof(data));return p

def run(device,handle,width,n,value,fill=False,use_or=False,unaligned_host=False):
    kind=U64 if width==64 else U32;step=width//8;mask=(1<<width)-1;value&=mask
    sentinel=0xdeadbeefcafebabe&mask;total=n+129
    source=(kind*total)(*([sentinel]*total));output=(kind*total)(*([sentinel]*total))
    pattern=[0,1,(1<<(width-1))-1,1<<(width-1),mask,0xa5a5a5a5a5a5a5a5&mask]
    for i in range(n):source[65+i]=pattern[i] if i<len(pattern) else ((i*0x9e3779b97f4a7c15)^0x8000000000000042)&mask
    expected_values=[value if fill else (source[65+i]|value if use_or else source[65+i]^value) for i in range(n)]
    for i,expected in enumerate(expected_values):output[65+i]=expected^mask
    pointers=[]
    try:
        for array in (source,output):pointers.append(allocate(device,array))
        interior=[U64(p.value+64*step) for p in pointers]
        scalar=kind(value);count=U32(n)
        values=[interior[1],scalar,count] if fill else [*interior,scalar,count]
        arguments=args(values)
        if unaligned_host:
            raw=c.create_string_buffer(9);struct.pack_into('<Q',raw,1,value)
            arguments[1 if fill else 2]=P(c.addressof(raw)+1)
        device.call('cuLaunchKernel',handle,(n+63)//64,1,1,64,1,1,0,None,arguments,None)
        device.call('cuMemcpyDtoH_v2',c.cast(output,P),pointers[1],c.sizeof(output))
        for i in range(n):
            expected=expected_values[i]
            if output[65+i]!=expected:raise RuntimeError('integer array bit mismatch')
        if any(v!=sentinel for v in output[:65]) or any(v!=sentinel for v in output[65+n:]):raise RuntimeError('integer array prefix/suffix guard modified')
        copied=(kind*total)();device.call('cuMemcpyDtoH_v2',c.cast(copied,P),pointers[0],c.sizeof(copied))
        if bytes(copied)!=bytes(source):raise RuntimeError('read-only input modified')
    finally:
        for p in pointers:device.call('cuMemFree_v2',p)

def invalid_pointers(device,handle):
    output=(U64*16)(*([0xdeadbeefcafebabe]*16));owner=allocate(device,output);tiny=U64()
    device.call('cuMemAlloc_v2',c.byref(tiny),4)
    foreign=P();foreign_pointer=U64()
    device.dll.cuCtxSetCurrent.argtypes=[P];device.dll.cuCtxSetCurrent.restype=c.c_int
    try:
        device.call('cuCtxCreate_v2',c.byref(foreign),0,0)
        device.call('cuMemAlloc_v2',c.byref(foreign_pointer),128)
        device.call('cuCtxSetCurrent',device.context)
        # N=0 prevents a faulty rejection check from causing unsafe GPU access.
        count=U32(0);scalar=U64(0xffffffffffffffff)
        for pointer in (0,0x1000,owner.value+4,owner.value+c.sizeof(output),tiny.value,foreign_pointer.value):
            p=U64(pointer);arguments=args([p,scalar,count])
            if device.dll.cuLaunchKernel(handle,1,1,1,1,1,1,0,None,arguments,None)!=1:raise RuntimeError('invalid typed pointer not rejected')
        device.call('cuMemcpyDtoH_v2',c.cast(output,P),owner,c.sizeof(output))
        if any(v!=0xdeadbeefcafebabe for v in output):raise RuntimeError('rejected pointer changed output')
    finally:
        if foreign.value:
            device.call('cuCtxSetCurrent',foreign)
            if foreign_pointer.value:device.call('cuMemFree_v2',foreign_pointer)
            device.call('cuCtxDestroy_v2',foreign)
        device.call('cuCtxSetCurrent',device.context)
        device.call('cuMemFree_v2',tiny);device.call('cuMemFree_v2',owner)
    run(device,handle,64,65,0x80000000fedcba98,fill=True,unaligned_host=True)
    return 6

def application_check(build,asset):
    sys.path.insert(0,str(REPO/'scripts'))
    from ct import digest,prepare_bundle
    folder=(REPO/build).resolve()
    if not folder.is_relative_to(REPO/'.cache/m3k-build'):raise RuntimeError('unexpected app build directory')
    app=folder/'m3k_cuda_app.exe';original=digest(app.read_bytes());asset_hash=digest(asset.read_bytes())
    bundle,report=prepare_bundle(app,REPO/'target/debug/ct_cuda.dll',[asset],REPO/'.cache/runs')
    child=subprocess.run([str(bundle/app.name),asset.name],cwd=bundle,capture_output=True,timeout=60)
    if child.returncode:raise RuntimeError('independent typed memory consumer failed')
    result=json.loads(child.stdout)
    if result!={'status':'pass','results':771,'guards':387}:raise RuntimeError('unexpected typed consumer result')
    if report['application_sha256']!=original or (bundle/asset.name).read_bytes()!=asset.read_bytes():raise RuntimeError('staging changed input bytes')
    cli=subprocess.run([sys.executable,str(REPO/'scripts/ct.py'),'run','--ct-dll',str(REPO/'target/debug/ct_cuda.dll'),'--ptx',str(asset),str(app),'--',asset.name],cwd=REPO,capture_output=True,timeout=60)
    if cli.returncode:raise RuntimeError('public typed memory CLI failed')
    lines=cli.stdout.splitlines();report=json.loads(lines[0])
    if report['application_sha256']!=original or report['assets_sha256']!=[asset_hash] or json.loads(lines[-1])!=result:raise RuntimeError('CLI result/bytes mismatch')
    if digest(app.read_bytes())!=original:raise RuntimeError('original app changed')
    return dict(**result,application_sha256=original,asset_sha256=asset_hash,public_cli_passed=True,bytes_preserved=True)

def main(build=None):
    text=FIXTURE.read_bytes();producer=Producer();baseline=REPO/'.cache/m3k-baseline/ct_cuda.dll'
    expected=(baseline.parent/'sha256.txt').read_text(encoding='utf-8-sig').strip().lower()
    if hashlib.sha256(baseline.read_bytes()).hexdigest()!=expected:raise RuntimeError('baseline hash mismatch')
    old=Device(baseline)
    try:
        code,h=load_code(old,text)
        if code not in (218,801) or h.value is not None:raise RuntimeError('baseline accepted typed memory extension')
    finally:old.close()
    plain=text.replace(b'ld.global.u32',b'ld.global.s32').replace(b'ld.global.u64',b'ld.global.b64').replace(b'st.global.b32',b'st.global.u32').replace(b'st.global.b64',b'st.global.u64')
    upper=text.replace(b'.version 7.0',b'.version 8.0').replace(b'sm_50',b'sm_52').replace(b'xor.b',b'or.b').replace(b'ld.global.u32',b'ld.global.b32').replace(b'ld.global.u64',b'ld.global.s64').replace(b'st.global.b32',b'st.global.s32')
    cache=REPO/'.cache/reference/m3k';cache.mkdir(parents=True,exist_ok=True)
    asset=cache/'integer_memory.fatbin';asset.write_bytes(producer.make(text,'compressed',b'50'))
    variants=[('raw',text),('plain',producer.make(plain,'plain',b'50')),('compressed',asset.read_bytes()),('alternatives',producer.make_many([(upper,b'52'),(text,b'50')],True))]
    device=Device();cases=results=guards=0
    try:
        for variant,image in variants:
            owner=module(device,image)
            try:
                handles=[function(device,owner,name) for name in ('xor32','xor64','fill64')]
                for n in SIZES:
                    for value in VALUES:
                        for index,handle in enumerate(handles):
                            run(device,handle,32 if index==0 else 64,n,value,fill=index==2,use_or=variant=='alternatives')
                            cases+=1;results+=n;guards+=129
                invalid=invalid_pointers(device,handles[2])
            finally:device.call('cuModuleUnload',owner)
        for bad in [text.replace(b'.align 8',b'.align 4'),text.replace(b'.param .b64 mask',b'.param .u64 mask'),text.replace(b'%rd3+8',b'%rd3+4')]:
            code,h=load_code(device,bad)
            if code not in (218,801) or h.value is not None:raise RuntimeError('invalid typed source accepted')
        conflict=upper.replace(b'.align 4',b'.align 8')
        code,h=load_code(device,producer.make_many([(text,b'50'),(conflict,b'52')],True))
        if code!=801 or h.value is not None:raise RuntimeError('alternative pointer alignment conflict accepted')
        owner=module(device,text)
        try:run(device,function(device,owner,'fill64'),64,65,0,fill=True)
        finally:device.call('cuModuleUnload',owner)
    finally:device.close()
    report=dict(status='pass',formats=4,entries=3,cases=cases,results=results,guards=guards,invalid_pointer_cases_per_image=invalid,negative_sources=3,alignment_conflicts=1,recovery_passed=True,unaligned_host_scalar_passed=True,baseline_rejected=True)
    if build:report['independent_application']=application_check(build,asset)
    print(json.dumps(report))

if __name__=='__main__':main(sys.argv[1] if len(sys.argv)>1 else None)
