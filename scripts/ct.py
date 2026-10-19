"""Experimental process-local CUDA Driver application connection (Windows x64)."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile

REPO = Path(__file__).resolve().parents[1]
MAX_IMAGE = 64 * 1024 * 1024


class LoaderError(Exception):
    """Messages are static categories, never application paths or source text."""


class PrivateArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise LoaderError("invalid command line; use --help")


def supported_symbols():
    header = (REPO / "include/ct_cuda.h").read_text(encoding="utf-8")
    return set(re.findall(r" X\((cu\w+),", header))


def inspect_pe(data, *, dll=False):
    def require(ok):
        if not ok:
            raise LoaderError("malformed or unsupported PE image")

    def unpack(fmt, offset):
        require(0 <= offset <= len(data) - struct.calcsize(fmt))
        return struct.unpack_from(fmt, data, offset)

    require(64 <= len(data) <= MAX_IMAGE and data[:2] == b"MZ")
    pe, = unpack("<I", 60)
    require(pe >= 64 and data[pe:pe + 4] == b"PE\0\0")
    machine, sections, _, _, _, optional_size, flags = unpack("<HHIIIHH", pe + 4)
    require(machine == 0x8664 and bool(flags & 0x2000) == dll and flags & 2)
    require(1 <= sections <= 96 and optional_size >= 112)
    opt = pe + 24
    magic, = unpack("<H", opt)
    require(magic == 0x20b and opt + optional_size <= len(data))
    headers, = unpack("<I", opt + 60)
    count, = unpack("<I", opt + 108)
    require(count <= 16 and 112 + count * 8 <= optional_size)
    table = opt + optional_size
    require(table + sections * 40 <= headers <= len(data))
    mappings = []
    for i in range(sections):
        virtual_size, rva, size, raw = unpack("<IIII", table + i * 40 + 8)
        require(raw + size <= len(data) and rva + max(size, virtual_size) <= 1 << 32)
        if size:
            require(raw >= headers)
        for start, end, _ in mappings:
            require(rva + size <= start or rva >= end)
        mappings.append((rva, rva + size, raw))

    def locate(rva, size):
        require(rva > 0 and size >= 0 and rva + size <= 1 << 32)
        if rva < headers:
            require(rva + size <= headers)
            return rva
        for start, end, raw in mappings:
            if start <= rva and rva + size <= end:
                return raw + rva - start
        raise LoaderError("unmapped PE address")

    def string(rva):
        out = bytearray()
        for i in range(512):
            b = data[locate(rva + i, 1)]
            if b == 0:
                require(bool(out) and all(32 <= c < 127 for c in out))
                return out.decode("ascii")
            out.append(b)
        raise LoaderError("oversized PE import name")

    def directory(index):
        return unpack("<II", opt + 112 + index * 8) if index < count else (0, 0)

    require(directory(13) == (0, 0))  # delay imports need a separate contract
    require(directory(14) == (0, 0))  # no managed assemblies
    imports = []
    import_rva, import_size = directory(1)
    if import_rva or import_size:
        require(import_rva != 0 and 20 <= import_size <= 20 * 1024)
        locate(import_rva, import_size)
        terminated = False
        for i in range(import_size // 20):
            descriptor = unpack("<IIIII", locate(import_rva + i * 20, 20))
            if not any(descriptor):
                terminated = True
                break
            original, _, _, name_rva, first = descriptor
            name = string(name_rva)
            require("/" not in name and "\\" not in name and ":" not in name)
            lower = name.lower()
            if lower.startswith("cudart"):
                raise LoaderError("CUDA Runtime imports are unsupported")
            names = []
            for j in range(4096):
                locate(first + j * 8, 8)  # IAT must exist even with a separate lookup table.
                thunk, = unpack("<Q", locate((original or first) + j * 8, 8))
                if thunk == 0:
                    break
                if thunk & (1 << 63):
                    if lower == "nvcuda.dll":
                        raise LoaderError("ordinal CUDA imports are unsupported")
                    names.append("ordinal")
                else:
                    require(thunk <= 0xffffffff)
                    locate(thunk, 2)
                    names.append(string(thunk + 2))
            else:
                raise LoaderError("oversized PE import table")
            if lower == "nvcuda.dll" and not set(names) <= supported_symbols():
                raise LoaderError("unsupported static CUDA symbol")
            imports.append({"library": name, "symbols": names})
        require(terminated)
    return {"architecture": "x64", "cuda_loading": "static" if any(
        i["library"].lower() == "nvcuda.dll" for i in imports) else "dynamic-or-none",
        "imports": imports, "compatibility": "unproven"}


def read_image(path):
    with path.open("rb") as f:
        data = f.read(MAX_IMAGE + 1)
    if len(data) > MAX_IMAGE:
        raise LoaderError("image exceeds inspection limit")
    return data


def digest(data):
    return hashlib.sha256(data).hexdigest()


def prepare_bundle(application, ct_dll, assets, root):
    application, ct_dll = Path(application), Path(ct_dll)
    if application.suffix.lower() != ".exe":
        raise LoaderError("application must be an executable")
    app_data, dll_data = read_image(application), read_image(ct_dll)
    report = inspect_pe(app_data)
    inspect_pe(dll_data, dll=True)
    payloads = {application.name: app_data, "nvcuda.dll": dll_data}
    names = {n.casefold() for n in payloads}
    if len(names) != 2:
        raise LoaderError("bundle filename collision")
    for asset in assets:
        asset = Path(asset)
        if asset.suffix.lower() not in (".ptx", ".fatbin") or asset.name.casefold() in names:
            raise LoaderError("assets must be distinct PTX text files")
        names.add(asset.name.casefold())
        data = read_image(asset)
        if len(data) > 262144 or b"\0" in data:
            raise LoaderError("unsupported PTX asset size or encoding")
        if asset.suffix.lower() == ".fatbin":
            if not data.isascii() or not re.search(rb"(?m)^\s*\.version\s+[0-9]+\.[0-9]+", data):
                raise LoaderError("only PTX text is accepted under a fatbin filename")
        payloads[asset.name] = data
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    bundle = Path(tempfile.mkdtemp(prefix="ct-", dir=root))
    for name, data in payloads.items():
        destination = bundle / name
        with destination.open("xb") as f:
            f.write(data)
        if destination.read_bytes() != data:
            raise LoaderError("bundle byte verification failed")
    report.update(application_sha256=digest(app_data), ct_sha256=digest(dll_data),
                  assets_sha256=[digest(payloads[Path(p).name]) for p in assets])
    return bundle, report


def run_child(application, arguments, cwd):
    return subprocess.run([str(application), *arguments], cwd=cwd, shell=False, check=False).returncode


def main():
    parser = PrivateArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="triage PE imports; no compatibility guarantee")
    inspect.add_argument("application", type=Path)
    run = commands.add_parser("run", help="execute a trusted standalone application through CT")
    run.add_argument("--ct-dll", type=Path, required=True)
    run.add_argument("--ptx", type=Path, action="append", default=[])
    run.add_argument("application", type=Path)
    run.add_argument("arguments", nargs=argparse.REMAINDER)
    try:
        args = parser.parse_args()
        if args.command == "inspect":
            print(json.dumps(inspect_pe(read_image(args.application)), ensure_ascii=True))
            return 0
        if os.name != "nt":
            raise LoaderError("application connection requires Windows x64")
        bundle, report = prepare_bundle(args.application, args.ct_dll, args.ptx, REPO / ".cache/runs")
        print(json.dumps({"stage": "CT-application-connection", **report}), flush=True)
        arguments = args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
        return run_child(bundle / args.application.name, arguments, bundle)
    except (LoaderError, OSError) as error:
        message = str(error) if isinstance(error, LoaderError) else "file or process operation failed"
        print(json.dumps({"status": "error", "reason": message}), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
