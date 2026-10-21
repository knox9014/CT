"""Explicit test-only dependency bundle; no public automatic-DLL-packaging claim."""
import argparse
import ctypes
import json
from pathlib import Path
import subprocess

from p05a_primary_check import ROOT, digest, inspect_pe, prepare_bundle


def run_bundle(folder, dll, consumer_override=None):
    app = folder / 'host.exe'
    assets = {'producer.dll': folder / 'producer.dll',
              'consumer.dll': consumer_override or folder / 'consumer.dll'}
    originals = {name: p.read_bytes() for name, p in {app.name: app, **assets}.items()}
    ptx = ROOT / 'tests/fixtures/vector_add.ptx'
    bundle, _ = prepare_bundle(app, dll, [ptx], ROOT / '.cache/runs')
    for name in assets:
        with (bundle / name).open('xb') as output:
            output.write(originals[name])
    result = subprocess.run([str(bundle / app.name), ptx.name], cwd=bundle,
                            capture_output=True, timeout=90)
    for name, raw in originals.items():
        assert (assets.get(name, app)).read_bytes() == raw == (bundle / name).read_bytes()
    assert (bundle / ptx.name).read_bytes() == ptx.read_bytes()
    return result, {name: digest(raw) for name, raw in originals.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('artifacts', type=Path)
    parser.add_argument('--baseline-dll', type=Path)
    args = parser.parse_args()
    ctypes.windll.kernel32.SetErrorMode(0x8007)
    folder = (ROOT / args.artifacts).resolve()
    assert folder.is_relative_to(ROOT / '.cache/p05c-build')
    for name, mode in [('host.exe', 'dynamic-or-none'), ('producer.dll', 'static'),
                       ('consumer.dll', 'dynamic-or-none')]:
        assert inspect_pe((folder / name).read_bytes(), dll=name.endswith('.dll'))['cuda_loading'] == mode
    baseline = None
    if args.baseline_dll:
        old = (ROOT / args.baseline_dll).resolve()
        assert old.is_relative_to(ROOT / '.cache')
        result, _ = run_bundle(folder, old)
        assert result.returncode == 42, 'old DLL must reject new flag exports'
        baseline = dict(sha256=digest(old.read_bytes()), outcome='missing_exports')
    result, hashes = run_bundle(folder, ROOT / 'target/debug/ct_cuda.dll')
    assert result.returncode == 0, result.stderr.decode(errors='replace')
    assert json.loads(result.stdout) == dict(status='pass', libraries=2,
        results=514, guards=128, shared_driver=True)
    broken, _ = run_bundle(folder, ROOT / 'target/debug/ct_cuda.dll', folder / 'consumer-noop.dll')
    assert broken.returncode == 3, 'skipping the post-unload kernel must fail numerical checks'
    assert b'consumer output mismatch at execution 2' in broken.stderr
    print(json.dumps(dict(status='pass', libraries=2, results=514, guards=128,
        unchanged_application_libraries_and_ptx=True, artifact_sha256=hashes,
        baseline=baseline, negative_noop_rejected=True, automatic_public_dependency_packaging=False)))


if __name__ == '__main__':
    main()
