"""Direct CT Driver global checks; requires a real Intel GPU and explicit DLL."""
import argparse
import ctypes as c
import json
from pathlib import Path

P=c.c_void_p
U=c.c_uint64
N=c.c_size_t
SOURCE=b""".version 8.0
.target sm_52
.address_size 64
.global .align 4 .u32 counter=7;
.global .align 4 .u32 zero;
.global .align 8 .b8 legacy[16];
.visible .entry step(.param .u64 .ptr .global .align 4 output) {
.reg .u64 %rd; .reg .u32 %r;
ld.param.u64 %rd,[output];
ld.volatile.global.u32 %r,[counter];
st.global.u32 [%rd],%r;
add.u32 %r,%r,1;
st.volatile.global.u32 [counter],%r;
ret;
}
"""

class Driver:
    def __init__(self, dll):
        self.dll=c.WinDLL(str(dll.resolve()), winmode=0x1100)
        signatures={
            'cuInit':[c.c_uint], 'cuDeviceGet':[c.POINTER(c.c_int), c.c_int],
            'cuCtxCreate_v2':[c.POINTER(P),c.c_uint,c.c_int], 'cuCtxDestroy_v2':[P], 'cuCtxSetCurrent':[P],
            'cuModuleLoadData':[c.POINTER(P),P], 'cuModuleUnload':[P],
            'cuModuleGetGlobal_v2':[c.POINTER(U),c.POINTER(N),P,c.c_char_p],
            'cuModuleGetFunction':[c.POINTER(P),P,c.c_char_p],
            'cuMemAlloc_v2':[c.POINTER(U),N], 'cuMemFree_v2':[U],
            'cuMemcpyHtoD_v2':[U,P,N], 'cuMemcpyDtoH_v2':[P,U,N], 'cuMemcpyDtoD_v2':[U,U,N],
            'cuMemsetD32_v2':[U,c.c_uint,N], 'cuMemGetAddressRange_v2':[c.POINTER(U),c.POINTER(N),U],
            'cuPointerGetAttribute':[P,c.c_int,U],
            'cuLaunchKernel':[P,c.c_uint,c.c_uint,c.c_uint,c.c_uint,c.c_uint,c.c_uint,c.c_uint,P,c.POINTER(P),c.POINTER(P)],
        }
        for name, args in signatures.items():
            f=getattr(self.dll,name); f.argtypes=args; f.restype=c.c_int
    def call(self,name,*args,expected=0):
        actual=getattr(self.dll,name)(*args)
        if actual!=expected: raise ValueError(name+' returned unexpected CUDA result')
    def module(self):
        m=P(); image=c.create_string_buffer(SOURCE); self.call('cuModuleLoadData',c.byref(m),image); return m
    def global_(self,m,name=b'counter'):
        p=U(); n=N(); self.call('cuModuleGetGlobal_v2',c.byref(p),c.byref(n),m,name)
        if n.value!=4 or not p.value or p.value%4: raise ValueError('global extent')
        return p.value
    def read(self,p):
        value=c.c_uint(); self.call('cuMemcpyDtoH_v2',c.byref(value),p,4); return value.value
    def write(self,p,value):
        data=c.c_uint(value); self.call('cuMemcpyHtoD_v2',p,c.byref(data),4)


