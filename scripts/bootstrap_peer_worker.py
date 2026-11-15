"""Synthetic-only Runtime prefix; never CT/application compatibility evidence."""
import argparse
import ctypes as c
import json
from pathlib import Path
import os
import sys

class Row(c.Structure):
    _fields_=[('kind',c.c_uint32),('version',c.c_int32),('flags',c.c_uint64),('result',c.c_int32),
              ('status',c.c_int32),('found',c.c_int32),('value',c.c_int32),('symbol',c.c_ubyte*64),('uuid',c.c_ubyte*16)]

def direct_contract(peer,configure):
    checks=0
    def require(value):
        nonlocal checks
        if not value:raise ValueError('native peer contract mismatch')
        checks+=1
    require(configure(99,1)==1);require(configure(3,2)==1);require(configure(3,1)==0)
    require(configure(0,0)==801)
    version=peer.cuDriverGetVersion;version.argtypes=[c.POINTER(c.c_int)];version.restype=c.c_int
    value=c.c_int(-1);require(version(None)==1);require(version(c.byref(value))==0 and value.value==12000)
    init=peer.cuInit;init.argtypes=[c.c_uint];init.restype=c.c_int
    require(init(0)==801);require(init(1)==1)
    table=peer.cuGetExportTable;table.argtypes=[c.POINTER(c.c_void_p),c.c_void_p];table.restype=c.c_int
    output=c.c_void_p(0xDEAD);identity=(c.c_ubyte*16)(*[7]*16)
    require(table(c.byref(output),identity)==801 and output.value is None)
    require(table(c.byref(output),None)==1 and output.value is None)
    resolve2=peer.cuGetProcAddress_v2
    resolve2.argtypes=[c.c_char_p,c.POINTER(c.c_void_p),c.c_int,c.c_uint64,c.POINTER(c.c_int)];resolve2.restype=c.c_int
    status=c.c_int(-1)
    require(resolve2(b'cuInit',c.byref(output),12090,2,c.byref(status))==0 and output.value==c.cast(init,c.c_void_p).value and status.value==0)
    require(resolve2(b'cuLaunchKernel',c.byref(output),12000,0,c.byref(status))==0 and output.value is None and status.value==1)
    resolve1=peer.cuGetProcAddress;resolve1.argtypes=resolve2.argtypes[:4];resolve1.restype=c.c_int
    require(resolve1(b'cuLaunchKernel',c.byref(output),12000,0)==500 and output.value is None)
    require(resolve2(b'cuGetProcAddress',c.byref(output),11999,0,c.byref(status))==0 and output.value==c.cast(resolve1,c.c_void_p).value)
    require(resolve2(b'cuGetProcAddress',c.byref(output),12000,0,c.byref(status))==0 and output.value==c.cast(resolve2,c.c_void_p).value)
    require(resolve2(None,c.byref(output),12000,0,c.byref(status))==1 and output.value is None)
    for symbol in ['cuLaunchKernel','cuMemAlloc_v2','cuDeviceGetCount']:
        try:getattr(peer,symbol)
        except AttributeError:checks+=1
        else:raise ValueError('unexpected device/launch export')
    return checks

def main():
    p=argparse.ArgumentParser();p.add_argument('--mode',type=int,choices=range(5),required=True)
    p.add_argument('--trace',type=int,choices=(0,1),required=True);p.add_argument('--contract',action='store_true');args=p.parse_args()
    if not sys.flags.isolated or not sys.flags.no_site:raise ValueError('isolated no-site startup required')
    sys.path.append(str(Path(__file__).resolve().parent));sys.pycache_prefix=str(Path.cwd()/'pycache');sys.dont_write_bytecode=True
    from runtime_bootstrap_worker import require_loaded
    if c.sizeof(Row)!=112:raise ValueError('peer row ABI')
    bundle=Path.cwd();keep=[os.add_dll_directory(str(bundle))]
    peer=c.WinDLL(str(bundle/'nvcuda.dll'));keep.append(peer);provider_sha=require_loaded(peer,bundle/'nvcuda.dll')
    configure=peer.ctPeerConfigure;configure.argtypes=[c.c_uint32,c.c_uint32];configure.restype=c.c_int
    if args.contract:
        checks=direct_contract(peer,configure)
        print(json.dumps(dict(scope='synthetic_peer_contract',application_supported=False,checks=checks,provider_sha256=provider_sha)))
        return
    if configure(args.mode,args.trace)!=0:raise ValueError('peer configuration rejected')
    runtime=c.WinDLL(str(bundle/'cudart64_12.dll'));keep.append(runtime)
    runtime_sha=require_loaded(runtime,bundle/'cudart64_12.dll')
    count=c.c_int(-1);function=runtime.cudaGetDeviceCount;function.argtypes=[c.POINTER(c.c_int)];function.restype=c.c_int
    try:outcome=dict(status='returned',code=function(c.byref(count)),count=count.value)
    except OSError:outcome=dict(status='native_fault',code=None,count=count.value)
    snapshot=peer.ctPeerSnapshot;snapshot.argtypes=[c.POINTER(Row),c.c_uint32,c.POINTER(c.c_uint32),c.POINTER(c.c_uint32)];snapshot.restype=c.c_int
    rows=(Row*512)();length=c.c_uint32();overflow=c.c_uint32()
    if snapshot(rows,512,c.byref(length),c.byref(overflow))!=0 or length.value>512:raise ValueError('peer snapshot failed')
    trace=[dict(kind=r.kind,symbol=bytes(r.symbol).split(b'\0',1)[0].decode('ascii'),version=r.version,flags=r.flags,
                result=r.result,status=r.status,found=r.found,value=r.value,uuid=bytes(r.uuid).hex()) for r in rows[:length.value]]
    print(json.dumps(dict(scope='synthetic_intervention',application_supported=False,mode=args.mode,
                         trace_enabled=bool(args.trace),outcome=outcome,trace=trace,overflow=bool(overflow.value),
                         provider_sha256=provider_sha,runtime_sha256=runtime_sha)))

if __name__=='__main__':main()
