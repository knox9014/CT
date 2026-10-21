"""Declarations are distinct from execution; provenance mismatches fail closed."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from compatibility_registry import (RegistryContext, canonical_hash, validate_applications,
    validate_configuration, validate_coverage, validate_environment, validate_report,
    validate_toolchain, validate_tool_execution)

TEST = 'tests/test_coverage_registry.py#test_static_registries'
COMMIT = 'a' * 40
HASH = 'b' * 64


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.coverage = dict(schema_version=1, source_baseline=COMMIT,
            test_catalog=[dict(id=TEST, kind='resolver')], features=[dict(
                id='driver.cuInit', category='abi', implementation='partial',
                limits={'scope': 'restricted'}, test_ids={'resolver': [TEST], 'behavior': []})])
        self.app = dict(id='consumer', execution_path='driver_external',
            evidence_tier='synthetic', inventory_state='pinned',
            source=dict(repository='https://example.com/ct', revision=COMMIT,
                        recipe_ref='tests/test_coverage_registry.py'),
            artifacts=[dict(role='executable', sha256=HASH, availability='local_only')],
            required_features=['driver.cuInit'], test_ids=[])
        self.tool = dict(id='compiler', pin_state='pinned', version='1.0',
            source_url='https://example.com/package', source_revision=None,
            artifact_sha256=HASH, platform='windows-x64',
            recipe_ref='tests/test_coverage_registry.py', files={'executable': HASH},
            validation_target=None)
        self.config = dict(schema_version=1, lane='cpu', cases=[dict(
            case_id='resolve-one', test_id=TEST, execution_kind='resolver',
            application_id=None, parameters={'seed': 42},
            artifact_requirements={}, tool_ids=[])])
        self.catalog = {TEST: dict(id=TEST, kind='resolver')}
        self.report = dict(schema_version=1, source_commit=COMMIT, target_profile='arc-preview',
            lane='cpu', environment_id=HASH, toolchain_lock_sha256=HASH,
            test_catalog_sha256=HASH, configuration_sha256=HASH, cases=[dict(
                case_id='resolve-one', test_id=TEST, execution_kind='resolver',
                application_id=None, status='pass', reason='passed', artifact_hashes={}, tool_ids=[])])

    def context(self):
        return RegistryContext(COMMIT, 'arc-preview', HASH, HASH, HASH, HASH,
            self.catalog, {c['case_id']: c for c in self.config['cases']},
            {'consumer': self.app}, {'compiler': self.tool}, frozenset({'resolve-one'}))

    def test_static_registries(self):
        self.assertEqual(validate_coverage(self.coverage, ROOT), [])
        self.assertEqual(validate_applications(dict(schema_version=1, source_baseline=COMMIT,
            applications=[self.app]), ROOT, {'driver.cuInit'}), [])

    def test_closed_coverage_and_duplicate_ids(self):
        for mutate in (lambda d: d.update(passed=True),
                       lambda d: d['features'].append(copy.deepcopy(d['features'][0])),
                       lambda d: d['test_catalog'].append(copy.deepcopy(d['test_catalog'][0])),
                       lambda d: d['features'][0].update(pass_count=1)):
            d = copy.deepcopy(self.coverage); mutate(d)
            self.assertTrue(validate_coverage(d, ROOT))

    def test_resolver_cannot_become_behavior(self):
        d = copy.deepcopy(self.coverage)
        d['features'][0]['test_ids'] = {'behavior': [TEST]}
        self.assertTrue(validate_coverage(d, ROOT))

    def test_unsafe_or_unknown_references(self):
        for ref in ('../outside#x', '/absolute#x', 'C:/local#x', '.cache/a#x',
                    'tests/missing#x', 'tests/\x00#x', TEST + 'missing'):
            d = copy.deepcopy(self.coverage); d['test_catalog'][0]['id'] = ref
            self.assertTrue(validate_coverage(d, ROOT), ref)
        d = copy.deepcopy(self.coverage); d['features'][0]['test_ids']['resolver'] = ['unknown']
        self.assertTrue(validate_coverage(d, ROOT))

    def test_candidate_and_unknown_features(self):
        original = copy.deepcopy(self.app)
        for field, value in (('required_features', ['unknown']), ('inventory_state', 'candidate'),
                             ('artifacts', [dict(role='executable', sha256=None, availability='missing')])):
            app = copy.deepcopy(original); app[field] = value
            if field == 'inventory_state':
                self.app = app
                self._application_case()
                self.assertTrue(validate_report(self.report, context=self.context()))
            else:
                self.assertTrue(validate_applications(dict(schema_version=1, source_baseline=COMMIT,
                    applications=[app]), ROOT, {'driver.cuInit'}))

    def _application_case(self):
        self.catalog[TEST]['kind'] = 'application'
        for case in (self.config['cases'][0], self.report['cases'][0]):
            case.update(execution_kind='application', application_id='consumer')
        self.config['cases'][0]['artifact_requirements'] = {'executable': HASH}
        self.report['cases'][0]['artifact_hashes'] = {'executable': HASH}

    def test_report_accepts_only_matching_identity(self):
        self.assertEqual(validate_report(self.report, context=self.context()), [])
        for key in ('source_commit', 'target_profile', 'environment_id', 'toolchain_lock_sha256',
                    'test_catalog_sha256', 'configuration_sha256', 'lane'):
            d = copy.deepcopy(self.report); d[key] = 'wrong'
            self.assertTrue(validate_report(d, context=self.context()), key)

    def test_report_cases_are_exact_and_required(self):
        for cases in ([], [self.report['cases'][0]] * 2,
                      [dict(self.report['cases'][0], case_id='unknown')],
                      [dict(self.report['cases'][0], execution_kind='native')],
                      [dict(self.report['cases'][0], status='not_run', reason='not_run')]):
            d = copy.deepcopy(self.report); d['cases'] = cases
            self.assertTrue(validate_report(d, context=self.context()))

    def test_application_hash_and_tool_checks(self):
        self._application_case()
        self.assertEqual(validate_report(self.report, context=self.context()), [])
        self.report['cases'][0]['artifact_hashes']['executable'] = 'c' * 64
        self.assertTrue(validate_report(self.report, context=self.context()))
        self.report['cases'][0]['artifact_hashes']['executable'] = HASH
        self.config['cases'][0]['tool_ids'] = ['compiler']
        self.report['cases'][0]['tool_ids'] = ['compiler']
        self.assertEqual(validate_report(self.report, context=self.context()), [])
        self.tool['pin_state'] = 'unresolved'
        self.assertTrue(validate_report(self.report, context=self.context()))

    def test_configuration_and_environment(self):
        self.assertEqual(validate_configuration(self.config, test_catalog=self.catalog), [])
        d = copy.deepcopy(self.config); d['cases'][0]['execution_kind'] = 'native'
        self.assertTrue(validate_configuration(d, test_catalog=self.catalog))
        d = copy.deepcopy(self.config); d['cases'] *= 2
        self.assertTrue(validate_configuration(d, test_catalog=self.catalog))
        env = dict(schema_version=1, os='Windows', host_abi='x64', gpu_model='Intel Arc B390',
                   driver_version='1', runtime_versions={'level-zero': '1'}, compiler_versions={})
        self.assertEqual(validate_environment(env), [])
        env['hostname'] = 'private'
        self.assertTrue(validate_environment(env))
        self.assertEqual(canonical_hash({'a': 1, 'b': 2}), canonical_hash({'b': 2, 'a': 1}))
        self.assertNotEqual(canonical_hash({'seed': 1}), canonical_hash({'seed': 2}))

    def test_toolchain_pins_and_observations(self):
        data = dict(schema_version=1, source_baseline=COMMIT, tools=[self.tool])
        self.assertEqual(validate_toolchain(data), [])
        self.assertEqual(validate_tool_execution(self.tool, observed_platform='windows-x64',
            observed_hashes={'executable': HASH}, required=True), [])
        for field in ('version', 'source_url', 'artifact_sha256', 'files'):
            d = copy.deepcopy(data); d['tools'][0][field] = None
            self.assertTrue(validate_toolchain(d), field)
        self.assertTrue(validate_tool_execution(self.tool, observed_platform='linux-x64',
            observed_hashes={'executable': HASH}, required=True))
        self.assertTrue(validate_tool_execution(self.tool, observed_platform='windows-x64',
            observed_hashes={'executable': 'c' * 64}, required=True))
        self.tool.update(pin_state='unresolved', version=None, artifact_sha256=None, files={})
        self.assertEqual(validate_toolchain(data), [])
        self.assertEqual(validate_tool_execution(self.tool, observed_platform='windows-x64',
            observed_hashes={}, required=False), ['skipped:tool_unavailable'])
        self.assertEqual(validate_tool_execution(self.tool, observed_platform='windows-x64',
            observed_hashes={}, required=True), ['tool_unavailable'])

    def test_toolchain_recipe_stays_in_public_repository(self):
        for recipe in ('C:/local/build.ps1', '.cache/build.ps1', '../outside',
                       'docs/nonexistent.md'):
            t = copy.deepcopy(self.tool); t['recipe_ref'] = recipe
            self.assertTrue(validate_toolchain(dict(schema_version=1, source_baseline=COMMIT,
                tools=[t])), recipe)

    def test_tool_file_checker_observes_actual_platform(self):
        from check_toolchain_files import observed_platform
        with patch('check_toolchain_files.platform.system', return_value='Linux'):
            self.assertNotEqual(observed_platform(), 'windows-x64')
        with patch('check_toolchain_files.platform.system', return_value='Windows'), patch(
                'check_toolchain_files.platform.machine', return_value='AMD64'):
            self.assertEqual(observed_platform(), 'windows-x64')

    def test_malformed_values_fail_without_exceptions(self):
        for value in (None, [], True, {}, {'schema_version': True}):
            self.assertTrue(validate_coverage(value, ROOT))
            self.assertTrue(validate_applications(value, ROOT, set()))
            self.assertTrue(validate_configuration(value, test_catalog={}))
            self.assertTrue(validate_environment(value))
            self.assertTrue(validate_report(value, context=self.context()))
            self.assertTrue(validate_toolchain(value))
        for field in ('id', 'category', 'implementation', 'limits', 'test_ids'):
            d = copy.deepcopy(self.coverage); d['features'][0][field] = []
            self.assertTrue(validate_coverage(d, ROOT), field)

    def test_repository_declarations_cover_existing_contract(self):
        coverage = json.loads((ROOT / 'docs/compatibility/coverage-v1.json').read_text())
        apps = json.loads((ROOT / 'docs/compatibility/applications.json').read_text())
        self.assertEqual(validate_coverage(coverage, ROOT), [])
        ids = {f['id'] for f in coverage['features']}
        self.assertEqual(validate_applications(apps, ROOT, ids), [])
        from check_compatibility_profile import expected_exports
        profile = json.loads((ROOT / 'docs/compatibility/profile-v1.json').read_text())
        self.assertTrue({'driver.' + e for e in expected_exports(ROOT)} <= ids)
        self.assertTrue({f['id'] for f in profile['features']} <= ids)
        self.assertEqual({a['execution_path'] for a in apps['applications']},
            {'driver_external', 'runtime_dynamic', 'runtime_static', 'block_parallel', 'library', 'jit'})


if __name__ == '__main__':
    unittest.main()
