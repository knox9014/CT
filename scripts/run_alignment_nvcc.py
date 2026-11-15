"""Diagnostic mixed-pointer nvcc consumer with original-byte replay and controls."""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import uuid

from run_relaxed_nvcc import (command, verify_files, build_commands, ptx_tokens,
                              host_environment, digest, payload, audit_probe,
                              source_fingerprint, prepare_bundle)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from alignment_nvcc_oracle import validate

SOURCE = 'tests/fixtures/alignment_nvcc_runtime.cu'
INPUTS = [SOURCE, 'tests/alignment_nvcc_oracle.py', 'tests/test_alignment_nvcc.py',
          'scripts/run_alignment_nvcc.py', 'scripts/run_relaxed_nvcc.py',
          'scripts/prepare_nvcc_default.py', 'scripts/prepare_nvcc_probe.py',
          'scripts/ct.py', 'scripts/run_validation.py', 'tests/p04a_noop_driver.c',
          'tests/p09a_noop_driver.c', 'tests/p04a_driver_control.def', 'include/ct_cuda.h']


def require_ptx(text):
    for entry in ('widen_array', 'copy_narrow'):
        m = re.search(r'\.entry\s+' + entry + r'\s*\(([^)]*)\)\s*\{([^}]*)\}', text)
        if not m or '.ptr' in m[1] or len(re.findall(r'\.param\s+\.u64\b', m[1])) != 2:
            raise ValueError('expected unannotated producer pointers absent')
        if 'cvta.to.global.u64' not in m[2]:
            raise ValueError('producer pointer conversions absent')
        store = 'st.global.u64' if entry == 'widen_array' else 'st.global.u32'
        if store not in m[2]:
            raise ValueError('producer memory operation absent')


def observe(folder, driver, seed):
    bundle, _ = prepare_bundle(folder / 'default.exe', folder / driver, [],
                               folder / 'runs', runtime_dll=folder / 'ct_cudart.dll')
    if driver == 'noop.dll':
        shutil.copyfile(folder / 'ct_cuda.dll', bundle / 'ct_underlying.dll')
    files = {p.name: digest(p) for p in bundle.iterdir() if p.is_file()}
    verify_files(bundle, files)
    result = subprocess.run([str(bundle / 'default.exe'), str(seed)], cwd=bundle,
                            capture_output=True, timeout=60)
    verify_files(bundle, files)
    noop = driver == 'noop.dll'
    if result.returncode or result.stderr or validate(json.loads(result.stdout), seed, noop=noop):
        raise ValueError('consumer execution/control failed')
    if noop and not validate(json.loads(result.stdout), seed):
        raise ValueError('noop falsely passed positive oracle')
    (bundle / 'stdout.json').write_bytes(result.stdout)
    (bundle / 'stderr.txt').write_bytes(result.stderr)
    return dict(seed=seed, mode='noop' if noop else 'positive', exit_code=0,
                bundle=bundle.relative_to(folder).as_posix(), files=files,
                stdout=digest(bundle / 'stdout.json'), stderr=digest(bundle / 'stderr.txt'))


def validate_runs(folder, files, rows):
    if (type(rows) is not list or len(rows) != 3
            or [r['mode'] for r in rows] != ['positive', 'positive', 'noop']
            or len({r['seed'] for r in rows}) != 3):
        raise ValueError('positive/control/fresh-seed set invalid')
    for row in rows:
        if set(row) != {'seed', 'mode', 'exit_code', 'bundle', 'files', 'stdout', 'stderr'} or type(row['exit_code']) is not int or row['exit_code'] != 0:
            raise ValueError('execution row schema')
        bundle = (folder / row['bundle']).resolve()
        if not bundle.is_relative_to(folder / 'runs'):
            raise ValueError('bundle escape')
        noop = row['mode'] == 'noop'
        wanted = {'default.exe': files['default.exe'], 'cudart64_12.dll': files['ct_cudart.dll'],
                  'nvcuda.dll': files['noop.dll' if noop else 'ct_cuda.dll']}
        if noop:
            wanted['ct_underlying.dll'] = files['ct_cuda.dll']
        if row['files'] != wanted:
            raise ValueError('bundle provider roles changed')
        verify_files(bundle, wanted)
        verify_files(bundle, {'stdout.json': row['stdout'], 'stderr.txt': row['stderr']})
        value = json.loads((bundle / 'stdout.json').read_bytes())
        if ((bundle / 'stderr.txt').read_bytes() or validate(value, row['seed'], noop=noop)
                or (noop and not validate(value, row['seed']))):
            raise ValueError('saved observations/control changed')


