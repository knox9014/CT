"""Run unchanged independent primary-context consumers in process-local bundles."""
import argparse
import ctypes
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from ct import digest, inspect_pe, prepare_bundle


def run_consumer(app, dll, ptx):
    before = digest(app.read_bytes())
    bundle, record = prepare_bundle(app, dll, [ptx], ROOT / '.cache/runs')
    result = subprocess.run([str(bundle / app.name), ptx.name], cwd=bundle,
                            capture_output=True, timeout=90)
    assert digest(app.read_bytes()) == before == record['application_sha256']
    assert digest((bundle / app.name).read_bytes()) == before
    assert (bundle / ptx.name).read_bytes() == ptx.read_bytes()
    return result, before


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('artifacts', type=Path)
    parser.add_argument('--baseline-dll', type=Path)
    args = parser.parse_args()
    ctypes.windll.kernel32.SetErrorMode(0x8007)
    artifacts = (ROOT / args.artifacts).resolve()
    assert artifacts.is_relative_to(ROOT / '.cache/p05a-build')
    ptx = ROOT / 'tests/fixtures/vector_add.ptx'
    baseline = None
    if args.baseline_dll:
        path = (ROOT / args.baseline_dll).resolve()
        assert path.is_relative_to(ROOT / '.cache')
        result, _ = run_consumer(artifacts / 'p05a_dynamic.exe', path, ptx)
        assert result.returncode == 42, 'pre-feature DLL must reject missing primary exports'
        baseline = dict(sha256=digest(path.read_bytes()), outcome='missing_exports')
    hashes = []
    for mode in ('static', 'dynamic'):
        app = artifacts / ('p05a_' + mode + '.exe')
        assert inspect_pe(app.read_bytes())['cuda_loading'] == (
            'static' if mode == 'static' else 'dynamic-or-none')
        result, app_hash = run_consumer(app, ROOT / 'target/debug/ct_cuda.dll', ptx)
        assert result.returncode == 0, result.stderr.decode(errors='replace')
        assert json.loads(result.stdout) == dict(status='pass', threads=2,
            results=514, guards=128, primary_lifecycle=True)
        hashes.append(app_hash)
    print(json.dumps(dict(status='pass', loading_modes=2, threads_per_consumer=2,
        results=1028, guards=256, application_sha256=hashes,
        unchanged_application_and_ptx=True, baseline=baseline)))


if __name__ == '__main__':
    main()
