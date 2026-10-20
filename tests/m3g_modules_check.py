"""Native multi-entry module/ABI/handle checks; all generated artifacts stay local."""
import ctypes as c
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from m3c_gpu_validation import Device, P, U32, U64, REPO
from m3d_fatbin_check import Producer
from m3f_selection_check import load_code

FIXTURE=REPO/'tests/fixtures/multi_entry.ptx'
NAMES=('kernel_add','kernel_sub','kernel_fill')


def module(device,image):
    code,handle=load_code(device,image)
    if code or handle.value is None: raise RuntimeError('multi-entry module load failed: '+str(code))
    return handle


def function(device,owner,name):
    output=P();device.call('cuModuleGetFunction',c.byref(output),owner,name.encode())
    return output


def empty_launch_code(device,handle):
    return device.dll.cuLaunchKernel(handle,1,1,1,64,1,1,0,None,None,None)


def run_loaded(device,handle,n,operation):
    left=(c.c_float*n)(*(i*.25 for i in range(n)))
    right=(c.c_float*n)(*(-i*.125 for i in range(n)))
    output=(c.c_float*(n+64))(*([float('nan')]*n+[-12345.25]*64))
    pointers=[]
    try:
        for array in (left,right,output):
            address=U64();device.call('cuMemAlloc_v2',c.byref(address),c.sizeof(array));pointers.append(address)
            device.call('cuMemcpyHtoD_v2',address,c.cast(array,P),c.sizeof(array))
        count=U32(n);value=c.c_float(3.25)
        values=(pointers[2],value,count) if operation=='fill' else (*pointers,count)
        args=(P*len(values))(*(c.cast(c.pointer(v),P) for v in values))
        device.call('cuLaunchKernel',handle,(n+63)//64,1,1,64,1,1,0,None,args,None)
        device.call('cuMemcpyDtoH_v2',c.cast(output,P),pointers[2],c.sizeof(output))
        for i in range(n):
            expected=3.25 if operation=='fill' else (left[i]-right[i] if operation=='sub' else left[i]+right[i])
            if output[i]!=expected: raise RuntimeError('multi-entry output mismatch or missing write')
        if any(output[i]!=-12345.25 for i in range(n,n+64)): raise RuntimeError('multi-entry guard modified')
    finally:
        for address in pointers: device.call('cuMemFree_v2',address)


def reordered(source,reverse):
    parts=source.split('.visible .entry ')
    bodies=parts[1:]
    if reverse:bodies.reverse()
    return (parts[0]+''.join('.visible .entry '+body for body in bodies)).encode()


def application_check(build,asset):
    sys.path.insert(0,str(REPO/'scripts'))
    from ct import digest,prepare_bundle
    folder=(REPO/build).resolve()
    if not folder.is_relative_to(REPO/'.cache/m3g-build'): raise RuntimeError('unexpected native test build directory')
    app=folder/'m3g_cuda_app.exe';original=digest(app.read_bytes());input_hash=digest(asset.read_bytes())
    bundle,report=prepare_bundle(app,REPO/'target/debug/ct_cuda.dll',[asset],REPO/'.cache/runs')
    child=subprocess.run([str(bundle/app.name),asset.name],cwd=bundle,capture_output=True,timeout=60)
    if child.returncode: raise RuntimeError('independent CUDA consumer failed')
    result=json.loads(child.stdout)
    if result!={'status':'pass','entries':3,'results':1028,'guards':256}: raise RuntimeError('unexpected independent CUDA consumer result')
    if report['application_sha256']!=original or (bundle/asset.name).read_bytes()!=asset.read_bytes(): raise RuntimeError('independent consumer staging changed bytes')
    cli=subprocess.run([sys.executable,str(REPO/'scripts/ct.py'),'run','--ct-dll',str(REPO/'target/debug/ct_cuda.dll'),
        '--ptx',str(asset),str(app),'--',asset.name],cwd=REPO,capture_output=True,timeout=60)
    if cli.returncode: raise RuntimeError('public CLI multi-entry consumer failed')
    lines=cli.stdout.splitlines();cli_report=json.loads(lines[0]);cli_result=json.loads(lines[-1])
    if cli_report['application_sha256']!=original or cli_report['assets_sha256']!=[input_hash] or cli_result!=result:
        raise RuntimeError('public CLI multi-entry preservation/result mismatch')
    if digest(app.read_bytes())!=original:raise RuntimeError('original consumer changed')
    return dict(**result,application_sha256=original,asset_sha256=input_hash,public_cli_passed=True,bytes_preserved=True)


def main(build=None,application_only=False):
    text=FIXTURE.read_text(encoding='utf-8');producer=Producer()
    cache=REPO/'.cache/reference/m3g';cache.mkdir(parents=True,exist_ok=True)
    asset=cache/'multi_entry.fatbin';asset.write_bytes(producer.make(text.encode(),'compressed',b'50'))
    if application_only:
        if build is None:raise RuntimeError('application-only check requires native build directory')
        print(json.dumps(dict(status='pass',scope='application',independent_application=application_check(build,asset))))
        return
    baseline=REPO/'.cache/m3g-baseline/ct_cuda.dll'
    expected=(baseline.parent/'sha256.txt').read_text(encoding='utf-8-sig').strip().lower()
    if hashlib.sha256(baseline.read_bytes()).hexdigest()!=expected:raise RuntimeError('baseline hash mismatch')
    old=Device(baseline)
    try:
        code,handle=load_code(old,text.encode())
        if code not in (218,801) or handle.value is not None: raise RuntimeError('baseline did not reject multi-entry input')
    finally:old.close()
    device=Device();closed=False;cases=outputs=guards=0;images=0
    try:
        for reverse in (False,True):
            raw=reordered(text,reverse)
            upper=reordered(text,not reverse).replace(b'.version 7.0',b'.version 8.0').replace(b'sm_50',b'sm_52').replace(b'add.rn.f32',b'sub.rn.f32')
            entries=[(raw,b'50'),(upper,b'52')]
            if reverse:entries.reverse()
            variants=[('raw',raw),('plain',producer.make(raw,'plain',b'50')),('compressed',producer.make(raw,'compressed',b'50')),
                      ('alternatives',producer.make_many(entries,True))]
            for variant,image in variants:
                images+=1;(cache/(variant+f'-{int(reverse)}.fatbin')).write_bytes(image)
                owner=module(device,image)
                try:
                    handles=[function(device,owner,name) for name in NAMES]
                    for n in (1,63,64,65,257,50000):
                        for index,handle in enumerate(handles):
                            operation=('sub' if variant=='alternatives' else 'add') if index==0 else ('sub' if index==1 else 'fill')
                            run_loaded(device,handle,n,operation);cases+=1;outputs+=n;guards+=64
                finally:device.call('cuModuleUnload',owner)
                if any(empty_launch_code(device,h)!=400 for h in handles):raise RuntimeError('unload did not invalidate every function')
        owner=module(device,text.encode());handles=[function(device,owner,name) for name in NAMES]
        duplicate=function(device,owner,NAMES[0]);run_loaded(device,duplicate,65,'add')
        missing=P(1)
        if device.dll.cuModuleGetFunction(c.byref(missing),owner,b'missing')!=500 or missing.value is not None:raise RuntimeError('missing entry output/error mismatch')
        if empty_launch_code(device,handles[2])!=1:raise RuntimeError('entry-local parameters not required')
        other=module(device,text.replace('add.rn.f32','sub.rn.f32').encode())
        other_function=function(device,other,NAMES[0]);run_loaded(device,other_function,65,'sub');run_loaded(device,handles[0],65,'add')
        device.call('cuModuleUnload',other)
        if empty_launch_code(device,other_function)!=400:raise RuntimeError('other module handle stayed valid')
        run_loaded(device,handles[0],65,'add')
        foreign=P();device.call('cuCtxCreate_v2',c.byref(foreign),0,0)
        try:
            if empty_launch_code(device,handles[0])!=400:raise RuntimeError('foreign context accepted function')
            output=P(1)
            if device.dll.cuModuleGetFunction(c.byref(output),owner,NAMES[0].encode())!=400 or output.value is not None:raise RuntimeError('foreign context accepted module')
            if device.dll.cuModuleUnload(owner)!=400:raise RuntimeError('foreign unload accepted module')
        finally:device.call('cuCtxDestroy_v2',foreign)
        negatives=[(text+text[text.index('.visible'):],218),(text[:-2],218),
                   (text.replace('ld.param.f32 %f0, [value];','bar.sync 0; ld.param.f32 %f0, [value];'),801)]
        for invalid,expected_code in negatives:
            code,out=load_code(device,invalid.encode())
            if code!=expected_code or out.value is not None:raise RuntimeError('invalid later entry accepted')
        run_loaded(device,handles[0],65,'add')
        for _ in range(100):run_loaded(device,handles[2],65,'fill')
        for _ in range(1000):
            cycle=module(device,text.encode());last=[function(device,cycle,name) for name in NAMES]
            device.call('cuModuleUnload',cycle)
        if any(empty_launch_code(device,h)!=400 for h in last):raise RuntimeError('cycled handles remained valid')
        header=text[:text.index('.visible')]
        limit=module(device,(header+''.join(f'.visible .entry empty_{i}() {{ ret; }}\n' for i in range(32))).encode())
        for i in range(32):function(device,limit,f'empty_{i}')
        device.call('cuLaunchKernel',function(device,limit,'empty_31'),1,1,1,1,1,1,0,None,None,None)
        device.call('cuModuleUnload',limit)
        device.close();closed=True
        fresh=Device()
        try:
            if empty_launch_code(fresh,duplicate)!=400:raise RuntimeError('destroyed context function stayed valid')
            output=P(1)
            if fresh.dll.cuModuleGetFunction(c.byref(output),owner,NAMES[0].encode())!=400 or output.value is not None:raise RuntimeError('destroyed context module stayed valid')
        finally:fresh.close()
        if (cases,outputs,guards)!=(144,1210800,9216):raise RuntimeError('unexpected multi-entry totals')
    finally:
        if not closed:device.close()
    report=dict(status='pass',formats=4,images=images,entries=3,cases=cases,results=outputs,guards=guards,
        baseline_rejected=True,entry_limit32_passed=True,duplicate_lookup_passed=True,isolated_modules_passed=True,
        context_lifetime_passed=True,negative_later_entries=3,recovery_passed=True,repeated_kernel_cases=100,
        repeated_results=6500,repeated_guards=6400,module_cycles=1000)
    if build:report['independent_application']=application_check(build,asset)
    print(json.dumps(report))


if __name__=='__main__':
    try:main(sys.argv[1] if len(sys.argv)>1 else None,'--application-only' in sys.argv[2:])
    except (RuntimeError,OSError,subprocess.SubprocessError) as error:
        print(json.dumps(dict(status='error',reason=str(error) if isinstance(error,RuntimeError) else 'local multi-entry test operation failed')))
        raise SystemExit(1)
