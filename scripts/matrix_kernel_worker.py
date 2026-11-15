"""Internal closed matrix Driver worker. Reports API completion, not correctness."""
import ctypes as c
import json
from pathlib import Path
import sys
from matrix_kernel_check import CASES,GUARDS,NAN,geometry,validate_job,preflight
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from m3c_gpu_validation import Device,P,U32,U64

def execute(job_path,*,breadth=False,rounding=False):
    if breadth and rounding:raise ValueError('conflicting matrix profiles')
    if rounding:
        import matrix_rounding_check as contract
    elif breadth:
        import matrix_breadth_check as contract
    else:
        import matrix_kernel_check as contract
    CASES,GUARDS,NAN,geometry,validate_job,preflight=(getattr(contract,n) for n in ('CASES','GUARDS','NAN','geometry','validate_job','preflight'))
    if sys.flags.optimize:raise ValueError('matrix checks require unoptimized Python')
    job_path=Path(job_path).resolve();folder=job_path.parent
    if Path.cwd().resolve()!=folder:raise ValueError('matrix bundle must be current directory')
    job=json.loads(job_path.read_bytes());entries=validate_job(job,folder)
    device=None;module=P();allocations=[];cleanup_errors=[];original=None;report=None
    try:
        device=Device(folder/'nvcuda.dll')
        device.dll.cuCtxSynchronize.argtypes=[];device.dll.cuCtxSynchronize.restype=c.c_int
        device.dll.cuMemsetD32_v2.argtypes=[U64,U32,c.c_size_t];device.dll.cuMemsetD32_v2.restype=c.c_int
        device.dll.cuDeviceGetName.argtypes=[P,c.c_int,c.c_int];device.dll.cuDeviceGetName.restype=c.c_int
        adapter=c.c_int();device.call('cuDeviceGet',c.byref(adapter),0)
        name=c.create_string_buffer(256);device.call('cuDeviceGetName',c.cast(name,P),len(name),adapter)
        limits=[]
        for attribute in range(1,8):
            value=c.c_int();device.call('cuDeviceGetAttribute',c.byref(value),attribute,adapter);limits.append(value.value)
        preflight(limits) # All four cases, including1024-thread groups, before first launch.
        ptx=c.create_string_buffer((folder/'matrix.ptx').read_bytes())
        device.call('cuModuleLoadData',c.byref(module),c.cast(ptx,P))
        rows=[]
        for index,case in enumerate(CASES):
            function=P();device.call('cuModuleGetFunction',c.byref(function),module,entries[case[0]].encode())
            buffers={k:(folder/f'case-{index}-{k}.bin').read_bytes() for k in ('a','b','c')}
            pointers={}
            for key,data in buffers.items():
                pointer=U64();device.call('cuMemAlloc_v2',c.byref(pointer),len(data));allocations.append(pointer)
                device.call('cuMemsetD32_v2',pointer,NAN,len(data)//4)
                host=c.create_string_buffer(data);device.call('cuMemcpyHtoD_v2',pointer,c.cast(host,P),len(data));pointers[key]=pointer
            # Keep argument values and their pointer array alive through explicit sync.
            values=[U64(pointers[k].value+GUARDS*4) for k in ('c','a','b')]+[c.c_int(case[2]),c.c_int(case[3])]
            arguments=(P*5)(*(c.cast(c.pointer(v),P) for v in values));grid,block=geometry(case)
            device.call('cuLaunchKernel',function,*grid,*block,0,None,arguments,None)
            device.call('cuCtxSynchronize')
            for key,data in buffers.items():
                host=c.create_string_buffer(len(data));device.call('cuMemcpyDtoH_v2',c.cast(host,P),pointers[key],len(data))
                (folder/f'case-{index}-{key}-readback.bin').write_bytes(host.raw)
            rows.append(dict(case=list(case),grid=list(grid),block=list(block),output_words=case[1]*case[3]))
        report=dict(status='completed',seed=job['seed'],adapter=name.value.decode('utf-8',errors='replace'),limits=limits,cases=rows,cleanup='pass')
    except BaseException as error:
        original=error
    finally:
        if device is not None:
            actions=([('cuModuleUnload',module)] if module.value else [])+[('cuMemFree_v2',pointer) for pointer in reversed(allocations)]+[('cuCtxDestroy_v2',device.context)]
            for action,value in actions:
                try:device.call(action,value)
                except BaseException as error:cleanup_errors.append(type(error).__name__)
    if original is not None:raise RuntimeError('matrix operation failed; cleanup_errors='+str(len(cleanup_errors))) from original
    if cleanup_errors:raise RuntimeError('matrix cleanup failed')
    return report

if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--breadth-v1':print(json.dumps(execute(sys.argv[2],breadth=True)))
    elif len(sys.argv)==3 and sys.argv[1]=='--rounding-v1':print(json.dumps(execute(sys.argv[2],rounding=True)))
    elif len(sys.argv)==2:print(json.dumps(execute(sys.argv[1])))
    else:raise SystemExit(40)
