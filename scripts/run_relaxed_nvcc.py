"""Genuine nvcc/Runtime diagnostic; local evidence, no clean release claim."""
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

from prepare_nvcc_default import host_environment, compiler_args
from prepare_nvcc_probe import audit_probe, digest, payload
from run_validation import source_fingerprint
from ct import prepare_bundle

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from relaxed_nvcc_oracle import validate

SOURCE = 'tests/fixtures/relaxed_nvcc_runtime.cu'
INPUTS = [SOURCE, 'tests/relaxed_nvcc_oracle.py', 'tests/test_relaxed_nvcc.py',
          'scripts/run_relaxed_nvcc.py', 'scripts/prepare_nvcc_default.py',
          'scripts/prepare_nvcc_probe.py', 'scripts/ct.py', 'scripts/run_validation.py',
          'tests/p04a_noop_driver.c', 'tests/p09a_noop_driver.c',
          'tests/p04a_driver_control.def', 'include/ct_cuda.h', 'include/ct_cudart.h']


def require_relaxed_ptx(text):
    """Require both natural instruction shapes in their own producer entries."""
    for entry, load in (('widen_value', True), ('narrow_value', False)):
        match = re.search(r'\.entry\s+' + entry + r'\s*\([^)]*\)\s*\{([^}]*)\}', text)
        if not match:
            raise ValueError('required producer entry absent')
        body = match[1]
        wide = set(re.findall(r'\.reg\s+\.b64\s+(%\w+)\s*;', body))
        for stem, count in re.findall(r'\.reg\s+\.b64\s+(%\w+)<(\d+)>\s*;', body):
            if int(count) > 256:
                raise ValueError('producer register limit')
            wide.update(stem + str(i) for i in range(int(count)))
        pattern = (r'ld\.volatile\.global\.u32\s+(%\w+)\s*,\s*\[ct_narrow\]' if load
                   else r'st\.volatile\.global\.u32\s+\[ct_narrow\]\s*,\s*(%\w+)')
        if not any(reg in wide for reg in re.findall(pattern, body)):
            raise ValueError('required natural relaxed operand absent')


def ptx_tokens(data):
    # fatbinary strips comments/formatting from kept PTX. Compare every token;
    # do not edit either producer artifact or substitute a hand-written kernel.
    text = data.decode('ascii').rstrip('\0')
    text = re.sub(r'/\*.*?\*/|//[^\r\n]*', '', text, flags=re.S)
    return re.findall(r'[A-Za-z_$%][A-Za-z0-9_.$%]*|[0-9]+|[^\s]', text)


def verify_files(folder, files):
    if type(files) is not dict or not files:
        raise ValueError('artifact table missing')
    for name, sha in files.items():
        p = folder / name
        if (not isinstance(name, str) or Path(name).is_absolute()
                or not p.resolve().is_relative_to(folder.resolve())
                or not p.is_file() or digest(p) != sha):
            raise ValueError('artifact changed or escaped')


def command(argv, folder, env, label, *, cwd=None):
    result = subprocess.run(argv, cwd=cwd or folder, env=env,
                            capture_output=True, timeout=180)
    (folder / (label + '.stdout')).write_bytes(result.stdout)
    (folder / (label + '.stderr')).write_bytes(result.stderr)
    if result.returncode:
        raise ValueError('diagnostic build failed: ' + label)


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
    if result.returncode or result.stderr:
        raise ValueError('consumer execution failed')
    value = json.loads(result.stdout)
    noop = driver == 'noop.dll'
    if validate(value, seed, noop=noop) or (noop and not validate(value, seed)):
        raise ValueError('consumer/control oracle failed')
    (bundle / 'stdout.json').write_bytes(result.stdout)
    (bundle / 'stderr.txt').write_bytes(result.stderr)
    return dict(seed=seed, mode='noop' if noop else 'positive', exit_code=0,
                bundle=bundle.relative_to(folder).as_posix(), files=files,
                stdout=digest(bundle / 'stdout.json'), stderr=digest(bundle / 'stderr.txt'))