def observe(dll, cycles=1000):
    d=Driver(dll); d.call('cuInit',0)
    dev=c.c_int(); d.call('cuDeviceGet',c.byref(dev),0)
    ctx=P(); d.call('cuCtxCreate_v2',c.byref(ctx),0,dev)
    first=d.module(); second=d.module(); a=d.global_(first); b=d.global_(second)
    if a==b or (d.read(a),d.read(b),d.read(d.global_(first,b'zero')))!=(7,7,0): raise ValueError('module initial state')
    n=N(99); p=U(99)
    d.call('cuModuleGetGlobal_v2',None,c.byref(n),first,b'counter')
    d.call('cuModuleGetGlobal_v2',c.byref(p),None,first,b'counter')
    if (n.value,p.value)!=(4,a): raise ValueError('nullable outputs')
    for name, expected in [(b'missing',500),(b'legacy',801),(b'',1),(b'x'*129,1)]:
        p.value=99; n.value=99
        d.call('cuModuleGetGlobal_v2',c.byref(p),c.byref(n),first,name,expected=expected)
        if (p.value,n.value)!=(0,0): raise ValueError('output reset')
    d.call('cuModuleGetGlobal_v2',None,None,first,b'counter',expected=1)
    d.call('cuModuleGetGlobal_v2',None,None,P(123),None,expected=400)
    data=c.c_uint(99); base=U(99); size=N(99)
    d.call('cuMemGetAddressRange_v2',c.byref(base),c.byref(size),a,expected=801)
    d.call('cuPointerGetAttribute',c.byref(data),8,a,expected=801)
    if (base.value,size.value,data.value)!=(99,99,99): raise ValueError('query outputs changed')
    d.call('cuMemFree_v2',a,expected=1)
    d.call('cuMemcpyDtoH_v2',c.byref(data),max(a,b,d.global_(first,b'zero'),d.global_(second,b'zero'))+4,0,expected=1)
    d.call('cuMemcpyDtoH_v2',c.byref(data),a,5,expected=1)
    d.write(a,123); d.call('cuMemcpyDtoD_v2',b,a,4)
    if d.read(b)!=123: raise ValueError('device copy')
    d.call('cuMemsetD32_v2',b,55,1)
    if d.read(b)!=55 or d.read(a)!=123: raise ValueError('module write isolation')
    output=U(); d.call('cuMemAlloc_v2',c.byref(output),4)
    f=P(); d.call('cuModuleGetFunction',c.byref(f),first,b'step')
    ptr=U(output.value); args=(P*1)(c.cast(c.byref(ptr),P))
    observed=[]
    for i in range(100):
        d.call('cuLaunchKernel',f,1,1,1,1,1,1,0,None,args,None)
        observed.append(d.read(output.value))
    if observed!=list(range(123,223)) or d.read(a)!=223 or d.read(b)!=55: raise ValueError('stored global kernel sequence')
    other=P(); d.call('cuCtxCreate_v2',c.byref(other),0,dev)
    d.call('cuModuleGetGlobal_v2',c.byref(p),c.byref(n),first,b'counter',expected=400)
    d.call('cuMemcpyDtoH_v2',c.byref(data),a,4,expected=1)
    third=d.module(); other_address=d.global_(third)
    if d.read(other_address)!=7: raise ValueError('context initialization')
    d.write(other_address,999)
    d.call('cuModuleUnload',third); d.call('cuCtxDestroy_v2',other)
    d.call('cuCtxSetCurrent',ctx)
    if d.read(a)!=223: raise ValueError('context isolation')
    d.call('cuMemFree_v2',output)
    d.call('cuModuleUnload',first)
    d.call('cuModuleGetGlobal_v2',c.byref(p),c.byref(n),first,b'counter',expected=400)
    d.call('cuMemcpyDtoH_v2',c.byref(data),a,4,expected=1)
    if d.read(b)!=55: raise ValueError('sibling after unload')
    d.call('cuModuleUnload',second)
    for _ in range(cycles):
        m=d.module(); g=d.global_(m)
        if d.read(g)!=7: raise ValueError('reload initialization')
        d.call('cuModuleUnload',m)
    d.call('cuCtxDestroy_v2',ctx)
    return dict(status='pass', scope='direct_driver_globals', ordered_calls=100, module_lifecycles=cycles, contexts=2)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--dll',type=Path,required=True)
    args=parser.parse_args()
    try: print(json.dumps(observe(args.dll)))
    except (OSError,ValueError,AttributeError): print(json.dumps(dict(status='fail',reason='global_driver_check_failed'))); raise SystemExit(1)
