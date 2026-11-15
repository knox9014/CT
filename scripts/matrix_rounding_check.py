"""Closed decimal-input/FMA matrix contract; strict bits and exact real-dot bounds."""
import hashlib
import re
import struct
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
from fma_check import fused_bits
from matrix_kernel_check import packet,exact,entry_map,omission_matches,GUARDS,NAN

CASES=((16,16,16,16),(32,32,64,32))
SEEDS=(193,194,295,296)
JOB_SCHEMA=3

@lru_cache(maxsize=2048,typed=True)
def word_fraction(word):
    if type(word) is not int or not 0<=word<=0xffffffff or (word>>23)&255==255:raise ValueError('finite binary32 word required')
    exponent=(word>>23)&255;mantissa=(word&0x7fffff)|(0x800000 if exponent else 0)
    power=exponent-150 if exponent else -149
    value=Fraction(mantissa)*(Fraction(2)**power)
    return -value if word>>31 else value

@lru_cache(maxsize=2048,typed=True)
def round_fraction(value):
    if type(value) is not Fraction or abs(value)>512 or (value and abs(value)<Fraction(1,2**100)):raise ValueError('independent rounding outside closed normal range')
    if not value:return 0
    # Binary64 only locates neighbouring candidates. Exact rational distance and
    # significand parity make the final choice, including double-rounding ties.
    guess=struct.unpack('<I',struct.pack('<f',float(value)))[0]
    candidates=[w for w in range(max(0,guess-1),min(0xffffffff,guess+1)+1) if (w>>23)&255!=255]
    return min(candidates,key=lambda w:(abs(word_fraction(w)-value),w&1))

def seed_value(seed):
    if type(seed) is not int or seed not in SEEDS:raise ValueError('unqualified rounding seed')
    return seed

def geometry(case):
    if type(case) not in (tuple,list) or len(case)!=4 or any(type(v) is not int for v in case) or tuple(case) not in CASES:raise ValueError('unqualified rounding geometry')
    tile,m,k,n=case;return (n//tile,m//tile,1),(tile,tile,1)

def input_words(seed,case):
    seed_value(seed);geometry(case);return _input_words(seed,tuple(case))

@lru_cache(maxsize=8)
def _input_words(seed,case):
    _,m,k,n=case
    if seed%2==0:
        return (tuple(round_fraction(Fraction((seed+r*7+j*3)%29-14,20)) for r in range(m) for j in range(k)),
                tuple(round_fraction(Fraction((seed*3+j*11-col*5)%31-15,25)) for j in range(k) for col in range(n)))
    a=[];b=[]
    for r in range(m):
        sign=0x80000000 if (r+seed//2)%2 else 0
        a.extend([(0xbf800000^sign) if j==0 else (0x3f800001^sign) if j==1 else 0 for j in range(k)])
    for j in range(k):
        for col in range(n):
            sign=0x80000000 if (col+seed//3)%2 else 0
            b.append((0x3f800000^sign) if j==0 else (0x3f7ffffe^sign) if j==1 else round_fraction(Fraction((seed+j*7-col*3)%19-9,10)))
    return tuple(a),tuple(b)

def reference(seed,case):
    input_words(seed,case);return _reference(seed,tuple(case))

@lru_cache(maxsize=8)
def _reference(seed,case):
    _,m,k,n=case;a,b=input_words(seed,case);words=[]
    for r in range(m):
        for col in range(n):
            total=0
            for j in range(k):
                total=fused_bits(a[r*k+j],b[j*n+col],total)
                if (total is None or (total>>23)&255==255
                        or (total&0x7fffffff and not total&0x7f800000)):raise ValueError('reference outside closed normal/zero range')
            words.append(total)
    return tuple(words)

@lru_cache(maxsize=8)
def _ideal_bounds(seed,case):
    _,m,k,n=case;a,b=input_words(seed,case);values=[];gamma=Fraction(k,2**24-k)
    for r in range(m):
        for col in range(n):
            terms=[word_fraction(a[r*k+j])*word_fraction(b[j*n+col]) for j in range(k)]
            values.append((sum(terms,Fraction()),gamma*sum(map(abs,terms),Fraction())))
    return tuple(values)

def real_dot_bounds_valid(seed,case,words):
    input_words(seed,case)
    if type(words) not in (tuple,list) or len(words)!=case[1]*case[3]:return False
    try:return all(abs(word_fraction(w)-ideal)<=bound for w,(ideal,bound) in zip(words,_ideal_bounds(seed,tuple(case))))
    except ValueError:return False

def input_files(seed):
    return {f'case-{i}-{key}.bin':data for i,case in enumerate(CASES) for key,data in input_parts(seed,case).items()}

def input_parts(seed,case):
    a,b=input_words(seed,case)
    return dict(a=packet(a),b=packet(b),c=packet([NAN]*(case[1]*case[3])))

def input_buffers(seed,case):return input_parts(seed,case),packet(reference(seed,case))

def validate_case(seed,case,inputs,readbacks):
    wanted,output=input_buffers(seed,case)
    return (type(inputs) is dict and type(readbacks) is dict and set(inputs)==set(readbacks)=={'a','b','c'}
        and all(type(inputs[k]) is bytes and inputs[k]==v for k,v in wanted.items())
        and all(type(readbacks[k]) is bytes and readbacks[k]==v for k,v in dict(wanted,c=output).items())
        and real_dot_bounds_valid(seed,case,reference(seed,case)))

def preflight(limits):
    if type(limits) is not list or len(limits)!=7 or any(type(v) is not int or v<=0 for v in limits):raise ValueError('invalid rounding limits')
    for case in CASES:
        grid,block=geometry(case)
        if block[0]*block[1]*block[2]>limits[0] or any(b>bound for b,bound in zip(block,limits[1:4])) or any(g>bound for g,bound in zip(grid,limits[4:])):raise ValueError('insufficient rounding device limits')

def validate_report(value,seed):
    if type(value) is not dict or type(value.get('adapter')) is not str or not 1<=len(value['adapter'])<=255 or '\0' in value['adapter']:return False
    try:seed_value(seed);preflight(value.get('limits'))
    except ValueError:return False
    return exact(value,dict(status='completed',seed=seed,adapter=value['adapter'],limits=value['limits'],cases=[dict(case=list(c),grid=list(geometry(c)[0]),block=list(geometry(c)[1]),output_words=c[1]*c[3]) for c in CASES],cleanup='pass'))

def validate_job(job,folder):
    if type(job) is not dict or set(job)!={'schema_version','seed','files'} or type(job['schema_version']) is not int or job['schema_version']!=JOB_SCHEMA:raise ValueError('rounding job schema')
    wanted=input_files(job['seed']);pins=job['files'];required=set(wanted)|{'nvcuda.dll','matrix.ptx'};folder=Path(folder).resolve()
    if type(pins) is not dict or set(pins) not in (required,required|{'ct_underlying.dll'}):raise ValueError('rounding job files')
    for name,sha in pins.items():
        path=folder/name
        if type(sha) is not str or not re.fullmatch('[0-9a-f]{64}',sha) or not path.is_file() or not path.resolve().is_relative_to(folder) or hashlib.sha256(path.read_bytes()).hexdigest()!=sha:raise ValueError('rounding artifact drift')
    if any((folder/n).read_bytes()!=data for n,data in wanted.items()):raise ValueError('rounding input drift')
    if any((folder/f'case-{i}-{key}-readback.bin').exists() for i in range(len(CASES)) for key in ('a','b','c')):raise ValueError('stale rounding readback')
    return entry_map((folder/'matrix.ptx').read_bytes())
