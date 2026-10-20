"""Ensure native predicate inputs distinguish complete64-bit equality."""
import unittest
import m3m_predicates_check as probe


class PredicateInputTests(unittest.TestCase):
    def test_high_bits_alone_can_change_equality(self):
        pairs = [(a, a if i % 5 == 0 else b)
                 for i, (a, b, _) in enumerate(probe.inputs(64, 63))]
        witnesses = [(a, b) for a, b in pairs
                     if a != b and (a & 0xffffffff) == (b & 0xffffffff)]
        self.assertTrue(witnesses, 'native eq/ne must detect truncation to low32')
        for a, b in witnesses:
            self.assertEqual(probe.oracle('eq', 'u64', a, b, 1), 0xfffffffffffffffe)
            self.assertEqual(probe.oracle('ne', 'u64', a, b, 1), 1)


if __name__ == '__main__': unittest.main()
