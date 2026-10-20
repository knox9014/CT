"""Native signed literal parsing through ordinary CUDA Driver API launches."""
import hashlib
import json

from m3c_gpu_validation import Device, REPO
from m3d_fatbin_check import Producer
from m3f_selection_check import load_code
from m3g_modules_check import module, function
from m3l_arithmetic_check import execute, SIZES
from m3n_minmax_check import inputs


def literals(width):
    mask = (1 << width) - 1; top = 1 << (width - 1)
    # Expected bits are explicit arithmetic values, not a PTX token parser.
    return [('-1', mask), (f'-{top}', top), ('-0x1', mask), ('-01', mask),
            (f'+0x{mask:x}', mask), ('+0', 0), ('-0', 0), ('+01', 1)]


OPERATIONS = [(mode, width, literal, bits) for mode in ('mov', 'add')
              for width in (32, 64) for literal, bits in literals(width)]


def source(profile=7):
    text = f'// Synthetic signed immediate probe.\n.version {profile}.0 .target sm_{50 if profile == 7 else 52} .address_size 64\n'
    for index, (mode, width, literal, _) in enumerate(OPERATIONS):
        reg = '%r' if width == 32 else '%d'
        operation = (f'mov.s{width} {reg}8,{literal};' if mode == 'mov'
                     else f'add.u{width} {reg}8,{reg}5,{literal};')
        alternate = f'not.b{width} {reg}8,{reg}8;' if profile == 8 else ''
        text += f'''.visible .entry immediate_{index}(
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
 add.u64 %d0,%d0,%d4; add.u64 %d3,%d3,%d4;
 ld.global.u{width} {reg}5,[%d0];
 {operation} {alternate}
 st.global.u{width} [%d3],{reg}8;
 end: ret;
}}
'''
    return text.encode()


def run_case(device, handle, mode, width, bits, n, invert=False):
    mask = (1 << width) - 1; triples = inputs(width, n)
    expected = [((bits if mode == 'mov' else (a + bits) & mask)
                 ^ (mask if invert else 0)) for a, _, _ in triples]
    execute(device, handle, mode, width, n,
            input_values=triples, expected_values=expected)


def main():
    producer = Producer(); text = source()
    baseline = REPO / '.cache/m3o-baseline/ct_cuda.dll'
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
                for index, (mode, width, _, bits) in enumerate(OPERATIONS):
                    handle = function(device, owner, f'immediate_{index}')
                    for n in SIZES:
                        run_case(device, handle, mode, width, bits, n, form == 'alternatives')
                        cases += 1; results += n; guards += 128
            finally: device.call('cuModuleUnload', owner)
        code, handle = load_code(device, text.replace(b',-1;', b',-2147483649;', 1))
        if code not in (218, 801) or handle.value is not None: raise RuntimeError('out-of-range literal accepted')
        owner = module(device, text)
        try: run_case(device, function(device, owner, 'immediate_0'), 'mov', 32, 0xffffffff, 65)
        finally: device.call('cuModuleUnload', owner)
    finally: device.close()
    print(json.dumps(dict(status='pass', entries=32, literal_forms_per_width=8,
                         formats=4, cases=cases, results=results, guards=guards,
                         inputs_preserved=True, baseline_rejected=True,
                         alternative_selection=True, bad_literal_recovery=True)))


if __name__ == '__main__': main()
