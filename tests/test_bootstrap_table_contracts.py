"""Prevent concrete ABI/table-identity and size-unit mistakes before exposure."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from check_bootstrap_tables import validate_inventory, check_binding, verify_sources

ROOT=Path(__file__).resolve().parents[1]


def inventory():
    return json.loads((ROOT/'docs/compatibility/bootstrap-tables.json').read_text(encoding='utf-8'))


class ContractTests(unittest.TestCase):
    def test_inventory_never_authorizes_native_execution(self):
        result=validate_inventory(inventory())
        self.assertIs(result['native_success_authorized'],False)
        self.assertEqual(result['tables'],2)
        self.assertEqual(result['callable_slots'],9)

    def test_slot_zero_and_null_holes_cannot_be_called(self):
        m=inventory();uuid=m['tables'][0]['uuid']
        for offset in (0,24,40,72,80,88,-8,1,104,True):
            with self.subTest(offset=offset),self.assertRaises(ValueError):check_binding(m,uuid,offset,'CUresult',[],'system')

    def test_void_getter_cannot_be_status_or_wrong_arity_abi(self):
        m=inventory();uuid=m['tables'][1]['uuid']
        descriptor=check_binding(m,uuid,16,'void',['void**','usize*'],'system')
        self.assertEqual(descriptor['index'],2)
        self.assertIs(descriptor['native_success_authorized'],False)
        for ret,args,abi in [('CUresult',['void**','usize*'],'system'),('void',['void**'],'system'),('void',['void**','usize*'],'C')]:
            with self.assertRaises(ValueError):check_binding(m,uuid,16,ret,args,abi)
        with self.assertRaises(ValueError):check_binding(m,m['tables'][0]['uuid'],16,'void',['void**','usize*'],'system')
        m['tables'][1]['functions'][0]['argument_types']=['void*','usize*']
        with self.assertRaises(ValueError):validate_inventory(m)

    def test_table_bytes_and_buffer_elements_are_distinct(self):
        for change in ('table_bytes','buffer_unit','buffer_count','slot_overlap','metadata_bool','promotion'):
            m=inventory()
            if change=='table_bytes':m['tables'][1]['byte_size']=7
            elif change=='buffer_unit':m['tables'][1]['buffer_reference'][0]['source_count_unit']='bytes'
            elif change=='buffer_count':m['tables'][1]['buffer_reference'][0]['element_count']=4096
            elif change=='slot_overlap':m['tables'][0]['null_slots'].append(1)
            elif change=='metadata_bool':m['pointer_bytes']=True
            else:m['native_success_authorized']=True
            with self.subTest(change=change),self.assertRaises(ValueError):validate_inventory(m)

    def test_evidence_must_have_pinned_ref_and_hashes(self):
        m=inventory();m['sources'][0]['url']=m['sources'][0]['url'].replace(m['source_commit'],'master')
        with self.assertRaises(ValueError):validate_inventory(m)
        cache=ROOT/'.cache/table-contract-tests';cache.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as folder:
            with self.assertRaises(ValueError):verify_sources(inventory(),Path(folder))
            p=Path(folder)/'dark_api/src/lib.rs';p.parent.mkdir(parents=True);p.write_text('changed',encoding='utf-8')
            with self.assertRaises(ValueError):verify_sources(inventory(),Path(folder))


if __name__=='__main__':unittest.main()
