"""Exercise the real module CLI, including stale-output and error boundaries."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ModuleCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build = subprocess.run(['cargo', 'build', '-p', 'ct-codegen-spirv', '--example', 'translate_module'],
                               cwd=ROOT, capture_output=True, timeout=120)
        if build.returncode:
            raise RuntimeError('module CLI build failed; compiler output remains local')
        target = Path(os.environ.get('CARGO_TARGET_DIR', str(ROOT / 'target')))
        if not target.is_absolute(): target = ROOT / target
        cls.tool = target / 'debug/examples' / ('translate_module.exe' if os.name == 'nt' else 'translate_module')

    def test_distinct_errors_remove_stale_output(self):
        cache = ROOT / '.cache/module-cli-tests'; cache.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as d:
            p = Path(d); source, output = p / 'input.ptx', p / 'output.spv'
            for data, expected in ((None, 2), ('invalid', 1),
                ('.version 7.0 .target sm_50 .address_size 64 .visible .entry k() { bar.sync 0; ret; }', 3)):
                if data is not None: source.write_text(data)
                output.write_bytes(b'stale')
                run = subprocess.run([str(self.tool), str(source), str(output)], capture_output=True, timeout=30)
                self.assertEqual(run.returncode, expected)
                self.assertFalse(output.exists())
                self.assertNotIn(str(p).encode(), run.stderr)
            source.write_text('keep input')
            run = subprocess.run([str(self.tool), str(source), str(source)], capture_output=True, timeout=30)
            self.assertEqual(run.returncode, 2)
            self.assertEqual(source.read_text(), 'keep input')

    def test_real_multi_entry_output(self):
        cache = ROOT / '.cache/module-cli-tests'; cache.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as d:
            output = Path(d) / 'output.spv'
            run = subprocess.run([str(self.tool), str(ROOT/'tests/fixtures/multi_entry.ptx'), str(output)],
                                 capture_output=True, timeout=30)
            self.assertEqual(run.returncode, 0)
            data = output.read_bytes()
            self.assertEqual(data[:4], b'\x03\x02\x23\x07')
            for name in (b'kernel_add\x00', b'kernel_sub\x00', b'kernel_fill\x00'):
                self.assertIn(name, data)


if __name__ == '__main__': unittest.main()
