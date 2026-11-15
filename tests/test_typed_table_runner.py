import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from run_typed_tables import validate_native, inventory, FIXTURE_IMPORTS, RUST_TEST_IMPORTS


class EvidenceTests(unittest.TestCase):
    def test_native_evidence_requires_all_wiring_and_teardown_checks(self):
        value=dict(scope='typed_deny_direct',checks=47,mask=511,stopped=True,loaded_same_file=True,
                   unloaded=True,runtime_exposed=False,application_supported=False)
        validate_native(value)
        for key,bad in [('checks',46),('mask',255),('stopped',1),('unloaded',False),('runtime_exposed',True),('application_supported',True)]:
            changed=copy.deepcopy(value);changed[key]=bad
            with self.subTest(key=key),self.assertRaises(ValueError):validate_native(changed)
        value['extra']=1
        with self.assertRaises(ValueError):validate_native(value)

    def test_extra_exports_or_nonreviewed_dependency_block_execution(self):
        exports={'ctTableGet','ctTableState'}
        inventory(exports,FIXTURE_IMPORTS,{'kernel32.dll'},RUST_TEST_IMPORTS)
        for ex,fixture,host in [(exports|{'cuGetExportTable'},FIXTURE_IMPORTS,{'kernel32.dll'}),
                                (exports,FIXTURE_IMPORTS|{'ze_loader.dll'},{'kernel32.dll'}),
                                (exports,FIXTURE_IMPORTS,{'kernel32.dll','nvcuda.dll'})]:
            with self.assertRaises(ValueError):inventory(ex,fixture,host,RUST_TEST_IMPORTS)
        with self.assertRaises(ValueError):inventory(exports,FIXTURE_IMPORTS,{'kernel32.dll'},RUST_TEST_IMPORTS|{'nvcuda.dll'})


if __name__=='__main__':unittest.main()
