"""Execute an NVIDIA-header-only consumer through CT's versioned resolvers."""
import json
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from ct import digest, prepare_bundle


def main():
    artifacts = (REPO / sys.argv[1]).resolve()
    assert artifacts.is_relative_to(REPO / ".cache/m3b-build")
    app = artifacts / "m3b_cuda.exe"
    ptx = REPO / "tests/fixtures/vector_add.ptx"
    dll = REPO / "target/debug/ct_cuda.dll"
    original = digest(app.read_bytes())
    total_queries = 0
    for mode in ("v1", "v2"):
        bundle, report = prepare_bundle(app, dll, [ptx], REPO / ".cache/runs")
        assert report["application_sha256"] == original
        assert (bundle / ptx.name).read_bytes() == ptx.read_bytes()
        result = subprocess.run([sys.executable, str(REPO / "scripts/ct.py"), "run", "--ct-dll",
            str(dll), "--ptx", str(ptx), str(app), "--", ptx.name, mode],
            cwd=REPO, capture_output=True, timeout=60)
        assert result.returncode == 0, f"resolver {mode} execution failed (exit {result.returncode})"
        output = [json.loads(line) for line in result.stdout.decode().splitlines()]
        assert output[0]["application_sha256"] == original
        assert output[-1] == {"status": "pass", "resolver": mode, "queries": 40, "results": 257, "guards": 64}
        total_queries += output[-1]["queries"]
    assert digest(app.read_bytes()) == original
    print(json.dumps({"status": "pass", "resolver_modes": 2, "queries": total_queries,
        "results": 514, "guards": 128, "official_cuda_headers": True,
        "unchanged_application_and_ptx": True, "application_sha256": original}))


if __name__ == "__main__":
    main()
