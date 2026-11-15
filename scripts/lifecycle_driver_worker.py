"""Isolated Driver module reuse; raw observations, not a numerical verdict."""
import ctypes as c
import json
from pathlib import Path
import struct
import sys
from lifecycle_check import closed,driver_header,driver_parts,NAN
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tests'))
from m3c_gpu_validation import Device,P,U32,U64

class ContractError(Exception):pass

def expected(code,wanted,reason):
    if code!=wanted:raise ContractError(reason)

def execute(seed,cycles):
    if sys.flags.optimize:raise ContractError('unoptimized_required')
    closed(seed,cycles,'driver');folder=Path.cwd();source_bytes=(folder/'vector.ptx').read_bytes()
    if source_bytes!=(ROOT/'tests/fixtures/vector_add.ptx').read_bytes():raise ContractError('ptx_identity')
    device=Device(folder/'nvcuda.dll')
    device.dll.cuMemsetD32_v2.argtypes=[U64,U32,c.c_size_t];device.dll.cuMemsetD32_v2.restype=c.c_int
    rows=[];stale=0;errors=0
    try:
        for index in range(cycles):
            module=P();pointers=[]
            try:
                source=c.create_string_buffer(source_bytes)
                device.call('cuModuleLoadData',c.byref(module),c.cast(source,P))
                function=P();expected(device.dll.cuModuleGetFunction(c.byref(function),module,b'missing_lifecycle'),500,'missing_function');errors+=1
                device.call('cuModuleGetFunction',c.byref(function),module,b'vector_add')
                parts=driver_parts(seed,index)[:3]
                for words in parts:
                    pointer=U64();data=struct.pack('<64I',*words)
                    device.call('cuMemAlloc_v2',c.byref(pointer),len(data));pointers.append(pointer)
                    device.call('cuMemsetD32_v2',pointer,NAN,64)
                    host=c.create_string_buffer(data);device.call('cuMemcpyHtoD_v2',pointer,c.cast(host,P),len(data))
                values=[U64(p.value+64) for p in pointers]+[U32(32)]
                args=(P*4)(*(c.cast(c.pointer(v),P) for v in values))
                device.call('cuLaunchKernel',function,1,1,1,64,1,1,0,None,args,None)
                device.call('cuCtxSynchronize')
                row=[]
                for pointer in pointers:
                    host=c.create_string_buffer(256);device.call('cuMemcpyDtoH_v2',c.cast(host,P),pointer,256)
                    row.extend(struct.unpack('<64I',host.raw))
                rows.append(row)
                old=P(module.value);device.call('cuModuleUnload',module);module=P()
                expected(device.dll.cuModuleUnload(old),400,'duplicate_unload');stale+=1
                expected(device.dll.cuLaunchKernel(function,1,1,1,64,1,1,0,None,None,None),400,'stale_function');stale+=1
                ignored=P();expected(device.dll.cuModuleGetFunction(c.byref(ignored),old,b'vector_add'),400,'stale_module');stale+=1
                while pointers:
                    pointer=pointers[-1];device.call('cuMemFree_v2',pointer);pointers.pop()
                    if not pointers:expected(device.dll.cuMemFree_v2(pointer),1,'duplicate_free');errors+=1
            finally:
                if module.value:device.call('cuModuleUnload',module)
                for pointer in reversed(pointers):device.call('cuMemFree_v2',pointer)
    finally:device.close()
    value=driver_header(seed,cycles);value.update(stale_checks=stale,recoverable_errors=errors,rows=rows)
    return value

if __name__=='__main__':
    try:
        if len(sys.argv)!=3:raise ContractError('arguments')
        print(json.dumps(execute(int(sys.argv[1]),int(sys.argv[2]))))
    except ContractError as error:
        print(json.dumps(dict(status='rejected',reason=str(error))));raise SystemExit(42)
