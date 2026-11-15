"""Independent exact float32 check; sample PASS text is insufficient evidence."""
import math
import struct


def validate_inputs(a, b, *, count=50000):
    if type(count) is not int or not 1 <= count <= 50000 or any(
            type(v) is not bytes or len(v) != count * 4 for v in (a,b)):
        return ['upstream input-buffer shape']
    if any(not math.isfinite(v) or not 0 <= v <= 1
           for data in (a,b) for (v,) in struct.iter_unpack('<f',data)):
        return ['upstream nonfinite/out-of-domain input']
    return []


def validate_buffers(a, b, c, *, count=50000):
    if validate_inputs(a,b,count=count) or type(c) is not bytes or len(c)!=count*4:
        return ['upstream raw-buffer shape']
    left, right, output = (struct.unpack('<' + 'f' * count, v) for v in (a,b,c))
    for x,y,z in zip(left,right,output):
        if not all(math.isfinite(v) for v in (x,y,z)) or not (0 <= x <= 1 and 0 <= y <= 1):
            return ['upstream nonfinite/out-of-domain observation']
        if struct.pack('<f', x+y) != struct.pack('<f', z):
            return ['upstream exact float32 sum mismatch']
    return []


def validate_trace(value, *, noop=False):
    wanted = dict(device='Intel(R) Arc(TM) B390 GPU', allocations=3,h2d=2,dtoh=1,
                  launches=1,forwarded=0 if noop else 1,frees=3,bytes=200000)
    return [] if type(value) is dict and value.keys() == wanted.keys() and all(
        type(value[k]) is type(v) and value[k] == v for k,v in wanted.items()) else ['upstream trace schema/counters']
