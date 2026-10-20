"""Pin signed unary boundaries in the actual native input generator."""
import unittest
import m3n_minmax_check as probe


class ExtremaInputTests(unittest.TestCase):
    def test_unary_operands_include_both_signed_extrema_zero_and_units(self):
        for width in (32, 64):
            mask = (1 << width) - 1; top = 1 << (width - 1)
            actual = {a for a, _, _ in probe.inputs(width, 63)}
            self.assertTrue({0, 1, mask, top - 1, top, top + 1} <= actual,
                            'native unary input must include signed boundaries and -1/+1')


if __name__ == '__main__': unittest.main()
