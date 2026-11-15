"""External oracle for the closed, metadata-injected original matrix sample."""
import math
import struct

SHAPES=((32,32,32),(64,64,96)) # M,K,N; tile32, all dimensions divisible by32
SCOPE=dict(metadata_injected=True,production_compatible=False,release_claim=False,
           injected_compute_capability=[5,2])

def exact(a,b):
    if type(a) is not type(b):return False
    if isinstance(b,dict):return a.keys()==b.keys() and all(exact(a[k],v) for k,v in b.items())
    if isinstance(b,list):return len(a)==len(b) and all(exact(x,y) for x,y in zip(a,b))
    return a==b

def scope_valid(value):return exact(value,SCOPE)

def expected_output(shape):
    if shape not in SHAPES:raise ValueError('closed matrix shape')
    m,k,n=shape
    # Original A=1, B=binary32(0.01). Every FMA is therefore one rounded add.
    b=struct.unpack('<f',struct.pack('<f',0.01))[0];total=0.0
    for _ in range(k):total=struct.unpack('<f',struct.pack('<f',total+b))[0]
    return struct.pack('<f',total)*(m*n)

def buffers_valid(shape,a,b,c):
    if shape not in SHAPES:return False
    m,k,n=shape
    if a!=struct.pack('<f',1.0)*(m*k) or b!=struct.pack('<f',0.01)*(k*n):return False
    return len(c)==4*m*n and all(math.isfinite(v[0]) for v in struct.iter_unpack('<f',c)) and c==expected_output(shape)

def trace_valid(value,mode):
    if mode not in ('positive','noop_launch','noop_copy'):return False
    return exact(value,dict(allocations=3,h2d=2,dtoh=1,launches=301,
                           forwarded=0 if mode=='noop_launch' else 301,frees=3,
                           uploaded=0 if mode=='noop_copy' else 2,metadata_injected=True))
