import copy
import unittest
import sys
import tempfile
import json
import hashlib
from pathlib import Path

from relaxed_nvcc_oracle import expected, validate
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from run_relaxed_nvcc import require_relaxed_ptx, verify_files, ptx_tokens, validate_runs


class RelaxedNvccOracleTests(unittest.TestCase):
    def test_edge_values_and_high_bit_truncation(self):
        value = expected(13)
        self.assertEqual(value['rows'][3]['wide'][2], 0x80000000)
        self.assertEqual(value['rows'][5]['wide'][2], 0xffffffff)
        self.assertFalse(validate(value, 13))

    def test_rejects_every_mutated_readback_word(self):
        original = expected(19)
        for i in range(8):
            for kind in ('wide', 'narrow'):
                for j in range(5):
                    value = copy.deepcopy(original)
                    value['rows'][i][kind][j] ^= 1
                    self.assertTrue(validate(value, 19))

    def test_closed_schema_and_exact_integer_types(self):
        for mutation in ('extra', 'missing', 'bool', 'seed'):
            value = expected(7)
            if mutation == 'extra': value['extra'] = 0
            if mutation == 'missing': del value['rows'][0]['wide']
            if mutation == 'bool': value['rows'][0]['narrow'][0] = True
            if mutation == 'seed': value['seed'] = 8
            self.assertTrue(validate(value, 7))

    def test_noop_is_detected(self):
        self.assertTrue(validate(expected(29, noop=True), 29))
        self.assertFalse(validate(expected(29, noop=True), 29, noop=True))

    def test_seed_is_bounded_and_not_bool(self):
        for seed in (0, -1, 1000001, True, '1'):
            with self.assertRaises(ValueError): expected(seed)


class RelaxedNvccArtifactTests(unittest.TestCase):
    TEXT = '''.visible .entry widen_value() { .reg .b64 %rd<2>;
    ld.volatile.global.u32 %rd1, [ct_narrow]; ret; }
    .visible .entry narrow_value() { .reg .b64 %rd<2>;
    st.volatile.global.u32 [ct_narrow], %rd1; ret; }'''

    def test_both_real_register_shapes_required(self):
        require_relaxed_ptx(self.TEXT)
        for bad in (self.TEXT.replace('ld.volatile.global.u32', 'ld.volatile.global.u64'),
                    self.TEXT.replace('st.volatile.global.u32', 'st.volatile.global.u64'),
                    self.TEXT.replace('.b64', '.b32'),
                    self.TEXT.replace('%rd1, [ct_narrow]', '%r1, [ct_narrow]'),
                    self.TEXT.replace('[ct_narrow], %rd1', '[ct_narrow], %r1')):
            with self.assertRaises(ValueError): require_relaxed_ptx(bad)

    def test_payload_comparison_only_ignores_comments_and_whitespace(self):
        original = self.TEXT.encode()
        changed = b'// producer header\r\n' + original.replace(b' ', b'\t')
        self.assertEqual(ptx_tokens(original), ptx_tokens(changed))
        self.assertNotEqual(ptx_tokens(original), ptx_tokens(original.replace(b'u32', b'u64')))

    def test_changed_and_escaped_artifacts_rejected(self):
        cache = Path(__file__).resolve().parents[1] / '.cache/relaxed-nvcc-tests'
        cache.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as d:
            folder = Path(d)
            (folder / 'a').write_bytes(b'original')
            files = {'a': hashlib.sha256(b'original').hexdigest()}
            verify_files(folder, files)
            (folder / 'a').write_bytes(b'changed')
            with self.assertRaises(ValueError): verify_files(folder, files)
            with self.assertRaises(ValueError): verify_files(folder, {'../outside': '0' * 64})

    def test_saved_execution_requires_correct_roles_controls_and_observations(self):
        cache = Path(__file__).resolve().parents[1] / '.cache/relaxed-nvcc-tests'
        cache.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as d:
            folder = Path(d)
            artifacts = {'default.exe': b'executable', 'ct_cuda.dll': b'driver',
                         'ct_cudart.dll': b'runtime', 'noop.dll': b'noop'}
            files = {n: hashlib.sha256(b).hexdigest() for n, b in artifacts.items()}
            rows = []
            for i, mode in enumerate(('positive', 'positive', 'noop')):
                bundle = folder / 'runs' / str(i)
                bundle.mkdir(parents=True)
                roles = {'default.exe': 'default.exe', 'cudart64_12.dll': 'ct_cudart.dll',
                         'nvcuda.dll': 'noop.dll' if mode == 'noop' else 'ct_cuda.dll'}
                if mode == 'noop': roles['ct_underlying.dll'] = 'ct_cuda.dll'
                for name, role in roles.items(): (bundle / name).write_bytes(artifacts[role])
                output = json.dumps(expected(i + 1, noop=mode == 'noop')).encode()
                (bundle / 'stdout.json').write_bytes(output)
                (bundle / 'stderr.txt').write_bytes(b'')
                rows.append(dict(seed=i + 1, mode=mode, exit_code=0,
                                 bundle=bundle.relative_to(folder).as_posix(),
                                 files={n: files[r] for n, r in roles.items()},
                                 stdout=hashlib.sha256(output).hexdigest(),
                                 stderr=hashlib.sha256(b'').hexdigest()))
            validate_runs(folder, files, rows)
            for mutation in ('missing', 'seed', 'role', 'path', 'bool', 'output'):
                bad = copy.deepcopy(rows)
                if mutation == 'missing': bad.pop()
                if mutation == 'seed': bad[1]['seed'] = bad[0]['seed']
                if mutation == 'role': bad[0]['files']['nvcuda.dll'] = files['noop.dll']
                if mutation == 'path': bad[0]['bundle'] = '../outside'
                if mutation == 'bool': bad[0]['exit_code'] = False
                if mutation == 'output':
                    p = folder / bad[0]['bundle'] / 'stdout.json'
                    data = json.dumps(expected(999)).encode()
                    p.write_bytes(data)
                    bad[0]['stdout'] = hashlib.sha256(data).hexdigest()
                with self.assertRaises(ValueError): validate_runs(folder, files, bad)


if __name__ == '__main__':
    unittest.main()
