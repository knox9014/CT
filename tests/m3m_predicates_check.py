"""Native full-width setp/selp checks through CT's CUDA Driver API."""
import ctypes as c
import hashlib
import json
import operator

from m3c_gpu_validation import Device, P, U32, U64, REPO
from m3d_fatbin_check import Producer
from m3f_selection_check import load_code
from m3g_modules_check import module, function
from m3k_memory_check import allocate, args
from m3l_arithmetic_check import inputs, SIZES

RELATIONS = dict(eq=operator.eq, ne=operator.ne, lt=operator.lt,
                 le=operator.le, gt=operator.gt, ge=operator.ge)
OPERATIONS = [(relation, kind) for relation in RELATIONS
              for kind in ('u32', 's32', 'u64', 's64')]


def oracle(relation, kind, a, b, value, invert=False):
    width = int(kind[1:]); top = 1 << (width - 1); mask = (1 << width) - 1
    if kind.startswith('s'):
        if a & top: a -= 1 << width
        if b & top: b -= 1 << width
    predicate = RELATIONS[relation](a, b)
    if invert: predicate = not predicate
    return value if predicate else value ^ mask


def source(profile=7):
    text = f'// Synthetic integer predicate/select probe.\n.version {profile}.0 .target sm_{50 if profile == 7 else 52} .address_size 64\n'
    for index, (relation, kind) in enumerate(OPERATIONS):
        width = int(kind[1:]); reg = '%r' if width == 32 else '%d'
        select = ('b', 'u', 's')[index % 3] + str(width)
        # Higher profile swaps both select arms, making selection observable.
        arms = f'{reg}7,{reg}9' if profile == 7 else f'{reg}9,{reg}7'
        text += f'''.visible .entry predicate_{index}(
 .param .u64 .ptr .global .align 8 a,
 .param .u64 .ptr .global .align 8 b,
 .param .u64 .ptr .global .align 8 value,
 .param .u64 .ptr .global .align 8 output,
 .param .u32 n) {{
 .reg .b32 %r<10>; .reg .b64 %d<10>; .reg .pred %p;
 ld.param.u64 %d0,[a]; ld.param.u64 %d1,[b];
 ld.param.u64 %d2,[value]; ld.param.u64 %d3,[output];
 ld.param.u32 %r0,[n]; mov.u32 %r1,%tid.x;
 mov.u32 %r2,%ctaid.x; mov.u32 %r3,%ntid.x;
 mad.lo.u32 %r4,%r2,%r3,%r1; setp.ge.u32 %p,%r4,%r0;
 @%p bra end; mul.wide.u32 %d4,%r4,{width // 8};
 add.u64 %d0,%d0,%d4; add.u64 %d1,%d1,%d4;
 add.u64 %d2,%d2,%d4; add.u64 %d3,%d3,%d4;
 ld.global.u{width} {reg}5,[%d0]; ld.global.u{width} {reg}6,[%d1];
 ld.global.u{width} {reg}7,[%d2]; not.b{width} {reg}9,{reg}7;
 setp.{relation}.{kind} %p,{reg}5,{reg}6;
 selp.{select} {reg}8,{arms},%p;
 st.global.u{width} [%d3],{reg}8;
 end: ret;
}}
'''
    return text.encode()


def execute(device, handle, relation, kind, n, invert=False):
    width = int(kind[1:]); element = U64 if width == 64 else U32
    mask = (1 << width) - 1; guard = 0xdeadbeefcafebabe & mask
    triples = [(a, a if i % 5 == 0 else b, value)
               for i, (a, b, value) in enumerate(inputs(width, n))]
    expected = [oracle(relation, kind, *values, invert) for values in triples]
    arrays = [(element * (n + 128))(*([guard] * (n + 128))) for _ in range(4)]
    for i, values in enumerate(triples):
        for j in range(3): arrays[j][64+i] = values[j]
        arrays[3][64+i] = expected[i] ^ mask
    pointers = []
    try:
        for array in arrays: pointers.append(allocate(device, array))
        interior = [U64(p.value + 64 * (width // 8)) for p in pointers]
        count = U32(n); arguments = args([*interior, count])
        device.call('cuLaunchKernel', handle, (n+63)//64, 1, 1,
                    64, 1, 1, 0, None, arguments, None)
        copied = (element * (n + 128))()
        device.call('cuMemcpyDtoH_v2', c.cast(copied, P), pointers[3], c.sizeof(copied))
        if list(copied[64:64+n]) != expected: raise RuntimeError('integer predicate/select mismatch or missing write')
        if any(v != guard for v in [*copied[:64], *copied[64+n:]]): raise RuntimeError('output guard modified')
        for pointer, original in zip(pointers[:3], arrays[:3]):
            device.call('cuMemcpyDtoH_v2', c.cast(copied, P), pointer, c.sizeof(copied))
            if bytes(copied) != bytes(original): raise RuntimeError('read-only input modified')
    finally:
        for pointer in pointers: device.call('cuMemFree_v2', pointer)


def main():
    text = source(); producer = Producer()
    baseline = REPO / '.cache/m3m-baseline/ct_cuda.dll'
    digest = (baseline.parent / 'sha256.txt').read_text(encoding='utf-8-sig').strip()
    if hashlib.sha256(baseline.read_bytes()).hexdigest() != digest: raise RuntimeError('baseline hash mismatch')
    old = Device(baseline)
    try:
        code, handle = load_code(old, text)
        if code not in (218, 801) or handle.value is not None: raise RuntimeError('baseline accepted extension')
    finally: old.close()
    variants = [('raw', text), ('plain', producer.make(text, 'plain', b'50')),
                ('compressed', producer.make(text, 'compressed', b'50')),
                ('alternatives', producer.make_many([(source(8), b'52'), (text, b'50')], True))]
    device = Device(); cases = results = guards = 0
    try:
        for form, image in variants:
            owner = module(device, image)
            try:
                for index, (relation, kind) in enumerate(OPERATIONS):
                    handle = function(device, owner, f'predicate_{index}')
                    for n in SIZES:
                        execute(device, handle, relation, kind, n, form == 'alternatives')
                        cases += 1; results += n; guards += 128
            finally: device.call('cuModuleUnload', owner)
    finally: device.close()
    print(json.dumps(dict(status='pass', comparisons=24, select_spellings=6,
                         formats=4, cases=cases, results=results, guards=guards,
                         inputs_preserved=True, baseline_rejected=True,
                         alternative_selection=True)))


if __name__ == '__main__': main()
