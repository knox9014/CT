"""Translate stored u64 and mixed globals and validate with pinned SPIRV-Tools."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
from compatibility_registry import validate_toolchain
from validate_spirv import run_validator

PREFIX = '.version 8.0\n.target sm_52\n.address_size 64\n'
FIXTURES = {
    'zero_unused': '.global .align 8 .u64 wide; .entry test(){ret;}',
    'initialized_shared': '.global .align 8 .u64 wide=0x1234567800000000; .entry first(){.reg .b64 %rd;ld.global.u64 %rd,[wide];ret;} .entry second(){st.global.u64 [wide],-1;ret;}',
    'volatile': '.global .align 8 .u64 wide=-1; .entry test(){.reg .b64 %rd;ld.volatile.global.u64 %rd,[wide];st.volatile.global.u64 [wide],%rd;ret;}',
    'mixed': '.global .align 4 .u32 small=11; .global .align 8 .u64 wide=0xffffffffffffffff; .entry test(){.reg .b32 %r;.reg .b64 %rd;ld.global.u32 %r,[small];ld.global.u64 %rd,[wide];ret;}',
}


def check_modules(directory, translator, validator, entry):
    rows = []
    for name, source in FIXTURES.items():
        ptx = directory/(name+'.ptx'); output = directory/(name+'.spv')
        ptx.write_text(PREFIX+source, encoding='utf-8')
        completed = subprocess.run([str(translator), str(ptx), str(output)], capture_output=True, timeout=30)
        if completed.returncode or not output.is_file():
            raise ValueError('global translation failed')
        rows.append(dict(case_id=name, expected='accepted', **run_validator(output, validator, entry, required=True)))
    good = (directory/'initialized_shared.spv').read_bytes()
    for name, data in [('truncated', good[:-3]), ('bad_magic', b'BAD!'+good[4:])]:
        output = directory/(name+'.spv'); output.write_bytes(data)
        rows.append(dict(case_id=name, expected='rejected', **run_validator(output, validator, entry, required=True)))
    return rows


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validator', type=Path, required=True)
    parser.add_argument('--lock', type=Path, default=root/'docs/compatibility/toolchain-lock-v1.json')
    args = parser.parse_args()
    try:
        lock = json.loads(args.lock.read_text())
        if validate_toolchain(lock): raise ValueError('invalid lock')
        entry = next(t for t in lock['tools'] if t['id']=='spirv-val')
        build = subprocess.run(['cargo', 'build', '-p', 'ct-codegen-spirv', '--example', 'translate_module'], cwd=root, capture_output=True, timeout=120)
        if build.returncode: raise ValueError('translator build failed')
        cache=root/'.cache/u64-global-validator'; cache.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as d:
            rows=check_modules(Path(d), root/'target/debug/examples/translate_module.exe', args.validator, entry)
        passed=all(r['status']=='pass' if r['expected']=='accepted' else r['status']=='fail' and r['reason']=='validation_rejected' for r in rows)
        print(json.dumps(dict(status='pass' if passed else 'fail', cases=rows)))
        return int(not passed)
    except (OSError, ValueError, StopIteration, subprocess.SubprocessError):
        print(json.dumps(dict(status='fail', reason='global_validation_failed')))
        return 1

if __name__=='__main__': raise SystemExit(main())
