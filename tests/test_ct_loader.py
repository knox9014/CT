"""Synthetic PE images; no personal application binaries are stored in Git."""
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ct import LoaderError, inspect_pe, prepare_bundle, run_child


def image(symbol=b"cuInit", library=b"nvcuda.dll", ordinal=False, dll=False):
    data = bytearray(2048)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 60, 128)
    data[128:132] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", data, 132, 0x8664, 1, 0, 0, 0, 240,
                     0x2022 if dll else 0x22)
    struct.pack_into("<H", data, 152, 0x20b)
    struct.pack_into("<I", data, 212, 512)  # SizeOfHeaders
    struct.pack_into("<I", data, 260, 16)
    struct.pack_into("<II", data, 272, 0x1000, 40)
    struct.pack_into("<IIII", data, 400, 1536, 0x1000, 1536, 512)
    struct.pack_into("<IIIII", data, 512, 0x1080, 0, 0, 0x1060, 0x1080)
    data[608:608 + len(library) + 1] = library + b"\0"
    struct.pack_into("<Q", data, 640, (1 << 63 | 3) if ordinal else 0x10c0)
    data[706:706 + len(symbol) + 1] = symbol + b"\0"
    return bytes(data)


class InspectTests(unittest.TestCase):
    def test_runtime_imports_require_exact_opt_in_profile(self):
        value = image(symbol=b'cudaMalloc',library=b'cudart64_12.dll')
        with self.assertRaises(LoaderError): inspect_pe(value)
        self.assertEqual(inspect_pe(value,runtime=True)['imports'][0]['symbols'],['cudaMalloc'])
        for symbol in (b'cudaLaunchKernel',b'__cudaRegisterFatBinary',b'__cudaPopCallConfiguration'):
            data=image(symbol=symbol,library=b'cudart64_12.dll')
            self.assertEqual(inspect_pe(data,runtime=True)['imports'][0]['symbols'],[symbol.decode()])
            with self.assertRaises(LoaderError):inspect_pe(data)
        for symbol,library,ordinal in [(b'__cudaRegisterVar',b'cudart64_12.dll',False),
            (b'cudaLaunchKernelExC',b'cudart64_12.dll',False),
            (b'cudaMalloc',b'cudart64_110.dll',False),(b'cudaMalloc',b'cudart64_12.dll',True)]:
            with self.subTest(symbol=symbol,library=library,ordinal=ordinal),self.assertRaises(LoaderError):
                inspect_pe(image(symbol=symbol,library=library,ordinal=ordinal),runtime=True)

    def test_runtime_bundle_preserves_all_payload_bytes_and_rejects_collisions(self):
        with tempfile.TemporaryDirectory(dir=self.temp_root) as root:
            root=Path(root)
            app,driver,runtime=root/'app.exe',root/'ct.dll',root/'runtime.dll'
            app.write_bytes(image(symbol=b'cudaMalloc',library=b'cudart64_12.dll'))
            driver.write_bytes(image(dll=True))
            runtime.write_bytes(image(dll=True,library=b'kernel32.dll',symbol=b'GetCurrentProcess'))
            bundle,report=prepare_bundle(app,driver,[],root/'runs',runtime_dll=runtime)
            for name,source in [('app.exe',app),('nvcuda.dll',driver),('cudart64_12.dll',runtime)]:
                self.assertEqual((bundle/name).read_bytes(),source.read_bytes())
            self.assertEqual(len(report['runtime_sha256']),64)
            for name in ['NVCUDA.DLL.exe','cudart64_12.dll']:
                # A Runtime-named asset must never shadow the explicitly supplied module.
                asset=root/name; asset.write_bytes(b'input')
                with self.assertRaises(LoaderError):prepare_bundle(app,driver,[asset],root/'runs',runtime_dll=runtime)

    def setUp(self):
        self.temp_root = (Path(__file__).resolve().parents[1] / ".cache/loader-tests").resolve()
        self.temp_root.mkdir(parents=True, exist_ok=True)

    def test_classifies_static_and_dynamic_and_unknown_symbols(self):
        self.assertEqual(inspect_pe(image())["cuda_loading"], "static")
        self.assertEqual(inspect_pe(image(library=b"kernel32.dll"))["cuda_loading"], "dynamic-or-none")
        with self.assertRaises(LoaderError):
            inspect_pe(image(symbol=b"cuNotImplemented"))
        with self.assertRaises(LoaderError):
            inspect_pe(image(library=b"cudart64_12.dll"))

    def test_rejects_bad_architecture_dll_delay_and_cuda_ordinals(self):
        for change in ("x86", "dll", "delay", "ordinal"):
            data = bytearray(image(ordinal=change == "ordinal", dll=change == "dll"))
            if change == "x86":
                struct.pack_into("<H", data, 132, 0x14c)
            if change == "delay":
                struct.pack_into("<II", data, 272 + 12 * 8, 0x1100, 32)
            with self.subTest(change=change), self.assertRaises(LoaderError):
                inspect_pe(bytes(data))

    def test_rejects_truncation_and_unmapped_rvas(self):
        for size in (0, 64, 150, 300, 530, 650, 710):
            with self.subTest(size=size), self.assertRaises(LoaderError):
                inspect_pe(image()[:size])
        data = bytearray(image())
        struct.pack_into("<I", data, 524, 0xfffffff0)
        with self.assertRaises(LoaderError):
            inspect_pe(bytes(data))

    def test_rejects_invalid_iat_even_with_valid_lookup_table(self):
        for address in (0, 0xfffffff0):
            data = bytearray(image())
            struct.pack_into("<I", data, 528, address)
            with self.subTest(address=address), self.assertRaises(LoaderError):
                inspect_pe(bytes(data))

    def test_cli_argument_errors_do_not_echo_private_input(self):
        marker = "C:" + "\\" + "Users" + "\\" + "synthetic-private" + "\\second.exe"
        script = Path(__file__).resolve().parents[1] / "scripts/ct.py"
        for arguments in (["inspect", "synthetic.exe", marker], [marker]):
            result = subprocess.run([sys.executable, str(script), *arguments], capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn(marker.encode(), result.stdout + result.stderr)
            self.assertIn(b"invalid command line", result.stdout)

    def test_bundle_preserves_bytes_and_rejects_collisions(self):
        with tempfile.TemporaryDirectory(dir=self.temp_root) as root:
            root = Path(root)
            app, dll, ptx = root / "app.exe", root / "ct_cuda.dll", root / "input.ptx"
            app.write_bytes(image())
            dll.write_bytes(image(dll=True))
            ptx.write_bytes(b"synthetic PTX bytes")
            bundle, report = prepare_bundle(app, dll, [ptx], root / "runs")
            self.assertEqual((bundle / app.name).read_bytes(), app.read_bytes())
            self.assertEqual((bundle / "nvcuda.dll").read_bytes(), dll.read_bytes())
            self.assertEqual((bundle / ptx.name).read_bytes(), ptx.read_bytes())
            self.assertEqual(len(report["application_sha256"]), 64)
            with self.assertRaises(LoaderError):
                prepare_bundle(app, dll, [app], root / "runs")
            other = root / "other"
            other.mkdir()
            collision = other / "INPUT.PTX"
            collision.write_bytes(b"collision")
            with self.assertRaises(LoaderError):
                prepare_bundle(app, dll, [ptx, collision], root / "runs")

    def test_child_arguments_and_exit_status(self):
        with tempfile.TemporaryDirectory(dir=self.temp_root) as root:
            code = "import sys; assert sys.argv[1:] == ['with space', 'quote\"', '한글']; sys.exit(7)"
            self.assertEqual(run_child(Path(sys.executable), ["-c", code, "with space", 'quote"', "한글"], Path(root)), 7)

    def test_ptx_text_can_use_upstream_fatbin_filename_but_binary_cannot(self):
        with tempfile.TemporaryDirectory(dir=self.temp_root) as root:
            root = Path(root)
            app, dll, asset = root / "app.exe", root / "ct.dll", root / "kernel.fatbin"
            app.write_bytes(image()); dll.write_bytes(image(dll=True))
            asset.write_bytes(b"// compiler output\n.version 8.0\n.target sm_52\n")
            bundle, _ = prepare_bundle(app, dll, [asset], root / "runs")
            self.assertEqual((bundle / asset.name).read_bytes(), asset.read_bytes())
            for invalid in (b"binary\0fatbin", b"arbitrary ASCII text", b"\xff.version 8.0"):
                asset.write_bytes(invalid)
                with self.assertRaises(LoaderError):
                    prepare_bundle(app, dll, [asset], root / "runs")

    def test_binary_fatbin_staging_checks_outer_length_and_cap(self):
        with tempfile.TemporaryDirectory(dir=self.temp_root) as root:
            root = Path(root)
            app, dll, asset = root / "app.exe", root / "ct.dll", root / "kernel.fatbin"
            app.write_bytes(image()); dll.write_bytes(image(dll=True))
            fatbin = struct.pack("<IHHQ",0xba55ed50,1,16,8)+b"synthetic"
            # Outer-only staging triage; CT performs full record validation before loading.
            fatbin = fatbin[:-1]
            asset.write_bytes(fatbin)
            bundle, _ = prepare_bundle(app,dll,[asset],root / "runs")
            self.assertEqual((bundle/asset.name).read_bytes(),fatbin)
            for bad in (fatbin[:-1],fatbin+b"extra",struct.pack("<IHHQ",0xba55ed50,1,16,1<<30)):
                asset.write_bytes(bad)
                with self.assertRaises(LoaderError): prepare_bundle(app,dll,[asset],root/"runs")


if __name__ == "__main__":
    unittest.main()