def audit_manifest(path, *, root=ROOT):
    folder = path.resolve().parent
    if not folder.is_relative_to((root / '.cache/relaxed-nvcc-runs').resolve()):
        raise ValueError('manifest escape')
    m = json.loads(path.read_bytes())
    if (set(m) != {'schema_version', 'scope', 'release_claim', 'source_fingerprint',
                  'inputs', 'producer', 'commands', 'files', 'runs'}
            or type(m['schema_version']) is not int or m['schema_version'] != 1
            or m['scope'] != 'diagnostic_relaxed_nvcc' or m['release_claim'] is not False):
        raise ValueError('manifest scope/schema')
    if m['source_fingerprint'] != source_fingerprint(root):
        raise ValueError('source changed')
    if m['inputs'] != {p: digest(root / p) for p in INPUTS}:
        raise ValueError('source inputs changed')
    producer = root / '.cache/p09a2-producer/manifest.json'
    if m['producer'] != {'sha256': digest(producer), 'profile': 'diagnostic'} or audit_probe(producer):
        raise ValueError('producer changed or unqualified scope')
    base = json.loads(producer.read_bytes())
    if m['commands'] != build_commands(folder, producer, base):
        raise ValueError('build recipe changed')
    files = m['files']
    required = {'default.exe', 'vector.cu', 'ct_cuda.dll', 'ct_cudart.dll', 'noop.dll',
                'keep/vector.ptx', 'keep/vector.fatbin', 'keep/default_dlink.fatbin',
                'keep/vector.cudafe1.stub.c', 'keep/default_dlink.reg.c'}
    if not required <= set(files):
        raise ValueError('required compiler/runtime outputs absent')
    verify_files(folder, files)
    if digest(folder / 'vector.cu') != m['inputs'][SOURCE]:
        raise ValueError('producer source differs')
    ptx = (folder / 'keep/vector.ptx').read_text(encoding='utf-8')
    require_relaxed_ptx(ptx)
    # Link kept PTX to the actual fatbin payload, not a separately edited listing.
    if ptx_tokens(payload(folder / 'keep/vector.fatbin')) != ptx_tokens((folder / 'keep/vector.ptx').read_bytes()):
        raise ValueError('producer PTX/payload mismatch')
    validate_runs(folder, files, m['runs'])
    return m


def validate_runs(folder, files, runs):
    if type(runs) is not list or len(runs) != 3 or [v['mode'] for v in runs] != ['positive', 'positive', 'noop']:
        raise ValueError('required execution/control absent')
    if len({v['seed'] for v in runs}) != 3:
        raise ValueError('fresh seeds missing')
    for row in runs:
        if set(row) != {'seed', 'mode', 'exit_code', 'bundle', 'files', 'stdout', 'stderr'} or type(row['exit_code']) is not int or row['exit_code'] != 0:
            raise ValueError('execution schema')
        bundle = (folder / row['bundle']).resolve()
        if not bundle.is_relative_to(folder / 'runs'):
            raise ValueError('bundle escape')
        expected_files = {'default.exe': files['default.exe'], 'cudart64_12.dll': files['ct_cudart.dll'],
                          'nvcuda.dll': files['noop.dll' if row['mode'] == 'noop' else 'ct_cuda.dll']}
        if row['mode'] == 'noop':
            expected_files['ct_underlying.dll'] = files['ct_cuda.dll']
        if row['files'] != expected_files:
            raise ValueError('execution DLL role mismatch')
        verify_files(bundle, row['files'])
        verify_files(bundle, {'stdout.json': row['stdout'], 'stderr.txt': row['stderr']})
        value = json.loads((bundle / 'stdout.json').read_bytes())
        noop = row['mode'] == 'noop'
        if (bundle / 'stderr.txt').read_bytes() or validate(value, row['seed'], noop=noop) or (noop and not validate(value, row['seed'])):
            raise ValueError('saved numerical/control mismatch')


def build_commands(folder, producer, base):
    cl = base['host']['tools']['cl.exe']['path']
    return {
        'cuda': compiler_args(folder, producer.parent, base['host']),
        'noop': [cl, '/nologo', '/W4', '/WX', '/LD', '/DNOOP_LAUNCH',
                 str(ROOT / 'tests/p04a_noop_driver.c'), '/Fo' + str(folder / 'noop.obj'),
                 '/Fe' + str(folder / 'noop.dll'), '/link',
                 '/DEF:' + str(ROOT / 'tests/p04a_driver_control.def')],
        'driver': ['cargo', 'build', '--locked', '-p', 'ct-cuda'],
        'runtime': ['cargo', 'build', '--locked', '--manifest-path', 'crates/ct-cudart/Cargo.toml'],
    }


