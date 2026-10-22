"""Validate the explicit bounded Runtime contract and reject profile drift."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import check_runtime_profile as profile

class RuntimeProfileTests(unittest.TestCase):
    def test_kernel_profile_has_exact21_and_no_default22(self):
        self.assertEqual(len(profile.SIGNATURES),21)
        self.assertIn('__cudaRegisterFatBinary',profile.SIGNATURES)
        self.assertIn('__cudaPushCallConfiguration',profile.SIGNATURES)
        self.assertNotIn('__cudaRegisterVar',profile.SIGNATURES)
    def test_runtime_header_closure_rejects_missing_or_modified_dependency(self):
        import tempfile,hashlib
        from check_runtime_header_closure import check
        cache=profile.REPO/'.cache/p09a-implementation/profile-tests';cache.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as name:
            root=Path(name);(root/'runtime').mkdir();(root/'support/crt').mkdir(parents=True)
            a=root/'runtime/a.h';b=root/'support/crt/b.h';a.write_bytes(b'A');b.write_bytes(b'B')
            lock={'tools':[{'id':'cuda-runtime-headers','files':{'a.h':hashlib.sha256(b'A').hexdigest()}},
                           {'id':'cuda-nvcc-support-headers','files':{'b.h':hashlib.sha256(b'B').hexdigest()}}]}
            deps={'Data':{'Includes':[str(a),str(b)]}}
            self.assertEqual(check(deps,root,lock),[])
            self.assertTrue(check({'Data':{'Includes':[str(a)]}},root,lock))
            b.write_bytes(b'changed');self.assertTrue(check(deps,root,lock))

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
