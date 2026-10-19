"""Real native CUDA-loading smoke test; generated files remain ignored."""
import ctypes
import json
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from ct import digest, inspect_pe, prepare_bundle


def main():
    ctypes.windll.kernel32.SetErrorMode(0x8007)
    artifacts = (REPO / sys.argv[1]).resolve()
    assert artifacts.is_relative_to(REPO / ".cache/m3-build")
    dll = REPO / "target/debug/ct_cuda.dll"
    ptx = REPO / "tests/fixtures/vector_add.ptx"
    # Ordinary dynamic loading without a local CT copy must fail on this Intel-only machine.
    baseline = subprocess.run([str(artifacts / "m3_dynamic.exe"), ptx.name],
                              cwd=artifacts, capture_output=True, timeout=30)
    assert baseline.returncode == 41, "baseline is not the expected driver-unavailable environment"
    hashes = []
    for mode in ("static", "dynamic"):
        app = artifacts / f"m3_{mode}.exe"
        before = digest(app.read_bytes())
        triage = inspect_pe(app.read_bytes())
        assert triage["cuda_loading"] == ("static" if mode == "static" else "dynamic-or-none")
        bundle, report = prepare_bundle(app, dll, [ptx], REPO / ".cache/runs")
        assert digest((bundle / app.name).read_bytes()) == before == report["application_sha256"]
        assert (bundle / ptx.name).read_bytes() == ptx.read_bytes()
        # Use the actual public CLI, not an explicit CT path inside the consumer.
        result = subprocess.run([sys.executable, str(REPO / "scripts/ct.py"), "run",
            "--ct-dll", str(dll), "--ptx", str(ptx), str(app), "--", ptx.name],
            cwd=REPO, capture_output=True, timeout=60)
        assert result.returncode == 0, "CUDA connection execution failed"
        lines = [json.loads(line) for line in result.stdout.decode().splitlines()]
        assert lines[-1] == {"status": "pass", "results": 257, "guards": 64, "application_local_driver": True}
        assert lines[0]["application_sha256"] == before
        assert digest(app.read_bytes()) == before
        hashes.append(before)
    print(json.dumps({"status": "pass", "loading_modes": 2, "results": 514, "guards": 128,
        "unchanged_application_and_ptx": True, "baseline_without_driver": "unavailable",
        "application_sha256": hashes}))


if __name__ == "__main__":
    main()
