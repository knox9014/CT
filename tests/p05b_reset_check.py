"""Native reset consumer with preserved application/PTX bytes and optional baseline."""
import argparse
import ctypes
import json
from pathlib import Path

from p05a_primary_check import ROOT, digest, inspect_pe, run_consumer


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('artifacts', type=Path)
    parser.add_argument('--baseline-dll', type=Path)
    args = parser.parse_args()
    ctypes.windll.kernel32.SetErrorMode(0x8007)
    artifacts = (ROOT / args.artifacts).resolve()
    assert artifacts.is_relative_to(ROOT / '.cache/p05b-build')
    ptx = ROOT / 'tests/fixtures/vector_add.ptx'
    baseline = None
    if args.baseline_dll:
        path = (ROOT / args.baseline_dll).resolve()
        assert path.is_relative_to(ROOT / '.cache')
        result, _ = run_consumer(artifacts / 'p05b_dynamic.exe', path, ptx)
        assert result.returncode == 42, 'pre-reset DLL must reject missing export'
        baseline = dict(sha256=digest(path.read_bytes()), outcome='missing_exports')
    hashes = []
    for mode in ('static', 'dynamic'):
        app = artifacts / ('p05b_' + mode + '.exe')
        assert inspect_pe(app.read_bytes())['cuda_loading'] == (
            'static' if mode == 'static' else 'dynamic-or-none')
        result, app_hash = run_consumer(app, ROOT / 'target/debug/ct_cuda.dll', ptx)
        assert result.returncode == 0, result.stderr.decode(errors='replace')
        assert json.loads(result.stdout) == dict(status='pass', threads=2,
            results=514, guards=128, reset_preserves_usage=True)
        hashes.append(app_hash)
    print(json.dumps(dict(status='pass', loading_modes=2, threads_per_consumer=2,
        results=1028, guards=256, application_sha256=hashes,
        unchanged_application_and_ptx=True, baseline=baseline)))


if __name__ == '__main__':
    main()
