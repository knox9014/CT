"""Independent CPU coordinate oracle for bounded multidimensional CUDA launches."""
import ctypes as c
import hashlib
import itertools
import json
import math
from pathlib import Path
import subprocess
import sys

from m3c_gpu_validation import Device, P, U32, U64, REPO
from m3d_fatbin_check import Producer
from m3f_selection_check import load_code
from m3g_modules_check import module, function

FIXTURE = REPO / 'tests/fixtures/multidimensional.ptx'
GUARD = 64
SENTINEL = -12345.25
SHAPES = [((1,1,1),(1,1,1)), ((3,5,1),(4,3,1)), ((2,3,4),(3,2,2)),
          ((1,3,2),(1,5,3)), ((3,1,2),(5,1,3)), ((2,3,1),(3,2,1)),
          ((3,2,5),(2,3,2)), ((2,3,4),(3,2,2))]


def arguments(values):
    return (P * len(values))(*(c.cast(c.pointer(v), P) for v in values))


def allocate(device, array):
    address = U64()
    device.call('cuMemAlloc_v2', c.byref(address), c.sizeof(array))
    device.call('cuMemcpyHtoD_v2', address, c.cast(array,P), c.sizeof(array))
    return address


def run_coordinates(device, handle, grid, block):
    extents = tuple(g*b for g,b in zip(grid,block))
    count = math.prod(extents) * 12
    lookup = (c.c_float * (max(*grid,*block)+1))(*(i*.25+1 for i in range(max(*grid,*block)+1)))
    output = (c.c_float * (count+GUARD))(*([float('nan')]*count+[SENTINEL]*GUARD))
    pointers = []
    try:
        pointers = [allocate(device, output), allocate(device, lookup)]
        args = arguments(pointers)
        device.call('cuLaunchKernel', handle, *grid, *block, 0, None, args, None)
        device.call('cuMemcpyDtoH_v2', c.cast(output,P), pointers[0], c.sizeof(output))
        # Enumerate CUDA block/thread coordinates independently of the PTX's
        # global-coordinate index calculation; x varies fastest in each record.
        for bz,by,bx in itertools.product(range(grid[2]),range(grid[1]),range(grid[0])):
            for tz,ty,tx in itertools.product(range(block[2]),range(block[1]),range(block[0])):
                x,y,z = bx*block[0]+tx, by*block[1]+ty, bz*block[2]+tz
                offset = (z*extents[1]*extents[0]+y*extents[0]+x)*12
                expected = (tx,ty,tz,*block,bx,by,bz,*grid)
                for component,value in enumerate(expected):
                    if output[offset+component] != value*.25+1:
                        raise RuntimeError('coordinate mapping mismatch or missing write')
        if any(v != SENTINEL for v in output[count:]): raise RuntimeError('coordinate output guard modified')
    finally:
        for address in pointers: device.call('cuMemFree_v2', address)
    return count