def run():
    folder = ROOT / '.cache/relaxed-nvcc-runs' / uuid.uuid4().hex
    folder.mkdir(parents=True)
    producer = ROOT / '.cache/p09a2-producer/manifest.json'
    base, env = host_environment(producer, folder)
    if base['host']['profile'] != 'diagnostic':
        raise ValueError('this recipe is diagnostic only')
    fingerprint = source_fingerprint(ROOT)
    inputs = {p: digest(ROOT / p) for p in INPUTS}
    shutil.copyfile(ROOT / SOURCE, folder / 'vector.cu')
    (folder / 'keep').mkdir()
    commands = build_commands(folder, producer, base)
    command(commands['cuda'], folder, env, 'cuda')
    require_relaxed_ptx((folder / 'keep/vector.ptx').read_text(encoding='utf-8'))
    command(commands['noop'], folder, env, 'noop')
    for role, output in (('driver', 'ct_cuda.dll'), ('runtime', 'ct_cudart.dll')):
        build_env = dict(os.environ, CARGO_INCREMENTAL='0', CARGO_TARGET_DIR=str(folder / (role + '-target')))
        command(commands[role], folder, build_env, role, cwd=ROOT)
        shutil.copyfile(folder / (role + '-target/debug') / output, folder / output)
    names = ['default.exe', 'vector.cu', 'ct_cuda.dll', 'ct_cudart.dll', 'noop.dll']
    names += [p.relative_to(folder).as_posix() for p in (folder / 'keep').iterdir()
              if p.is_file() and (p.suffix in ('.ptx', '.fatbin') or p.name.endswith(('.stub.c', '.reg.c', '.fatbin.c')))]
    files = {n: digest(folder / n) for n in names}
    seeds = set()
    while len(seeds) < 3:
        seeds.add(secrets.randbelow(1000000) + 1)
    seeds = sorted(seeds)
    runs = []
    for index, driver in enumerate(('ct_cuda.dll', 'ct_cuda.dll', 'noop.dll')):
        verify_files(folder, files)
        runs.append(observe(folder, driver, seeds[index]))
    m = dict(schema_version=1, scope='diagnostic_relaxed_nvcc', release_claim=False,
             source_fingerprint=fingerprint, inputs=inputs,
             producer={'sha256': digest(producer), 'profile': base['host']['profile']},
             commands=commands, files=files, runs=runs)
    path = folder / 'manifest.json'
    path.write_text(json.dumps(m, indent=2) + '\n', encoding='utf-8')
    audit_manifest(path)
    return path, m


def replay(path):
    m = audit_manifest(path)
    folder = path.resolve().parent
    manifest_sha = digest(path)
    old_seeds = {r['seed'] for r in m['runs']}
    seeds = set()
    while len(seeds) < 3:
        seed = secrets.randbelow(1000000) + 1
        if seed not in old_seeds:
            seeds.add(seed)
    seeds = sorted(seeds)
    rows = []
    for i, driver in enumerate(('ct_cuda.dll', 'ct_cuda.dll', 'noop.dll')):
        verify_files(folder, m['files'])
        rows.append(observe(folder, driver, seeds[i]))
    verify_files(folder, m['files'])
    validate_runs(folder, m['files'], rows)
    if digest(path) != manifest_sha or source_fingerprint(ROOT) != m['source_fingerprint']:
        raise ValueError('replay inputs changed')
    report = {'scope': 'diagnostic_relaxed_nvcc_replay', 'release_claim': False,
              'manifest_sha256': manifest_sha, 'runs': rows}
    (folder / ('replay-' + uuid.uuid4().hex + '.json')).write_text(
        json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return m


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--audit', type=Path)
    actions.add_argument('--replay', type=Path)
    args = parser.parse_args()
    try:
        if args.audit:
            m = audit_manifest(args.audit)
        elif args.replay:
            m = replay(args.replay)
        else:
            path, m = run()
        print(json.dumps({'status': 'pass', 'scope': m['scope'], 'release_claim': False,
                          'execution_performed': not bool(args.audit),
                          'recorded_positive_processes': 2, 'recorded_noop_controls': 1,
                          'application_sha256': m['files']['default.exe']}))
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        print(json.dumps({'status': 'fail', 'reason': 'relaxed_nvcc_diagnostic_failed'}))
        raise SystemExit(1)
