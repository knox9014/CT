"""Exact modular arithmetic through CUDA Driver API on the native GPU."""
import ctypes as c
import hashlib
import json

from m3c_gpu_validation import Device, P, U32, U64, REPO
from m3d_fatbin_check import Producer
from m3f_selection_check import load_code
from m3g_modules_check import module, function
from m3k_memory_check import allocate, args

SIZES = (1, 63, 64, 65, 257, 50000)
OPERATIONS = [(op, kind) for op in ('add', 'sub', 'mul.lo', 'mad.lo')
              for kind in ('u32', 's32', 'u64', 's64')]


def oracle(op, a, b, third, width):
    if op == 'add': value = a + b
    elif op == 'sub': value = a - b
    elif op == 'mul.lo': value = a * b
    elif op == 'mad.lo': value = a * b + third
    else: raise ValueError('unknown operation')
    return value & ((1 << width) - 1)


def source(profile=7):
    text = f'// Synthetic modular arithmetic probe.\n.version {profile}.0 .target sm_{50 if profile == 7 else 52} .address_size 64\n'
    for index, (op, kind) in enumerate(OPERATIONS):
        width = int(kind[1:]); step = width // 8
        # Give the higher alternative observably different add/sub semantics.
        if profile == 8: op = {'add': 'sub', 'sub': 'add'}.get(op, op)
        reg = '%r' if width == 32 else '%d'
        text += f'''.visible .entry calc_{index}(
 .param .u64 .ptr .global .align 8 a,
 .param .u64 .ptr .global .align 8 b,
 .param .u64 .ptr .global .align 8 third,
 .param .u64 .ptr .global .align 8 output,
 .param .u32 n) {{
 .reg .b32 %r<9>; .reg .b64 %d<10>; .reg .pred %p;
 ld.param.u64 %d0,[a]; ld.param.u64 %d1,[b];
 ld.param.u64 %d2,[third]; ld.param.u64 %d3,[output];
 ld.param.u32 %r0,[n]; mov.u32 %r1,%tid.x;
 mov.u32 %r2,%ctaid.x; mov.u32 %r3,%ntid.x;
 mad.lo.u32 %r4,%r2,%r3,%r1; setp.ge.u32 %p,%r4,%r0;
 @%p bra end;
 mul.wide.u32 %d4,%r4,{step};
 add.u64 %d0,%d0,%d4; add.u64 %d1,%d1,%d4;
 add.u64 %d2,%d2,%d4; add.u64 %d3,%d3,%d4;
 ld.global.u{width} {reg}5,[%d0];
 ld.global.u{width} {reg}6,[%d1];
 ld.global.u{width} {reg}7,[%d2];
 {op}.{kind} {reg}8,{reg}5,{reg}6{',' + reg + '7' if op == 'mad.lo' else ''};
 st.global.u{width} [%d3],{reg}8;
 end: ret;
}}
'''
    return text.encode()


def inputs(width, n):
    mask = (1 << width) - 1
    top = 1 << (width - 1)
    boundary = [(0, 0, 0), (mask, 1, 1), (0, 1, mask),
                (top, mask, top), (mask, mask, mask), (top - 1, 2, mask),
                (top + 1, top + 1, top - 1), (1, 0, mask)]
    return [boundary[i] if i < len(boundary) else
            tuple(((i * multiplier) ^ salt) & mask for multiplier, salt in
                  ((0x9e3779b97f4a7c15, top), (0xd1342543de82ef95, mask),
                   (0xa0761d6478bd642f, top - 1))) for i in range(n)]


def execute(device, handle, op, width, n):
    kind = U64 if width == 64 else U32
    mask = (1 << width) - 1; guard = 0xdeadbeefcafebabe & mask
    triples = inputs(width, n)
    expected = [oracle(op, *values, width) for values in triples]
    arrays = [(kind * (n + 128))(*([guard] * (n + 128))) for _ in range(4)]
    for i, values in enumerate(triples):
        for j in range(3): arrays[j][64 + i] = values[j]
        arrays[3][64 + i] = expected[i] ^ mask
    pointers = []
    try:
        for array in arrays: pointers.append(allocate(device, array))
        interior = [U64(p.value + 64 * (width // 8)) for p in pointers]
        count = U32(n); arguments = args([*interior, count])
        device.call('cuLaunchKernel', handle, (n + 63) // 64, 1, 1,
                    64, 1, 1, 0, None, arguments, None)
        copied = (kind * (n + 128))()
        device.call('cuMemcpyDtoH_v2', c.cast(copied, P), pointers[3], c.sizeof(copied))
        if list(copied[64:64+n]) != expected: raise RuntimeError('modular integer mismatch or missing write')
        if any(v != guard for v in [*copied[:64], *copied[64+n:]]): raise RuntimeError('output guard changed')
        for pointer, original in zip(pointers[:3], arrays[:3]):
            device.call('cuMemcpyDtoH_v2', c.cast(copied, P), pointer, c.sizeof(copied))
            if bytes(copied) != bytes(original): raise RuntimeError('input buffer modified')
    finally:
        for pointer in pointers: device.call('cuMemFree_v2', pointer)


def main():
    producer = Producer(); text = source()
    baseline = REPO / '.cache/m3l-baseline/ct_cuda.dll'
    digest = (baseline.parent / 'sha256.txt').read_text(encoding='utf-8-sig').strip()
    if hashlib.sha256(baseline.read_bytes()).hexdigest() != digest: raise RuntimeError('baseline hash mismatch')
    old = Device(baseline)
    try:
        code, handle = load_code(old, text)
        if code not in (218, 801) or handle.value is not None: raise RuntimeError('baseline accepted new arithmetic')
    finally: old.close()
    variants = [('raw', text), ('plain', producer.make(text, 'plain', b'50')),
                ('compressed', producer.make(text, 'compressed', b'50')),
                ('alternatives', producer.make_many([(source(8), b'52'), (text, b'50')], True))]
    device = Device(); cases = results = guards = 0
    try:
        for form, image in variants:
            owner = module(device, image)
            try:
                for index, (op, kind) in enumerate(OPERATIONS):
                    handle = function(device, owner, f'calc_{index}')
                    if form == 'alternatives': op = {'add': 'sub', 'sub': 'add'}.get(op, op)
                    for n in SIZES:
                        execute(device, handle, op, int(kind[1:]), n)
                        cases += 1; results += n; guards += 128
            finally: device.call('cuModuleUnload', owner)
    finally: device.close()
    print(json.dumps(dict(status='pass', spellings=16, formats=4, cases=cases,
                         results=results, guards=guards, inputs_preserved=True,
                         baseline_rejected=True, alternative_selection=True)))


if __name__ == '__main__': main()
