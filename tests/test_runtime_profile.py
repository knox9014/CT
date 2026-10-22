"""Validate the explicit bounded Runtime contract and reject profile drift."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import check_runtime_profile as profile

class RuntimeProfileTests(unittest.TestCase):
    def test_profile_rejects_drift_duplicates_missing_and_escaped_references(self):
        value = json.loads((profile.REPO / profile.PROFILE).read_text())
        self.assertEqual(profile.validate(value), [])
        for change in ('missing', 'duplicate', 'signature', 'escape', 'extra'):
            bad = copy.deepcopy(value)
            if change == 'missing': bad['exports'].pop()
            if change == 'duplicate': bad['exports'].append(bad['exports'][0])
            if change == 'signature': bad['exports'][0]['signature_id'] = 'wrong'
            if change == 'escape': bad['exports'][0]['test_ids'] = ['../outside#test']
            if change == 'extra': bad['extra'] = True
            with self.subTest(change=change): self.assertTrue(profile.validate(bad))

if __name__ == '__main__': unittest.main()
