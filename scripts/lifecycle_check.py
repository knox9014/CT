"""Independent closed raw-buffer expectations for bounded resource reuse."""
import struct
from matrix_kernel_check import exact
SEEDS=(193,731)
GUARD=0xdeadbeef
NAN=0x7fc00000
MASK=0xffffffff

def closed(seed,cycles,kind):
    if type(seed) is not int or seed not in SEEDS or type(cycles) is not int or cycles not in ((8,256) if kind=='runtime' else (8,160)):raise ValueError('unqualified lifetime profile')

def runtime_header(seed,cycles):
    closed(seed,cycles,'runtime')
    return dict(status='completed',seed=seed,cycles=cycles,stale_checks=4*cycles+2,recoverable_errors=4*cycles,budget_errors=2,replacements=2,cleanup=True)

def runtime_row(seed,index,mode):
    if mode not in ('positive','noop_launch','noop_copy'):raise ValueError('lifetime mode')
    values=[((((seed+index*31)*7919+i*1237)&MASK)^0xa5a55a5a) for i in range(32)]
    a=[GUARD]+values+[GUARD]
    b=[GUARD]+[((v+17)&MASK) if mode=='positive' else 0 for v in values]+[GUARD]
    if mode=='noop_copy':a=[0x5a5a5a5a]*34;b=[0]+[0x5a5a5a6b]*32+[0]
    return [GUARD]+a+b+[GUARD]

def validate_runtime(value,seed,cycles,mode):
    try:
        wanted=runtime_header(seed,cycles);wanted['rows']=[runtime_row(seed,i,mode) for i in range(cycles)]
        return exact(value,wanted)
    except (ValueError,TypeError):return False

def bits(value):return struct.unpack('<I',struct.pack('<f',value))[0]

def driver_header(seed,cycles):
    closed(seed,cycles,'driver')
    return dict(status='completed',seed=seed,cycles=cycles,stale_checks=3*cycles,recoverable_errors=2*cycles,cleanup=True)

def driver_parts(seed,index):
    base=seed%17+index
    a=[GUARD]*16+[bits((base+i)/8) for i in range(32)]+[GUARD]*16
    b=[GUARD]*16+[bits(-i/16) for i in range(32)]+[GUARD]*16
    initial=[GUARD]*16+[NAN]*32+[GUARD]*16
    output=[GUARD]*16+[bits((2*base+i)/16) for i in range(32)]+[GUARD]*16
    return a,b,initial,output

def driver_row(seed,index,mode):
    a,b,initial,out=driver_parts(seed,index)
    if mode=='positive':return a+b+out
    if mode=='noop_launch':return a+b+initial
    if mode=='noop_copy':return [NAN]*192
    raise ValueError('lifetime mode')

def validate_driver(value,seed,cycles,mode):
    try:
        wanted=driver_header(seed,cycles)
        if type(value) is not dict or set(value)!=set(wanted)|{'rows'} or not exact({k:value[k] for k in wanted},wanted):return False
        rows=value['rows']
        if type(rows) is not list or len(rows)!=cycles:return False
        for i,row in enumerate(rows):
            if type(row) is not list or len(row)!=192 or any(type(w) is not int or not 0<=w<=MASK for w in row):return False
            if mode=='noop_copy':
                if row[:128]!=[NAN]*128 or not all(w&0x7f800000==0x7f800000 and w&0x7fffff for w in row[128:]):return False
            elif not exact(row,driver_row(seed,i,mode)):return False
        return mode in ('positive','noop_launch','noop_copy')
    except (ValueError,TypeError):return False
