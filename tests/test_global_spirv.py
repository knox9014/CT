"""Global validator controls cannot trust a successful process alone."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from check_global_spirv import check_modules

class GlobalSpirvTests(unittest.TestCase):
    def setUp(self):
        self.cache = Path(__file__).resolve().parents[1]/'.cache/global-validator-tests'
        self.cache.mkdir(parents=True, exist_ok=True)
    def test_exit_zero_validator_is_rejected_by_negative_controls(self):
        with tempfile.TemporaryDirectory(dir=self.cache) as d:
            with patch('check_global_spirv.subprocess.run') as process, patch('check_global_spirv.run_validator') as validator:
                process.return_value.returncode = 0
                def fake_translation(argv, **kwargs):
                    if len(argv) == 3:
                        Path(argv[2]).write_bytes(bytes.fromhex('0302230700000100000000000100000000000000'))
                    return process.return_value
                process.side_effect = fake_translation
                validator.return_value = dict(status='pass', reason='passed')
                rows = check_modules(Path(d), Path('translator'), Path('validator'), {})
                self.assertTrue(any(r['expected'] == 'rejected' and r['status'] == 'pass' for r in rows))
                self.assertFalse(all(r['status'] == ('pass' if r['expected'] == 'accepted' else 'fail') for r in rows))
    def test_missing_translator_fails_without_success_rows(self):
        with tempfile.TemporaryDirectory(dir=self.cache) as d:
            with self.assertRaises(OSError):
                check_modules(Path(d), Path(d)/'missing.exe', Path(d)/'missing-val.exe', {})

if __name__ == '__main__': unittest.main()
