"""Independent native nested-stack/other-thread context destruction regression."""
import argparse
import ctypes
import json
from pathlib import Path
import subprocess
from p05a_primary_check import ROOT, digest, prepare_bundle


def run(app, dll):
    before = app.read_bytes()
    bundle, _ = prepare_bundle(app, dll, [], ROOT / '.cache/runs')
    result = subprocess.run([str(bundle / app.name)], cwd=bundle, capture_output=True, timeout=90)
    assert app.read_bytes() == before == (bundle / app.name).read_bytes()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('artifacts', type=Path)
    parser.add_argument('--baseline-dll', type=Path)
    args = parser.parse_args()
    ctypes.windll.kernel32.SetErrorMode(0x8007)
    folder = (ROOT / args.artifacts).resolve()
    assert folder.is_relative_to(ROOT / '.cache/p05d-build')
    app = folder / 'host.exe'
    baseline = None
    if args.baseline_dll:
        dll = (ROOT / args.baseline_dll).resolve()
        assert dll.is_relative_to(ROOT / '.cache')
        old = run(app, dll)
        assert old.returncode == 3 and b'duplicate stack entry was removed' in old.stderr
        baseline = dict(sha256=digest(dll.read_bytes()), outcome='duplicate_stack_removal')
    result = run(app, ROOT / 'target/debug/ct_cuda.dll')
    assert result.returncode == 0, result.stderr.decode(errors='replace')
    assert json.loads(result.stdout) == dict(status='pass', cases=3, threads=2, memory_checks=3)
    print(json.dumps(dict(status='pass', cases=3, threads=2, memory_checks=3,
        unchanged_application=True, application_sha256=digest(app.read_bytes()), baseline=baseline)))


if __name__ == '__main__':
    main()