def audit(path):
    folder = path.resolve().parent
    if not folder.is_relative_to(ROOT / '.cache/alignment-nvcc-runs'):
        raise ValueError('capture escape')
    m = json.loads(path.read_bytes())
    if (set(m) != {'schema_version', 'scope', 'release_claim', 'source_fingerprint', 'inputs',
                  'producer_sha256', 'commands', 'files', 'runs'}
            or type(m['schema_version']) is not int or m['schema_version'] != 1
            or m['scope'] != 'diagnostic_alignment_nvcc' or m['release_claim'] is not False):
        raise ValueError('capture schema/scope')
    if m['source_fingerprint'] != source_fingerprint(ROOT) or m['inputs'] != {p:digest(ROOT/p) for p in INPUTS}:
        raise ValueError('capture source changed')
    producer = ROOT / '.cache/p09a2-producer/manifest.json'
    if digest(producer) != m['producer_sha256'] or audit_probe(producer):
        raise ValueError('producer changed')
    base = json.loads(producer.read_bytes())
    if base['host']['profile'] != 'diagnostic' or m['commands'] != build_commands(folder, producer, base):
        raise ValueError('producer host/recipe scope changed')
    required = {'default.exe','vector.cu','ct_cuda.dll','ct_cudart.dll','noop.dll',
                'keep/vector.ptx','keep/vector.fatbin','keep/default_dlink.fatbin',
                'keep/vector.cudafe1.stub.c','keep/default_dlink.reg.c'}
    if not required <= set(m['files']):
        raise ValueError('compiler/runtime artifacts absent')
    verify_files(folder, m['files'])
    if digest(folder / 'vector.cu') != m['inputs'][SOURCE]:
        raise ValueError('compiled source differs')
    require_ptx((folder / 'keep/vector.ptx').read_text(encoding='utf-8'))
    if ptx_tokens(payload(folder / 'keep/vector.fatbin')) != ptx_tokens((folder / 'keep/vector.ptx').read_bytes()):
        raise ValueError('kept PTX/payload mismatch')
    exe = (folder / 'default.exe').read_bytes()
    if any((folder / 'keep' / n).read_bytes() not in exe for n in ('vector.fatbin','default_dlink.fatbin')):
        raise ValueError('compiler image not embedded in EXE')
    validate_runs(folder, m['files'], m['runs'])
    return m


def execute_set(folder, files, *, exclude=()):
    seeds = set()
    while len(seeds) < 3:
        seed = secrets.randbelow(1000000) + 1
        if seed not in exclude:
            seeds.add(seed)
    rows = []
    for seed, driver in zip(sorted(seeds), ('ct_cuda.dll','ct_cuda.dll','noop.dll')):
        verify_files(folder, files)
        rows.append(observe(folder, driver, seed))
    verify_files(folder, files)
    validate_runs(folder, files, rows)
    return rows


def build():
    folder = ROOT / '.cache/alignment-nvcc-runs' / uuid.uuid4().hex
    folder.mkdir(parents=True)
    producer = ROOT / '.cache/p09a2-producer/manifest.json'
    base, env = host_environment(producer, folder)
    if base['host']['profile'] != 'diagnostic':
        raise ValueError('diagnostic recipe only')
    fingerprint = source_fingerprint(ROOT)
    inputs = {p:digest(ROOT/p) for p in INPUTS}
    shutil.copyfile(ROOT / SOURCE, folder / 'vector.cu')
    (folder / 'keep').mkdir()
    commands = build_commands(folder, producer, base)
    for role in ('cuda','noop'):
        command(commands[role], folder, env, role)
    require_ptx((folder / 'keep/vector.ptx').read_text(encoding='utf-8'))
    for role, dll in (('driver','ct_cuda.dll'),('runtime','ct_cudart.dll')):
        build_env = dict(os.environ, CARGO_INCREMENTAL='0', CARGO_TARGET_DIR=str(folder / (role+'-target')))
        command(commands[role], folder, build_env, role, cwd=ROOT)
        shutil.copyfile(folder / (role+'-target/debug') / dll, folder / dll)
    names = ['default.exe','vector.cu','ct_cuda.dll','ct_cudart.dll','noop.dll']
    names += [p.relative_to(folder).as_posix() for p in (folder/'keep').iterdir()
              if p.is_file() and (p.suffix in ('.ptx','.fatbin') or p.name.endswith(('.stub.c','.reg.c','.fatbin.c')))]
    files = {n:digest(folder/n) for n in names}
    m = dict(schema_version=1,scope='diagnostic_alignment_nvcc',release_claim=False,
             source_fingerprint=fingerprint,inputs=inputs,producer_sha256=digest(producer),
             commands=commands,files=files,runs=execute_set(folder, files))
    path = folder/'manifest.json'
    path.write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8')
    audit(path)
    return path,m


def replay(path):
    m = audit(path)
    sha = digest(path)
    rows = execute_set(path.resolve().parent,m['files'],exclude={r['seed'] for r in m['runs']})
    if digest(path) != sha or source_fingerprint(ROOT) != m['source_fingerprint']:
        raise ValueError('replay input drift')
    report = dict(manifest_sha256=sha,release_claim=False,runs=rows)
    (path.parent/('replay-'+uuid.uuid4().hex+'.json')).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return m


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--audit',type=Path)
    modes.add_argument('--replay',type=Path)
    args = parser.parse_args()
    try:
        path = args.audit or args.replay
        if args.audit:
            m = audit(path)
        elif args.replay:
            m = replay(path)
        else:
            path,m = build()
        print(json.dumps(dict(status='pass',scope=m['scope'],release_claim=False,
                              execution_performed=not bool(args.audit),
                              manifest=path.resolve().relative_to(ROOT).as_posix(),
                              application_sha256=m['files']['default.exe'])))
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError):
        print(json.dumps(dict(status='fail',reason='alignment_nvcc_diagnostic_failed')))
        raise SystemExit(1)
