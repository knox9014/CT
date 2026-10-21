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
    def test_multiline_resolver_entries_preserve_primary_version_ranges(self):
        expected = expected_exports(ROOT)
        for name, canonical, minimum in (
                ('cuDevicePrimaryCtxGetState', 'cuDevicePrimaryCtxGetState', 7000),
                ('cuDevicePrimaryCtxRelease_v2', 'cuDevicePrimaryCtxRelease', 11000)):
            self.assertEqual(expected[name]['lookup_ranges'], [
                dict(symbol=canonical, minimum=minimum, maximum=12000)])

    def setUp(self):
        self.data = json.loads((ROOT / 'docs/compatibility/profile-v1.json').read_text(encoding='utf-8'))

    def test_current_profile_is_explicitly_bounded(self):
        self.assertEqual(validate_profile(self.data, ROOT), [])
        self.assertEqual(len(self.data['exports']), 29)
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
