"""Candidate identity and required execution lanes cannot be inferred from names."""
import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from check_integration_audit import validate_stack, validate_integration_report


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.stack = dict(schema_version=1, source_baseline='a'*40, base_commit='b'*40,
            pull_requests=[dict(id=1, base=None, head='c'*40, depends_on=[], review_baseline='b'*40),
                           dict(id=2, base=1, head='d'*40, depends_on=[1], review_baseline='c'*40)])
        self.report = dict(schema_version=1, candidate_commit='e'*40, source_tree_sha256='f'*64,
            clean=True, release_claim=False, remote_snapshot_status='not_run', remote_heads={},
            required_lanes=['cpu','validator'], lane_reports=[
                dict(lane='cpu', source_commit='e'*40, source_tree_sha256='f'*64,
                     cases=[dict(case_id='cpu.rust',status='pass')]),
                dict(lane='validator', source_commit='e'*40, source_tree_sha256='f'*64,
                     cases=[dict(case_id='validator.real',status='pass')])])

    def audit(self, report, stack, **kwargs):
        kwargs.setdefault('expected_cases', {'cpu':{'cpu.rust'},'validator':{'validator.real'}})
        return validate_integration_report(report,stack,**kwargs)

    def test_valid_static_graph_and_local_candidate(self):
        self.assertEqual(validate_stack(self.stack), [])
        self.assertEqual(self.audit(self.report, self.stack), [])

    def test_cycles_unknown_base_and_stale_remote_heads(self):
        for mutation in ('cycle','unknown','duplicate'):
            s = copy.deepcopy(self.stack)
            if mutation=='cycle': s['pull_requests'][0].update(base=2, depends_on=[2])
            if mutation=='unknown': s['pull_requests'][1].update(base=99, depends_on=[99])
            if mutation=='duplicate': s['pull_requests'].append(s['pull_requests'][0])
            self.assertTrue(validate_stack(s), mutation)
        self.report.update(remote_snapshot_status='observed',remote_heads={'1':'c'*40,'2':'0'*40})
        self.assertTrue(self.audit(self.report,self.stack))

    def test_required_lanes_and_exact_source(self):
        for mutation in ('missing','not_run','commit','tree','empty'):
            r = copy.deepcopy(self.report)
            if mutation=='missing': r['lane_reports'].pop()
            if mutation=='not_run': r['lane_reports'][1]['cases'][0]['status']='not_run'
            if mutation=='commit': r['lane_reports'][0]['source_commit']='0'*40
            if mutation=='tree': r['lane_reports'][0]['source_tree_sha256']='0'*64
            if mutation=='empty': r['lane_reports'][0]['cases']=[]
            self.assertTrue(self.audit(r,self.stack),mutation)

    def test_dirty_candidate_and_unverified_identity_cannot_release(self):
        self.report['release_claim']=True
        self.assertTrue(self.audit(self.report,self.stack))
        self.report['clean']=False
        self.assertTrue(self.audit(self.report,self.stack,
            expected_candidate='e'*40,expected_tree='f'*64))

    def test_required_lanes_cannot_substitute_dummy_cases(self):
        self.report['lane_reports'][0]['cases']=[dict(case_id='dummy',status='pass')]
        self.assertTrue(self.audit(self.report,self.stack,
            expected_cases={'cpu':{'cpu.rust'},'validator':{'validator.real'}}))

    def test_independent_clean_state_is_required_even_for_local_audit(self):
        self.assertTrue(self.audit(self.report,self.stack,expected_clean=False))


if __name__ == '__main__': unittest.main()
