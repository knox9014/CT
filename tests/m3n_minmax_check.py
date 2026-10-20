"""Native integer extrema/unary operations with independent Python oracle."""
import hashlib
import json

from m3c_gpu_validation import Device, REPO
from m3d_fatbin_check import Producer
from m3f_selection_check import load_code
from m3g_modules_check import module, function
from m3l_arithmetic_check import execute, SIZES
from m3m_predicates_check import inputs as predicate_inputs

OPERATIONS = ([(op, kind) for op in ('min', 'max')
               for kind in ('u32', 's32', 'u64', 's64')] +
              [(op, kind) for op in ('abs', 'neg') for kind in ('s32', 's64')])


def inputs(width, n):
    triples = predicate_inputs(width, n)
    mask = (1 << width) - 1
    for index, (a, b) in enumerate([(mask, 0), (1, mask)], 8):
        if index < n:
            triples[index] = (a, b, triples[index][2])
    return triples


def oracle(op, kind, a, b):
    width = int(kind[1:]); mask = (1 << width) - 1; top = 1 << (width - 1)
    if kind.startswith('s'):
        if a & top: a -= 1 << width
        if b & top: b -= 1 << width
    if op == 'min': value = min(a, b)
    elif op == 'max': value = max(a, b)
    elif op == 'abs': value = abs(a)
    elif op == 'neg': value = -a
    else: raise ValueError('unknown operation')
    return value & mask


def source(profile=7):
    text = f'// Synthetic integer min/max/abs/neg probe.\n.version {profile}.0 .target sm_{50 if profile == 7 else 52} .address_size 64\n'
    for index, (op, kind) in enumerate(OPERATIONS):
        width = int(kind[1:]); reg = '%r' if width == 32 else '%d'
        operand = f'{reg}5' + (f',{reg}6' if op in ('min', 'max') else '')
        alternate = f'not.b{width} {reg}8,{reg}8;' if profile == 8 else ''
        text += f'''.visible .entry extrema_{index}(
 .param .u64 .ptr .global .align 8 a,
 .param .u64 .ptr .global .align 8 b,
 .param .u64 .ptr .global .align 8 unused,
 .param .u64 .ptr .global .align 8 output,
 .param .u32 n) {{
 .reg .b32 %r<9>; .reg .b64 %d<9>; .reg .pred %p;
 ld.param.u64 %d0,[a]; ld.param.u64 %d1,[b];
 ld.param.u64 %d2,[unused]; ld.param.u64 %d3,[output];
 ld.param.u32 %r0,[n]; mov.u32 %r1,%tid.x;
 mov.u32 %r2,%ctaid.x; mov.u32 %r3,%ntid.x;
 mad.lo.u32 %r4,%r2,%r3,%r1; setp.ge.u32 %p,%r4,%r0;
 @%p bra end; mul.wide.u32 %d4,%r4,{width // 8};
 add.u64 %d0,%d0,%d4; add.u64 %d1,%d1,%d4;
 add.u64 %d3,%d3,%d4;
 ld.global.u{width} {reg}5,[%d0]; ld.global.u{width} {reg}6,[%d1];
 {op}.{kind} {reg}8,{operand}; {alternate}
 st.global.u{width} [%d3],{reg}8;
 end: ret;
}}
'''
    return text.encode()


def main():
    producer = Producer(); text = source()
    baseline = REPO / '.cache/m3n-baseline/ct_cuda.dll'
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
                for index, (op, kind) in enumerate(OPERATIONS):
                    width = int(kind[1:]); mask = (1 << width) - 1
                    handle = function(device, owner, f'extrema_{index}')
                    for n in SIZES:
                        triples = [(a, a if i % 7 == 0 else b, value)
                                   for i, (a, b, value) in enumerate(inputs(width, n))]
                        expected = [oracle(op, kind, a, b) ^ (mask if form == 'alternatives' else 0)
                                    for a, b, _ in triples]
                        execute(device, handle, op, width, n,
                                input_values=triples, expected_values=expected)
                        cases += 1; results += n; guards += 128
            finally: device.call('cuModuleUnload', owner)
    finally: device.close()
    print(json.dumps(dict(status='pass', spellings=12, formats=4, cases=cases,
                         results=results, guards=guards, inputs_preserved=True,
                         baseline_rejected=True, alternative_selection=True)))


if __name__ == '__main__': main()
