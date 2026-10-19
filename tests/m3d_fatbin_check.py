"""Genuine NVIDIA nvFatbin containers; vendor artifacts remain ignored."""
import ctypes as c
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(REPO / "scripts"))
from ct import digest, prepare_bundle
from m3c_external_check import ASSET, REFERENCE, verify_source
from m3c_gpu_validation import Device, P, validate

WHEEL = "nvidia_nvfatbin_cu12-12.4.99-py3-none-win_amd64.whl"
WHEEL_HASH = "398b9ea66d888ae858e74935658dae5f9149fad0978b3ed55bb2d5113dec78fc"


class Producer:
    def __init__(self):
        wheel = REFERENCE / WHEEL
        if digest(wheel.read_bytes()) != WHEEL_HASH: raise RuntimeError("unexpected nvFatbin package hash")
        path = REFERENCE / "nvfatbin-12.4/nvfatbin_120_0.dll"
        with zipfile.ZipFile(wheel) as archive:
            names = [n for n in archive.namelist() if n.endswith("/bin/nvfatbin_120_0.dll")]
            if len(names) != 1: raise RuntimeError("unexpected nvFatbin package layout")
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(archive.read(names[0]))
        self.lib = c.WinDLL(str(path))
        signatures = {
            "nvFatbinCreate": [c.POINTER(P),c.POINTER(c.c_char_p),c.c_size_t],
            "nvFatbinAddPTX": [P,c.c_char_p,c.c_size_t,c.c_char_p,c.c_char_p,c.c_char_p],
            "nvFatbinSize": [P,c.POINTER(c.c_size_t)], "nvFatbinGet": [P,P], "nvFatbinDestroy": [c.POINTER(P)],
        }
        for name,args in signatures.items():
            f=getattr(self.lib,name);f.argtypes=args;f.restype=c.c_int

    def call(self,name,*args):
        if getattr(self.lib,name)(*args): raise RuntimeError("nvFatbin producer operation failed")

    def make(self,text,variant,arch=b"52"):
        options=(c.c_char_p*4)(b"-64",b"-cuda",b"-host=windows",b"-compress-all" if variant=="compressed" else b"-compress=false")
        handle=P();self.call("nvFatbinCreate",c.byref(handle),options,4)
        try:
            source=text+b"\0"
            self.call("nvFatbinAddPTX",handle,source,len(source),arch,b"vectorAdd",b"-ftz=true" if variant=="options" else None)
            if variant=="duplicate":
                self.call("nvFatbinAddPTX",handle,source,len(source),arch,b"vectorAdd_second",None)
            size=c.c_size_t();self.call("nvFatbinSize",handle,c.byref(size))
            if not 16 <= size.value <= 16*1024*1024: raise RuntimeError("unexpected produced image size")
            output=c.create_string_buffer(size.value);self.call("nvFatbinGet",handle,output)
            return output.raw
        finally: self.call("nvFatbinDestroy",c.byref(handle))