def run_matrix(device, handle, dims, block):
    count = math.prod(dims)
    grid = tuple((d+b-1)//b for d,b in zip(dims,block))
    left = (c.c_float*count)(*(i*.25 for i in range(count)))
    right = (c.c_float*count)(*(-i*.125 for i in range(count)))
    # Entire padded dispatch volume is retained and guarded, beyond logical N.
    padding = max(GUARD, math.prod(g*b for g,b in zip(grid,block))-count+GUARD)
    output = (c.c_float*(count+padding))(*([float('nan')]*count+[SENTINEL]*padding))
    pointers = []
    try:
        for array in (left,right,output): pointers.append(allocate(device,array))
        values = [*pointers,*(U32(d) for d in dims)]
        args = arguments(values)
        device.call('cuLaunchKernel', handle, *grid, *block, 0, None, args, None)
        device.call('cuMemcpyDtoH_v2', c.cast(output,P), pointers[2], c.sizeof(output))
        if any(output[i] != left[i]+right[i] for i in range(count)): raise RuntimeError('matrix mismatch or missing write')
        if any(v != SENTINEL for v in output[count:]): raise RuntimeError('matrix padding modified')
    finally:
        for address in pointers: device.call('cuMemFree_v2', address)
    return count,padding


def rejected_launches(device, handle):
    caps=[]
    for attribute in range(1,8):
        value=c.c_int();device.call('cuDeviceGetAttribute',c.byref(value),attribute,0)
        if value.value<=0: raise RuntimeError('nonpositive advertised dimension cap')
        caps.append(value.value)
    output=(c.c_float*64)(*([SENTINEL]*64));lookup=(c.c_float*4)(1,1.25,1.5,1.75)
    pointers=[];cases=[]
    for axis in range(3):
        for bad in (0,caps[axis+4]+1):
            grid=[1]*3;grid[axis]=bad;cases.append((grid,[1]*3))
        for bad in (0,caps[axis+1]+1):
            block=[1]*3;block[axis]=bad;cases.append(([1]*3,block))
        grid=[1]*3;grid[axis]=caps[axis+4]
        block=[1]*3;block[axis]=3
        if grid[axis]*3>0xffffffff: cases.append((grid,block))
    cases.append(([1]*3,caps[1:4]))
    try:
        pointers=[allocate(device,output),allocate(device,lookup)];args=arguments(pointers)
        for grid,block in cases:
            # Exercise malformed arguments too; identical error codes alone do
            # not establish validation precedence.
            for params in (args,None):
                code=device.dll.cuLaunchKernel(handle,*grid,*block,0,None,params,None)
                if code!=1: raise RuntimeError('invalid dimension was not rejected with INVALID_VALUE')
            device.call('cuMemcpyDtoH_v2',c.cast(output,P),pointers[0],c.sizeof(output))
            if any(v!=SENTINEL for v in output): raise RuntimeError('invalid launch changed output')
        for shared,stream,extra in [(1,None,None),(0,P(1),None),(0,None,args)]:
            if device.dll.cuLaunchKernel(handle,1,1,1,1,1,1,shared,stream,args,extra)!=801:
                raise RuntimeError('unsupported launch option accepted')
    finally:
        for address in pointers:device.call('cuMemFree_v2',address)
    run_coordinates(device,handle,(2,3,2),(3,2,2))
    return dict(invalid_shapes=len(cases),invalid_calls=len(cases)*2,unsupported_options=3,limits=caps)


def application_check(build,asset):
    sys.path.insert(0,str(REPO/'scripts'))
    from ct import digest,prepare_bundle
    folder=(REPO/build).resolve()
    if not folder.is_relative_to(REPO/'.cache/m3h-build'): raise RuntimeError('unexpected application build directory')
    app=folder/'m3h_cuda_app.exe';original=digest(app.read_bytes());asset_hash=digest(asset.read_bytes())
    bundle,report=prepare_bundle(app,REPO/'target/debug/ct_cuda.dll',[asset],REPO/'.cache/runs')
    child=subprocess.run([str(bundle/app.name),asset.name],cwd=bundle,capture_output=True,timeout=60)
    if child.returncode:raise RuntimeError('independent dimension consumer failed')
    result=json.loads(child.stdout)
    if result!={'status':'pass','results':936,'guards':632}:raise RuntimeError('unexpected consumer results')
    if report['application_sha256']!=original or (bundle/asset.name).read_bytes()!=asset.read_bytes():raise RuntimeError('staging changed bytes')
    cli=subprocess.run([sys.executable,str(REPO/'scripts/ct.py'),'run','--ct-dll',str(REPO/'target/debug/ct_cuda.dll'),'--ptx',str(asset),str(app),'--',asset.name],cwd=REPO,capture_output=True,timeout=60)
    if cli.returncode:raise RuntimeError('public CLI dimension consumer failed')
    lines=cli.stdout.splitlines();report=json.loads(lines[0])
    if report['application_sha256']!=original or report['assets_sha256']!=[asset_hash] or json.loads(lines[-1])!=result:raise RuntimeError('CLI bytes/results mismatch')
    if digest(app.read_bytes())!=original:raise RuntimeError('original application changed')
    return dict(**result,application_sha256=original,asset_sha256=asset_hash,public_cli_passed=True,bytes_preserved=True)


def main(build=None):
    source=FIXTURE.read_bytes();producer=Producer()
    cache=REPO/'.cache/reference/m3h';cache.mkdir(parents=True,exist_ok=True)
    asset=cache/'multidimensional.fatbin';asset.write_bytes(producer.make(source,'compressed',b'50'))
    baseline=REPO/'.cache/m3h-baseline/ct_cuda.dll'
    expected=(baseline.parent/'sha256.txt').read_text(encoding='utf-8-sig').strip().lower()
    if hashlib.sha256(baseline.read_bytes()).hexdigest()!=expected:raise RuntimeError('baseline hash mismatch')
    old=Device(baseline)
    try:
        code,handle=load_code(old,source)
        if code not in (218,801) or handle.value is not None:raise RuntimeError('baseline accepted multidimensional PTX')
    finally:old.close()
    device=Device();cases=outputs=guards=0
    try:
        for image in (source,asset.read_bytes()):
            owner=module(device,image)
            try:
                coords=function(device,owner,'coordinates');matrix=function(device,owner,'matrix_add')
                for grid,block in SHAPES:
                    outputs+=run_coordinates(device,coords,grid,block);guards+=GUARD;cases+=1
                for dims,block in [((1,1,1),(1,1,1)),((17,13,1),(4,3,1)),((13,11,5),(4,3,2)),((65,7,3),(8,2,2)),((3,19,7),(1,4,3))]:
                    count,padding=run_matrix(device,matrix,dims,block)
                    outputs+=count;guards+=padding;cases+=1
                rejected=rejected_launches(device,coords)
            finally:device.call('cuModuleUnload',owner)
    finally:device.close()
    report=dict(status='pass',cases=cases,results=outputs,guards=guards,rejection=rejected,baseline_rejected=True)
    if build:report['independent_application']=application_check(build,asset)
    print(json.dumps(report))


if __name__=='__main__':main(sys.argv[1] if len(sys.argv)>1 else None)
