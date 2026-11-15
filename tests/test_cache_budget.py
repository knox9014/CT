import importlib
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
try:
    budget=importlib.import_module('cache_budget')
except ModuleNotFoundError as error:
    if error.name!='cache_budget':raise
    budget=None


class CacheBudgetTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(budget,'storage budget helper is not implemented')

    def test_limits_include_equality_and_conservative_peak(self):
        result=budget.assess(38*budget.GIB,32*budget.GIB,2*budget.GIB)
        self.assertEqual(result['projected_cache_bytes'],40*budget.GIB)
        self.assertEqual(result['projected_free_bytes'],30*budget.GIB)

    def test_cache_limit_refuses_before_disk_is_full(self):
        with self.assertRaisesRegex(ValueError,'cache_limit'):
            budget.assess(39*budget.GIB,100*budget.GIB,2*budget.GIB)

    def test_free_space_floor_refuses_even_with_small_cache(self):
        with self.assertRaisesRegex(ValueError,'free_space_floor'):
            budget.assess(0,31*budget.GIB,2*budget.GIB)

    def test_negative_boolean_and_noninteger_sizes_are_refused(self):
        for bad in (-1,True,1.5,'1'):
            for slot in range(3):
                values=[0,100*budget.GIB,0];values[slot]=bad
                with self.assertRaises(ValueError):budget.assess(*values)
        for kwargs in ({'cache_limit':True},{'free_floor':-1}):
            with self.assertRaises(ValueError):budget.assess(0,100*budget.GIB,0,**kwargs)

    def test_real_tree_counts_bytes_and_missing_cache_is_not_created(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as name:
            root=Path(name)
            self.assertEqual(budget.cache_bytes(root),0)
            self.assertFalse((root/'.cache').exists())
            folder=root/'.cache/deep';folder.mkdir(parents=True)
            (folder/'a').write_bytes(b'a'*7);(root/'.cache/b').write_bytes(b'b'*12)
            self.assertEqual(budget.cache_bytes(root),19)

    def test_refusal_does_not_mutate_existing_files_or_create_output(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as name:
            root=Path(name);folder=root/'.cache';folder.mkdir();file=folder/'evidence';file.write_bytes(b'keep')
            before=sorted(p.relative_to(root).as_posix() for p in root.rglob('*'))
            with self.assertRaisesRegex(ValueError,'cache_limit'):
                budget.ensure_budget(root,1,cache_limit=4,free_floor=0)
            self.assertEqual(file.read_bytes(),b'keep')
            self.assertEqual(before,sorted(p.relative_to(root).as_posix() for p in root.rglob('*')))

    def test_cache_file_is_not_treated_as_an_empty_directory(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as name:
            root=Path(name);(root/'.cache').write_bytes(b'not a directory')
            with self.assertRaisesRegex(ValueError,'cache_not_directory'):budget.cache_bytes(root)


if __name__=='__main__':unittest.main()
