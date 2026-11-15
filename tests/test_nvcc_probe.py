import importlib.util
import tempfile
import unittest
import sys
import json
import struct
import zipfile
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
spec = importlib.util.spec_from_file_location('nvcc_probe', ROOT/'scripts/prepare_nvcc_probe.py')
probe = importlib.util.module_from_spec(spec) if spec else None


class NvccProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if spec and spec.loader and spec.origin and Path(spec.origin).is_file():
            spec.loader.exec_module(probe)

    def test_raw_lz4_is_independent_and_bounded(self):
        self.assertTrue(hasattr(probe, 'decode_lz4'), 'independent decoder is required')
        self.assertEqual(probe.decode_lz4(bytes([0x20, 97, 0]), 2), b'a\0')
        for block, size in [(b'\x00\x00\x00', 4), (b'\xf0', 20), (b'\x10a', 2)]:
            with self.assertRaises(ValueError):
                probe.decode_lz4(block, size)
        with self.assertRaises(ValueError):
            probe.decode_lz4(b'\x00', 262153)

    def test_replay_rejects_changed_payload(self):
        self.assertTrue(hasattr(probe, 'audit_probe'), 'independent artifact audit is required')
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as folder:
            p = Path(folder)/'manifest.json'
            p.write_text('{"success":true}', encoding='utf-8')
            self.assertTrue(probe.audit_probe(p))

    def test_replay_requires_header_closure(self):
        self.assertTrue(hasattr(probe, 'validate_host'), 'header closure validation is required')
        with self.assertRaises(ValueError):
            probe.validate_host({'profile': 'diagnostic', 'files': {}})

    def test_diagnostic_is_never_qualified(self):
        self.assertTrue(hasattr(probe, 'validate_host'), 'host qualification check is required')
        with self.assertRaises(ValueError):
            probe.validate_host({'profile': 'qualified', 'compiler_version': '19.51',
                                 'override': True, 'files': {'x': '0'*64}})

    def test_host_environment_preserves_unicode(self):
        self.assertTrue(hasattr(probe, 'decode_host_env'))
        data = 'INCLUDE=C:\\테스트\\include\r\n=Z:=Z:\\\r\nLIB=C:\\lib\r\n'.encode('utf-16-le')
        self.assertEqual(probe.decode_host_env(data), {'INCLUDE': 'C:\\테스트\\include', 'LIB': 'C:\\lib'})

    def test_producer_roles_use_fixed_member_paths(self):
        tool_spec = importlib.util.spec_from_file_location('tool_files', ROOT/'scripts/check_toolchain_files.py')
        tools = importlib.util.module_from_spec(tool_spec)
        tool_spec.loader.exec_module(tools)
        self.assertTrue(hasattr(tools, 'member_path'))
        self.assertEqual(tools.member_path('cuda-nvcc-producer', 'host_runtime.h'), 'include/crt/host_runtime.h')
        self.assertEqual(tools.member_path('cuda-nvcc-support-headers', 'host_defines.h'), 'crt/host_defines.h')

    def fixture(self, folder):
        archive = folder/'cuda_nvcc.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('archive/include/crt/host_runtime.h', b'CT-owned header stand-in')
        vendor = folder/'toolkit/include/crt/host_runtime.h'
        vendor.parent.mkdir(parents=True)
        vendor.write_bytes(b'CT-owned header stand-in')
        host_root = folder/'host'
        host_root.mkdir()
        for name in ('cl.exe', 'link.exe', 'header.h', 'vcvars.cmd'):
            (host_root/name).write_bytes(b'CT-owned non-executable stand-in')
        host = dict(profile='diagnostic', compiler_version='19.51.1', override=True, environment_policy=probe.ENV_POLICY,
                    roots=[str(host_root)], files=probe.inventory([host_root]),
                    tools={name: dict(path=str(host_root/name), sha256=probe.digest(host_root/name)) for name in ('cl.exe', 'link.exe')},
                    vcvars=dict(path=str(host_root/'vcvars.cmd'), sha256=probe.digest(host_root/'vcvars.cmd')))
        (folder/'vector.cu').write_bytes(probe.SOURCE.read_bytes())
        artifacts = {}
        for mode in ('compressed', 'plain'):
            keep = folder/('keep-'+mode)
            keep.mkdir()
            h = bytearray(72)
            struct.pack_into('<HHIQ', h, 0, 1, 0x101, 72, 8)
            struct.pack_into('<IIIII', h, 20, 64, 8 << 16, 52, 0, 0)
            struct.pack_into('<I', h, 40, 0x2041 if mode == 'compressed' else 0x41)
            if mode == 'compressed':
                struct.pack_into('<I', h, 16, 3)
                struct.pack_into('<Q', h, 56, 2)
            body = b'\x20a\0'+b'\0'*5 if mode == 'compressed' else b'a'+b'\0'*7
            (keep/'vector.fatbin').write_bytes(struct.pack('<IHHQ', 0xba55ed50, 1, 16, 80)+h+body)
            (keep/'vector.ptx').write_bytes(b'a')
            (keep/'vector.cudafe1.stub.c').write_bytes(b'CT-owned stub stand-in')
            (folder/(mode+'.exe')).write_bytes(b'CT-owned non-executable stand-in')
            names = [mode+'.exe']+['keep-'+mode+'/vector'+s for s in ('.fatbin', '.ptx', '.cudafe1.stub.c')]
            artifacts[mode] = {n: probe.digest(folder/n) for n in names}
        value = dict(schema_version=1, source_sha256=probe.digest(probe.SOURCE), packages=str(folder),
                     vendor_files={'toolkit/include/crt/host_runtime.h': probe.digest(vendor)}, host=host,
                     commands={m: probe.compiler_args(folder, 'diagnostic', m, str(host_root)) for m in ('compressed', 'plain')},
                     artifacts=artifacts, runtime_exercised=False)
        return value, {'cuda_nvcc.zip': probe.digest(archive)}

    def test_complete_replay_detects_each_tamper(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as tmp:
            folder = Path(tmp)
            value, pins = self.fixture(folder)
            manifest = folder/'manifest.json'
            with patch.dict(probe.PINS, pins, clear=True):
                manifest.write_text(json.dumps(value), encoding='utf-8')
                self.assertEqual(probe.audit_probe(manifest), [])
                for mutation in ('payload', 'vendor', 'closure', 'vcvars', 'qualified', 'source'):
                    changed = json.loads(json.dumps(value))
                    if mutation == 'payload':
                        changed['artifacts']['plain']['keep-plain/vector.fatbin'] = '0'*64
                    elif mutation == 'vendor':
                        changed['vendor_files'] = {}
                    elif mutation == 'closure':
                        del changed['host']['files'][str(folder/'host/header.h')]
                    elif mutation == 'vcvars':
                        changed['host']['vcvars']['sha256'] = '0'*64
                    elif mutation == 'qualified':
                        changed['host'].update(profile='qualified', compiler_version='19.38.1', override=False)
                        changed['commands'] = {m: probe.compiler_args(folder, 'qualified', m, str(folder/'host')) for m in ('compressed', 'plain')}
                    else:
                        (folder/'vector.cu').write_bytes(b'changed source')
                    manifest.write_text(json.dumps(changed), encoding='utf-8')
                    self.assertTrue(probe.audit_probe(manifest), mutation)

    def test_wrong_actual_compression_mode_rejected_even_with_updated_hash(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as tmp:
            folder = Path(tmp)
            value, pins = self.fixture(folder)
            source = folder/'keep-plain/vector.fatbin'
            dest = folder/'keep-compressed/vector.fatbin'
            dest.write_bytes(source.read_bytes())
            value['artifacts']['compressed']['keep-compressed/vector.fatbin'] = probe.digest(dest)
            manifest = folder/'manifest.json'
            manifest.write_text(json.dumps(value), encoding='utf-8')
            with patch.dict(probe.PINS, pins, clear=True):
                self.assertTrue(probe.audit_probe(manifest))

    def test_hidden_compiler_flags_are_removed(self):
        self.assertTrue(hasattr(probe, 'normalize_env'))
        original = {'Path':'compiler', 'INCLUDE':'headers', 'CL':'/Iforeign', '_CL_':'/FIforeign.h',
                    'NVCC_PREPEND_FLAGS':'--no-compress', 'nvcc_append_flags':'-Iforeign',
                    'NVCC_CCBIN':'foreign', 'LINK':'/LIBPATH:foreign', 'CPATH':'foreign'}
        clean = probe.normalize_env(original)
        self.assertEqual(clean, {'Path':'compiler', 'INCLUDE':'headers'})


if __name__ == '__main__':
    unittest.main()
