"""Real native CUDA-loading smoke test; generated files remain ignored."""
import ctypes
import json
import os
from pathlib import Path
import re
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from ct import digest, inspect_pe, prepare_bundle


def main():
    ctypes.windll.kernel32.SetErrorMode(0x8007)
    artifacts = (REPO / sys.argv[1]).resolve()
    assert artifacts.is_relative_to(REPO / ".cache/m3-build")
    target = REPO / ".cache/m3-device-target/debug"
    dll = target / "ct_cuda.dll"
    ptx = REPO / "tests/fixtures/vector_add.ptx"
    env = os.environ.copy()
    env.pop("CT_M3_DEVICE_UUID", None)
    env.pop("CT_M3_CAPTURE_DEVICE", None)
    smoke = subprocess.run(
        [str(target / "ct-intel-smoke.exe"), str(REPO / "tests/fixtures/vector_add.spv"), *sys.argv[2:]],
        cwd=REPO, env={**env, "CT_M3_CAPTURE_DEVICE": "1"}, capture_output=True, timeout=60,
    )
    assert smoke.returncode == 0, "Intel GPU selection or native calculation failed"
    selection = json.loads(smoke.stdout)
    uuid = selection["selected_uuid"]
    assert re.fullmatch(r"[0-9a-f]{32}", uuid) and uuid != "0" * 32, "GPU UUID unavailable"
    native_report = selection["report"]
    assert native_report["status"] == "pass"
    # The control observes DLL lookup. The consumer exits before calling a nonlocal driver.
    baseline_code = None
    try:
        baseline = subprocess.run(
            [str(artifacts / "m3_dynamic.exe"), ptx.name],
            cwd=artifacts, env=env, capture_output=True, timeout=30,
        )
        baseline_code = baseline.returncode
    except (OSError, subprocess.TimeoutExpired):
        pass
    baseline_status = {
        41: "unavailable",
        5: "nonlocal-driver",
    }.get(baseline_code, "inconclusive")
    hashes = []
    device_names = []
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
            cwd=REPO, env={**env, "CT_M3_DEVICE_UUID": uuid}, capture_output=True, timeout=60)
        assert result.returncode == 0, "CUDA connection execution failed"
        lines = [json.loads(line) for line in result.stdout.decode().splitlines()]
        observation = lines[-1]
        device_name = bytes.fromhex(observation.pop("device_name_hex")).decode("utf-8")
        assert device_name and "\0" not in device_name
        device_names.append(device_name)
        assert observation.pop("device_verified") is True, "CUDA context device was not verified"
        assert observation == {"status": "pass", "results": 257, "guards": 64, "application_local_driver": True}
        assert lines[0]["application_sha256"] == before
        assert digest(app.read_bytes()) == before
        hashes.append(before)
    assert all(name == native_report["device"] for name in device_names), "GPU names differ across tests"
    print(json.dumps({"status": "pass", "loading_modes": 2, "results": 514, "guards": 128,
        "device": device_names[0], "same_device_verified": True,
        "driver_version_raw": native_report["driver_version_raw"],
        "unchanged_application_and_ptx": True, "baseline_without_driver": baseline_status,
        "baseline_exit_code": baseline_code,
        "application_sha256": hashes}))


if __name__ == "__main__":
    main()
