"""R1a closed breadth jobs: exact dyadic mixed, asymmetric and cancelling inputs."""
import hashlib
import re
import struct
from pathlib import Path
from matrix_kernel_check import CASES as BASELINE_CASES
CASES=BASELINE_CASES+((32,32,96,64),(32,96,32,64),(32,64,128,32))
SEEDS=(193,194,195,296,297,298)
JOB_SCHEMA=2
GUARDS=16
GUARD=0xdeadbeef
NAN=0x7fc00000
ORIGINAL_PTX_SHA256='999de47c5a9d2610641f37fd5a949523d3e29c3b6c257d5dff7f65e9359ec07b'
def geometry(case):
    if type(case) not in (tuple,list) or len(case)!=4 or any(type(v) is not int for v in case) or tuple(case) not in CASES:raise ValueError('unqualified matrix geometry')
    tile,m,k,n=case
    return (n//tile,m//tile,1),(tile,tile,1)
def seed_value(seed):
    if type(seed) is not int or not 1<=seed<=1000000:raise ValueError('invalid matrix seed')
    return seed
def coefficients(seed,case):
    seed_value(seed);geometry(case);_,m,k,n=case
    if seed not in SEEDS:raise ValueError('unqualified breadth seed')
    if seed%3==0:
        return ([((seed*13+r*5+c*3)%17)-8 for r in range(m) for c in range(k)],
                [((seed*29+r*7-c*11)%19)-9 for r in range(k) for c in range(n)])
    if seed%3==1:
        return ([((seed+r*7+c*c)%13)-6 for r in range(m) for c in range(k)],
                [((seed*3+r*r-c*5)%19)-9 for r in range(k) for c in range(n)])
    # Adjacent K terms cancel exactly; magnitudes and rows remain nonuniform.
    return ([(-1 if c%2 else 1)*(1+(seed+r+c//2)%8) for r in range(m) for c in range(k)],
            [((seed+r//2*3+c*7)%19)-9 for r in range(k) for c in range(n)])
def dot_words(a,b,m,k,n):
    if any(type(v) is not int or not 1<=v<=128 for v in (m,k,n)) or len(a)!=m*k or len(b)!=k*n or any(type(v) is not int or abs(v)>9 for v in (*a,*b)):raise ValueError('unbounded exact matrix reference')
    return [struct.unpack('<I',struct.pack('<f',sum(a[r*k+j]*b[j*n+c] for j in range(k))/128))[0] for r in range(m) for c in range(n)]
def packet(words):return struct.pack('<'+'I'*(len(words)+2*GUARDS),*([GUARD]*GUARDS+list(words)+[GUARD]*GUARDS))
def input_parts(seed,case):
    a,b=coefficients(seed,case);_,m,k,n=case
    aw=[struct.unpack('<I',struct.pack('<f',v/8))[0] for v in a]
    bw=[struct.unpack('<I',struct.pack('<f',v/16))[0] for v in b]
    return dict(a=packet(aw),b=packet(bw),c=packet([NAN]*(m*n))),a,b
def input_buffers(seed,case):
    buffers,a,b=input_parts(seed,case);_,m,k,n=case
    return buffers,packet(dot_words(a,b,m,k,n))
def validate_case(seed,case,inputs,readbacks):
    wanted,output=input_buffers(seed,case)
    return (type(inputs) is dict and type(readbacks) is dict and set(inputs)==set(readbacks)=={'a','b','c'}
            and all(type(inputs[k]) is bytes and inputs[k]==v for k,v in wanted.items())
            and all(type(readbacks[k]) is bytes and readbacks[k]==v for k,v in dict(a=wanted['a'],b=wanted['b'],c=output).items()))
def exact(a,b):
    if type(a) is not type(b):return False
    if type(b) is dict:return set(a)==set(b) and all(exact(a[k],v) for k,v in b.items())
    if type(b) is list:return len(a)==len(b) and all(exact(x,y) for x,y in zip(a,b))
    return a==b
def validate_report(value,seed):
    if type(value) is not dict or type(value.get('adapter')) is not str or not 1<=len(value['adapter'])<=255 or '\0' in value['adapter']:return False
    try:seed_value(seed);preflight(value.get('limits'))
    except ValueError:return False
    wanted=dict(status='completed',seed=seed,adapter=value['adapter'],limits=value['limits'],
                cases=[dict(case=list(case),grid=list(geometry(case)[0]),block=list(geometry(case)[1]),output_words=case[1]*case[3]) for case in CASES],cleanup='pass')
    return exact(value,wanted)
def omission_matches(mode,inputs,readbacks):
    if type(inputs) is not dict or type(readbacks) is not dict or set(inputs)!=set(readbacks) or set(inputs)!={'a','b','c'}:return False
    if any(type(readbacks[k]) is not bytes or len(readbacks[k])!=len(v) for k,v in inputs.items()):return False
    if mode=='noop_launch':return readbacks==inputs
    if mode=='noop_copy':
        if any(readbacks[k]!=struct.pack('<I',NAN)*(len(inputs[k])//4) for k in ('a','b')):return False
        return all(word&0x7f800000==0x7f800000 and word&0x7fffff!=0 for word, in struct.iter_unpack('<I',readbacks['c']))
    return False
def entry_map(data):
    if hashlib.sha256(data).hexdigest()!=ORIGINAL_PTX_SHA256:raise ValueError('original PTX identity differs')
    names=re.findall(rb'\.entry\s+([A-Za-z_$][\w$]*)\s*\(',data)
    expected={t:f'_Z13MatrixMulCUDAILi{t}EEvPfS0_S0_ii' for t in (16,32)}
    if len(names)!=2 or set(names)!={n.encode() for n in expected.values()}:raise ValueError('original matrix entry set differs')
    return expected
def preflight(limits):
    if type(limits) is not list or len(limits)!=7 or any(type(v) is not int or v<=0 for v in limits):raise ValueError('invalid matrix device limits')
    for case in CASES:
        grid,block=geometry(case)
        if block[0]*block[1]*block[2]>limits[0] or any(b>bound for b,bound in zip(block,limits[1:4])) or any(g>bound for g,bound in zip(grid,limits[4:])):raise ValueError('device cannot execute complete matrix profile')
def input_files(seed):
    result={}
    for i,case in enumerate(CASES):
        inputs,_,_=input_parts(seed,case)
        result.update({f'case-{i}-{k}.bin':v for k,v in inputs.items()})
    return result
def validate_job(job,folder):
    if type(job) is not dict or set(job)!={'schema_version','seed','files'} or type(job['schema_version']) is not int or job['schema_version']!=JOB_SCHEMA:raise ValueError('matrix job schema')
    seed_value(job['seed']);wanted=input_files(job['seed']);pins=job['files']
    required=set(wanted)|{'nvcuda.dll','matrix.ptx'}
    if type(pins) is not dict or set(pins) not in (required,required|{'ct_underlying.dll'}):raise ValueError('matrix job files')
    folder=Path(folder).resolve()
    for name,sha in pins.items():
        path=folder/name
        if type(sha) is not str or not re.fullmatch('[0-9a-f]{64}',sha) or not path.is_file() or not path.resolve().is_relative_to(folder) or hashlib.sha256(path.read_bytes()).hexdigest()!=sha:raise ValueError('matrix job artifact drift')
    for name,data in wanted.items():
        if (folder/name).read_bytes()!=data:raise ValueError('matrix input recipe differs')
    if any((folder/f'case-{i}-{k}-readback.bin').exists() for i in range(len(CASES)) for k in ('a','b','c')):raise ValueError('stale matrix readback')
    return entry_map((folder/'matrix.ptx').read_bytes())
