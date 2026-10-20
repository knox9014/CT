"""Runner boundaries use fake processes only here; real validation is separate."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import subprocess

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from validate_spirv import run_validator


class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.cache = Path(__file__).resolve().parents[1] / '.cache/validator-tests'
        self.cache.mkdir(parents=True, exist_ok=True)

    def test_missing_and_hash_mismatch_cannot_pass(self):
        with tempfile.TemporaryDirectory(dir=self.cache) as d:
            p = Path(d)
            module = p / 'module.spv'; module.write_bytes(b'input')
            tool = p / 'validator.exe'
            lock = dict(pin_state='unresolved', files={}, validation_target='opencl1.2', platform='windows-x64')
            self.assertEqual(run_validator(module, tool, lock, required=True)['status'], 'fail')
            self.assertEqual(run_validator(module, tool, lock, required=False)['status'], 'skipped')
            tool.write_bytes(b'tool')
            lock.update(pin_state='pinned', files={'spirv-val.exe': 'a' * 64})
            self.assertEqual(run_validator(module, tool, lock, required=True)['reason'], 'tool_hash_mismatch')

    def test_process_outcomes_and_environment(self):
        with tempfile.TemporaryDirectory(dir=self.cache) as d:
            p = Path(d)
            module = p / 'module.spv'; module.write_bytes(b'input')
            tool = p / 'validator.exe'; tool.write_bytes(b'tool')
            lock = dict(pin_state='pinned', files={'spirv-val.exe': hashlib.sha256(b'tool').hexdigest()},
                        validation_target='opencl1.2', platform='windows-x64')
            with patch('validate_spirv.subprocess.run') as run:
                run.return_value = subprocess.CompletedProcess([], 0, b'', b'')
                self.assertEqual(run_validator(module, tool, lock, required=True)['status'], 'pass')
                argv = run.call_args.args[0]
                self.assertEqual(argv[1:3], ['--target-env', 'opencl1.2'])
                self.assertNotIn('shell', run.call_args.kwargs)
                run.return_value = subprocess.CompletedProcess([], 1, b'', b'private raw diagnostic')
                result = run_validator(module, tool, lock, required=True)
                self.assertEqual(result['reason'], 'validation_rejected')
                self.assertNotIn('private', str(result))
                run.side_effect = subprocess.TimeoutExpired([], 1)
                self.assertEqual(run_validator(module, tool, lock, required=True)['reason'], 'tool_timeout')

    def test_wrong_target_cannot_silently_change_profile(self):
        with tempfile.TemporaryDirectory(dir=self.cache) as d:
            p = Path(d) / 'missing'
            result = run_validator(p, p, dict(validation_target='vulkan1.0'), required=True)
            self.assertEqual(result['status'], 'fail')


if __name__ == '__main__': unittest.main()