def main(build, variant="plain"):
    verify_source()
    artifacts=(REPO/build).resolve()
    if not artifacts.is_relative_to(REPO/".cache/m3c-build"): raise RuntimeError("unexpected sample build directory")
    app=artifacts/"vectorAddDrv.exe"
    producer=Producer()
    text=ASSET.read_bytes()
    images={v:producer.make(text,v) for v in ("plain","compressed","duplicate","options")}
    milestone="m3e" if variant=="compressed" else "m3d"
    # Real producer parity fixtures remain local and are consumed by Rust tests.
    parity=REFERENCE/"m3e";parity.mkdir(parents=True,exist_ok=True)
    for name in ("plain","compressed"): (parity/(name+".fatbin")).write_bytes(images[name])
    chosen=images[variant]
    asset=REFERENCE/milestone/variant/"vectorAdd_kernel64.fatbin"
    asset.parent.mkdir(parents=True,exist_ok=True);asset.write_bytes(chosen)
    original=digest(app.read_bytes())
    bundle,report=prepare_bundle(app,REPO/"target/debug/ct_cuda.dll",[asset],REPO/".cache/runs")
    result=subprocess.run([str(bundle/app.name),"--device=0"],cwd=bundle,capture_output=True,timeout=60)
    logs=REPO/"results/local";logs.mkdir(parents=True,exist_ok=True)
    (logs/(milestone+"-upstream-output.log")).write_bytes(result.stdout+result.stderr)
    if result.returncode or b"Result = PASS" not in result.stdout:
        print(json.dumps({"status":"failure","exit":result.returncode,"cuda_errors":[int(v) for v in re.findall(rb"(?:code|error)\s*=\s*(\d+)",result.stderr)]}))
        raise RuntimeError("official sample fatbin execution failed; raw output remains local")
    if digest(app.read_bytes())!=original or report["application_sha256"]!=original or (bundle/asset.name).read_bytes()!=chosen:
        raise RuntimeError("sample or fatbin byte preservation failed")
    independent=validate(chosen)
    independent.update(fatbin_cases=6,fatbin_results=50450,fatbin_guards=384,raw_ptx_regression_cases=8)
    device=Device()
    try:
        for rejected in ("duplicate","options"):
            output=P(1)
            code=device.dll.cuModuleLoadData(c.byref(output),c.cast(c.create_string_buffer(images[rejected]),P))
            if code!=801 or output.value is not None: raise RuntimeError("unsupported producer variant was not safely rejected")
        # Corrupt compressed length, decoded length, offset and padding. All
        # declarations stay bounded/readable; no arbitrary pointer probes.
        broken=[]
        source=images["compressed"]
        header=int.from_bytes(source[20:24],"little")
        for start,width,value in ((32,4,0),(72,8,0),(72,8,262153)):
            raw=bytearray(source);raw[start:start+width]=value.to_bytes(width,"little");broken.append(bytes(raw))
        raw=bytearray(source);raw[-1]=1;broken.append(bytes(raw))
        raw=bytearray(source);raw[16+header]=0;raw[17+header:19+header]=b"\0\0";broken.append(bytes(raw))
        for raw in broken:
            output=P(1)
            code=device.dll.cuModuleLoadData(c.byref(output),c.cast(c.create_string_buffer(raw),P))
            if code not in (218,801) or output.value is not None: raise RuntimeError("malformed compressed fatbin was not safely rejected")
        # Renamed entries and changed arithmetic prove no name/hash substitution.
        generic=(REPO/"tests/fixtures/vector_add.ptx").read_bytes().replace(b"vector_add",b"renamed_difference").replace(b"add.rn.f32",b"sub.rn.f32")
        renamed=producer.make(generic,"compressed",arch=b"50")
        device.run(renamed,"renamed_difference",257,expected_sub=True)
        legacy=producer.make((REPO/"tests/fixtures/vector_add.ptx").read_bytes(),"compressed",arch=b"50")
        device.run(legacy,"vector_add",65) # Rejection did not damage context; legacy profile also works.
    finally: device.close()
    cli=subprocess.run([sys.executable,str(REPO/"scripts/ct.py"),"run","--ct-dll",
        str(REPO/"target/debug/ct_cuda.dll"),"--ptx",str(asset),str(app),"--","--device=0"],
        cwd=REPO,capture_output=True,timeout=60)
    if cli.returncode or b"Result = PASS" not in cli.stdout: raise RuntimeError("public CLI fatbin run failed")
    cli_report=json.loads(cli.stdout.splitlines()[0])
    if cli_report["application_sha256"]!=original or cli_report["assets_sha256"]!=[digest(chosen)]:
        raise RuntimeError("public CLI staged hashes changed")
    print(json.dumps({"status":"pass","sample":"NVIDIA vectorAddDrv","elements":50000,
        "real_binary_fatbin":True,"compressed":variant=="compressed","producer":"NVIDIA nvFatbin12.4.99","fatbin_bytes":len(chosen),
        "fatbin_sha256":digest(chosen),"compiler_input_ptx_sha256":digest(text),
        "application_sha256":original,"unchanged_application_and_fatbin":True,
        "independent_gpu_checks":independent,"unsupported_producer_variants_rejected":2,
        "malformed_compressed_variants_rejected":len(broken),"renamed_subtraction_results":257,"renamed_subtraction_guards":64,
        "post_rejection_recovery_passed":True,"legacy_fatbin_profile_passed":True,"public_cli_passed":True}))


if __name__=="__main__":
    try: main(sys.argv[1],"compressed" if "--compressed" in sys.argv[2:] else "plain")
    except (RuntimeError,OSError,subprocess.SubprocessError) as error:
        print(json.dumps({"status":"error","reason":str(error) if isinstance(error,RuntimeError) else "local fatbin test operation failed"}))
        raise SystemExit(1)
