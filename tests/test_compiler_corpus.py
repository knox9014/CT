"""Producer fixtures keep original bytes and reviewed expectations separate."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import subprocess

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from run_compiler_corpus import CorpusContext, run_case, validate_corpus, verify_fixture


class CorpusTests(unittest.TestCase):
    def setUp(self):
        cache = ROOT / '.cache/corpus-tests'; cache.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=cache)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        folder = self.root / 'tests/corpus'; folder.mkdir(parents=True)
        (folder / 'source.cu').write_text('extern "C" __global__ void k() {}')
        recipe = dict(schema_version=1, source_ref='tests/corpus/source.cu', tool_id='nvrtc', options=[])
        (folder / 'recipe.json').write_text(json.dumps(recipe))
        h = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
        self.bytes = b'original PTX'
        self.case = dict(id='scalar', source_ref='tests/corpus/source.cu', source_sha256=h(folder/'source.cu'),
            recipe_ref='tests/corpus/recipe.json', recipe_sha256=h(folder/'recipe.json'), tool_id='nvrtc',
            options=[], output_sha256=hashlib.sha256(self.bytes).hexdigest(), capture_state='captured',
            expected_class='unsupported', expected_rejection=dict(stage='translation',category='unsupported'),
            required_features=['ptx.module'], evidence_tier='synthetic')
        self.context = CorpusContext(self.root, self.root/'cache', {}, {}, self.root/'translator.exe',
                                     self.root/'validator.exe', None)
        self.fixture = self.context.cache_root / 'sha256' / (self.case['output_sha256'] + '.ptx')
        self.fixture.parent.mkdir(parents=True)
        self.fixture.write_bytes(self.bytes)

    def manifest(self, case=None):
        return dict(schema_version=1, source_baseline='a'*40, cases=[case or self.case])

    def test_provenance_and_closed_schema(self):
        self.assertEqual(validate_corpus(self.manifest(), self.root, {'nvrtc'}), [])
        for key in ('source_sha256', 'recipe_sha256', 'tool_id', 'output_sha256', 'options'):
            c = copy.deepcopy(self.case); c.pop(key)
            self.assertTrue(validate_corpus(self.manifest(c), self.root, {'nvrtc'}), key)
        for ref in ('../outside', '.cache/private', 'tests/nonexistent.cu'):
            c = copy.deepcopy(self.case); c['source_ref'] = ref
            self.assertTrue(validate_corpus(self.manifest(c), self.root, {'nvrtc'}))
        (self.root/'tests/corpus/recipe.json').write_text('{}')
        self.assertTrue(validate_corpus(self.manifest(), self.root, {'nvrtc'}))

    def test_replay_never_compiles_and_tamper_fails(self):
        self.assertTrue(verify_fixture(self.bytes, self.case['output_sha256']))
        with patch('run_compiler_corpus.subprocess.run') as run:
            run.return_value = subprocess.CompletedProcess([], 3, b'', b'')
            result = run_case(self.case, mode='replay', required=True, context=self.context)
            self.assertEqual(result['status'], 'pass')
            self.assertFalse(result['feature_supported'])
            self.assertEqual(len(run.call_args_list), 1)
            self.fixture.write_bytes(self.bytes + b'!')
            self.assertEqual(run_case(self.case, mode='replay', required=True, context=self.context)['reason'],
                             'artifact_hash_mismatch')
            self.fixture.unlink()
            self.assertEqual(run_case(self.case, mode='replay', required=True, context=self.context)['reason'],
                             'artifact_missing')

    def test_only_explicit_unsupported_satisfies_negative_expectation(self):
        with patch('run_compiler_corpus.subprocess.run') as run:
            for code in (0, 1, 2):
                run.return_value = subprocess.CompletedProcess([], code, b'', b'')
                self.assertEqual(run_case(self.case, mode='replay', required=True, context=self.context)['status'], 'fail')

    def test_pending_is_not_a_compatibility_pass(self):
        c = copy.deepcopy(self.case)
        c.update(capture_state='pending', output_sha256=None, expected_class=None, expected_rejection=None)
        self.assertEqual(validate_corpus(self.manifest(c), self.root, {'nvrtc'}), [])
        self.assertEqual(run_case(c, mode='replay', required=True, context=self.context)['status'], 'fail')
        self.assertEqual(run_case(c, mode='unknown', required=True, context=self.context)['reason'], 'input_invalid')

    def test_supported_output_requires_real_validator_success(self):
        self.case.update(expected_class='supported', expected_rejection=None)
        with patch('run_compiler_corpus.subprocess.run') as run, patch('run_compiler_corpus.run_validator') as val:
            run.return_value = subprocess.CompletedProcess([], 0, b'', b'')
            val.return_value = dict(status='fail',reason='validation_rejected')
            self.assertEqual(run_case(self.case, mode='replay', required=True, context=self.context)['status'], 'fail')
            val.return_value = dict(status='pass',reason='passed')
            self.assertTrue(run_case(self.case, mode='replay', required=True, context=self.context)['feature_supported'])

    def test_capture_cannot_load_an_unhashed_alternate_dll(self):
        folder = self.root / 'tools'; folder.mkdir()
        files = {}
        for name in ('nvrtc64_120_0.dll', 'nvrtc-builtins64_120.dll'):
            (folder/name).write_bytes(name.encode())
            files[name] = hashlib.sha256(name.encode()).hexdigest()
        other = folder/'other.dll'; other.write_bytes(b'unpinned')
        tools = {'nvrtc': dict(id='nvrtc', pin_state='pinned', platform='windows-x64', files=files)}
        context = CorpusContext(self.root, self.context.cache_root, tools, {'nvrtc': other},
            self.context.translator_path, self.context.validator_path, None)
        with patch('run_compiler_corpus.subprocess.run') as run, patch('run_compiler_corpus.platform.system', return_value='Windows'), patch('run_compiler_corpus.platform.machine', return_value='AMD64'):
            run.return_value = subprocess.CompletedProcess([], 1, b'', b'')
            result = run_case(self.case, mode='capture', required=True, context=context)
            self.assertEqual(result['reason'], 'tool_hash_mismatch')
            run.assert_not_called()


if __name__ == '__main__': unittest.main()
