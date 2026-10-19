"""Pinned upstream source + real NVRTC PTX; vendor files and raw output stay local."""
import ctypes as c
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from ct import digest, prepare_bundle

REFERENCE = REPO / ".cache/reference"
VENDOR = REPO / ".cache/vendor/cuda-samples-12.0"
COMMIT = "2b689228b746248b7bb7d2778d5ea0701669f7d3"
SAMPLE = VENDOR / "Samples/0_Introduction/vectorAddDrv"
ASSET = REFERENCE / "vectorAdd_kernel64.fatbin"
PACKAGES = (
    ("nvidia_cuda_runtime_cu12-12.0.107-py3-none-win_amd64.whl", "f595d66142e9ba5d1157d73ef06488735d814415a462714426f3989344e675eb", "cuda-12.0"),
    ("nvidia_cuda_nvrtc_cu12-12.0.76-py3-none-win_amd64.whl", "e6a0649a8519f49847ea636b2043dfe65d6cb4c3104ed12b69eb14c1413e5c1a", "nvrtc-12.0"),
    ("nvidia_cuda_nvcc_cu12-12.0.76-py3-none-win_amd64.whl", "135809154702a6302713391d3b78b9f6b4584157f539103dbd2b1d5e5922a225", "cuda-12.0"),
)


def verify_source():
    command = ["git", "-C", str(VENDOR)]
    head = subprocess.check_output([*command, "rev-parse", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
    if head != COMMIT or subprocess.run([*command, "diff", "--quiet", "HEAD", "--", "Common", "Samples/0_Introduction/vectorAddDrv"], capture_output=True).returncode:
        raise RuntimeError("official source revision or working files changed")


def prepare():
    verify_source()
    for filename, expected, directory in PACKAGES:
        wheel = REFERENCE / filename
        if digest(wheel.read_bytes()) != expected:
            raise RuntimeError("unexpected NVIDIA package hash")
        with zipfile.ZipFile(wheel) as archive:
            for name in archive.namelist():
                parts = Path(name).parts
                if name.endswith("/") or ".." in parts or len(parts) < 4:
                    continue
                if parts[2] not in ("include", "bin"):
                    continue
                destination = REFERENCE / directory / Path(*parts[2:])
                if not destination.resolve().is_relative_to((REFERENCE / directory).resolve()):
                    raise RuntimeError("unexpected archive entry")
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.read(name))
    dll = REFERENCE / "nvrtc-12.0/bin/nvrtc64_120_0.dll"
    with os.add_dll_directory(str(dll.parent)):
        builtins = c.WinDLL(str(dll.parent / "nvrtc-builtins64_120.dll"))
        compiler = c.WinDLL(str(dll))
        compiler.nvrtcCreateProgram.argtypes = [c.POINTER(c.c_void_p), c.c_char_p, c.c_char_p, c.c_int, c.c_void_p, c.c_void_p]
        compiler.nvrtcCompileProgram.argtypes = [c.c_void_p, c.c_int, c.POINTER(c.c_char_p)]
        compiler.nvrtcGetPTXSize.argtypes = [c.c_void_p, c.POINTER(c.c_size_t)]
        compiler.nvrtcGetPTX.argtypes = [c.c_void_p, c.c_void_p]
        compiler.nvrtcDestroyProgram.argtypes = [c.POINTER(c.c_void_p)]
        program = c.c_void_p()
        source = (SAMPLE / "vectorAdd_kernel.cu").read_bytes()
        if compiler.nvrtcCreateProgram(c.byref(program), source, b"vectorAdd_kernel.cu", 0, None, None):
            raise RuntimeError("NVRTC program creation failed")
        try:
            options = (c.c_char_p * 2)(b"--gpu-architecture=compute_52", b"--std=c++11")
            if compiler.nvrtcCompileProgram(program, 2, options):
                raise RuntimeError("NVRTC compilation failed")
            size = c.c_size_t()
            if compiler.nvrtcGetPTXSize(program, c.byref(size)) or size.value > 262144:
                raise RuntimeError("NVRTC output size failed")
            output = c.create_string_buffer(size.value)
            if compiler.nvrtcGetPTX(program, output):
                raise RuntimeError("NVRTC output failed")
            ASSET.write_bytes(output.raw[:-1])
        finally:
            compiler.nvrtcDestroyProgram(c.byref(program))
        assert builtins  # Keep explicitly loaded compiler dependency alive.
    print(json.dumps({"status": "prepared", "upstream": COMMIT, "ptx_sha256": digest(ASSET.read_bytes())}))


def run(build):
    verify_source()
    artifacts = (REPO / build).resolve()
    assert artifacts.is_relative_to(REPO / ".cache/m3c-build")
    application = artifacts / "vectorAddDrv.exe"
    original = digest(application.read_bytes())
    bundle, report = prepare_bundle(application, REPO / "target/debug/ct_cuda.dll", [ASSET], REPO / ".cache/runs")
    result = subprocess.run([str(bundle / application.name), "--device=0"], cwd=bundle, capture_output=True, timeout=60)
    logs = REPO / "results/local"
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "m3c-upstream-output.log").write_bytes(result.stdout + result.stderr)
    if result.returncode or b"Result = PASS" not in result.stdout:
        codes = re.findall(rb"(?:code|error)\s*=\s*(\d+)", result.stderr)
        print(json.dumps({"status": "failure", "exit": result.returncode, "cuda_errors": [int(v) for v in codes]}))
        raise RuntimeError("upstream sample did not pass; raw output remains local")
    assert original == report["application_sha256"] == digest(application.read_bytes())
    assert (bundle / ASSET.name).read_bytes() == ASSET.read_bytes()
    from m3c_gpu_validation import validate
    independent = validate(ASSET.read_bytes())
    print(json.dumps({"status": "pass", "sample": "NVIDIA vectorAddDrv", "elements": 50000,
        "unchanged_host_source": True, "unchanged_kernel_source": True,
        "unchanged_application_and_compiled_ptx": True, "application_sha256": original,
        "ptx_sha256": digest(ASSET.read_bytes()), "independent_gpu_checks": independent,
        "packaging": "PTX text under expected fatbin filename"}))


if __name__ == "__main__":
    try:
        if sys.argv[1] == "prepare": prepare()
        elif sys.argv[1] == "run": run(sys.argv[2])
        else: raise RuntimeError("unknown test phase")
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "error", "reason": str(error) if isinstance(error, RuntimeError) else "local preparation or execution failed"}))
        raise SystemExit(1)
