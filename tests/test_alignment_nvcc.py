import copy
import unittest
from alignment_nvcc_oracle import expected, validate


class AlignmentNvccOracleTests(unittest.TestCase):
    def test_exact_positive_and_noop(self):
        for seed in (1, 19, 1000000):
            self.assertFalse(validate(expected(seed), seed))
            self.assertFalse(validate(expected(seed, noop=True), seed, noop=True))
            self.assertTrue(validate(expected(seed, noop=True), seed))

    def test_every_device_readback_and_guard_word_is_checked(self):
        original = expected(17)
        for kind in ('wide', 'narrow', 'negative', 'input'):
            for i in range(len(original[kind])):
                bad = copy.deepcopy(original)
                bad[kind][i] ^= 1
                self.assertTrue(validate(bad, 17))

    def test_invalid_launch_status_schema_and_types(self):
        for key, val in (('invalid', 0), ('invalid', True), ('device', 'other GPU'),
                         ('seed', 99), ('wide', [])):
            bad = expected(7)
            bad[key] = val
            self.assertTrue(validate(bad, 7))
        bad = expected(7); bad['extra'] = 0
        self.assertTrue(validate(bad, 7))

    def test_bad_seeds(self):
        for seed in (0, -1, True, '1', 1000001):
            with self.assertRaises(ValueError): expected(seed)


if __name__ == '__main__':
    unittest.main()
