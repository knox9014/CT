"""The support manifest is a bounded static contract, not an execution report."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from check_compatibility_profile import validate_profile, expected_exports


class ProfileTests(unittest.TestCase):
    def test_only_audited_bootstrap_names_extend_lookup_ceiling(self):
        expected=expected_exports(ROOT)
        for name in ('cuInit','cuDriverGetVersion','cuDeviceGetCount','cuGetProcAddress_v2'):
            self.assertEqual(expected[name]['lookup_ranges'][0]['maximum'],12090)
        self.assertEqual(expected['cuGetProcAddress']['lookup_ranges'][0]['maximum'],11999)
        self.assertEqual(expected['cuMemcpyHtoD_v2']['lookup_ranges'][0]['maximum'],12000)
        self.assertEqual(validate_profile(self.data,ROOT),[])
    def test_runtime_and_streams_declare_only_implemented_bounded_scope(self):
        features={f['id']:f for f in self.data['features']}
        for name in ('runtime','streams'):
            self.assertEqual(features[name]['state'],'experimental')
            self.assertEqual(features[name]['limits']['implementation'],'partial')
        self.assertEqual(features['streams']['limits']['scope'],'Runtime-owned logical streams only; no native queue overlap')
        self.assertFalse(features['streams']['limits']['driver_streams'])
        self.assertEqual(features['driver.streams']['state'],'unsupported')
        self.assertFalse(features['runtime']['limits']['general_cuda_compatibility'])
        self.assertEqual(features['product.virtual_target']['limits']['target'],'ct-sm52-subset-v1')

    def test_multiline_resolver_entries_preserve_primary_version_ranges(self):
        expected = expected_exports(ROOT)
        for name, canonical, minimum in (
                ('cuDevicePrimaryCtxGetState', 'cuDevicePrimaryCtxGetState', 7000),
                ('cuDevicePrimaryCtxRelease_v2', 'cuDevicePrimaryCtxRelease', 11000)):
            self.assertEqual(expected[name]['lookup_ranges'], [
                dict(symbol=canonical, minimum=minimum, maximum=12000)])

    def test_reset_uses_v2_version_range_without_legacy_export(self):
        expected = expected_exports(ROOT)
        self.assertEqual(expected['cuDevicePrimaryCtxReset_v2']['lookup_ranges'], [
            dict(symbol='cuDevicePrimaryCtxReset', minimum=11000, maximum=12000)])
        self.assertNotIn('cuDevicePrimaryCtxReset', expected)

    def setUp(self):
        self.data = json.loads((ROOT / 'docs/compatibility/profile-v1.json').read_text(encoding='utf-8'))

    def test_flag_apis_keep_distinct_verified_floors(self):
        expected = expected_exports(ROOT)
        for name, canonical, minimum in [('cuCtxGetFlags','cuCtxGetFlags',7000),
                ('cuDevicePrimaryCtxSetFlags_v2','cuDevicePrimaryCtxSetFlags',11000)]:
            self.assertEqual(expected[name]['lookup_ranges'], [
                dict(symbol=canonical,minimum=minimum,maximum=12000)])
        self.assertNotIn('cuDevicePrimaryCtxSetFlags',expected)

    def test_current_profile_is_explicitly_bounded(self):
        self.assertEqual(validate_profile(self.data, ROOT), [])
        self.assertEqual(len(self.data['exports']), 50)
        self.assertEqual(next(e for e in self.data['exports'] if e['symbol']=='cuDriverGetVersion')['behavior'], 'NOT_SUPPORTED')
        self.assertTrue(all(f['state'] in ('experimental','unsupported') for f in self.data['features']))

    def test_rejects_export_signature_drift(self):
        for mutation in ('signature', 'missing', 'duplicate', 'lookup'):
            data = copy.deepcopy(self.data)
            if mutation=='signature': data['exports'][0]['signature_id'] += ' wrong'
            if mutation=='missing': data['exports'].pop()
            if mutation=='duplicate': data['exports'].append(data['exports'][0])
            if mutation=='lookup': data['exports'][0]['lookup_ranges'][0]['maximum'] += 1
            self.assertTrue(validate_profile(data, ROOT), mutation)

    def test_rejects_missing_or_escaping_test_reference(self):
        for reference in ('../outside#marker', '/absolute#marker', 'C:/local#marker', '.cache/private#marker',
                          'tests/no-such-file#marker', 'tests/test_ct_loader.py#no_such_marker', 'tests/\0#marker', ''):
            data=copy.deepcopy(self.data); data['features'][0]['test_ids']=[reference]
            self.assertTrue(validate_profile(data, ROOT), reference)
        data=copy.deepcopy(self.data);data['features'][0]['test_ids']=[]
        self.assertTrue(validate_profile(data, ROOT))

    def test_manifest_cannot_claim_execution_pass(self):
        for state in ('supported','pass','skip','not_run'):
            data=copy.deepcopy(self.data);data['features'][0]['state']=state
            self.assertTrue(validate_profile(data, ROOT))
        for data in (None, {}, {'schema_version':True}, {'schema_version':1,'exports':'wrong'}):
            self.assertTrue(validate_profile(data, ROOT))
        data=copy.deepcopy(self.data);data['execution_status']='pass'
        self.assertTrue(validate_profile(data, ROOT))


if __name__ == '__main__': unittest.main()
