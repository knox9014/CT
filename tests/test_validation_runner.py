"""Exercise real subprocess boundaries without GPU or vendor tools."""
from pathlib import Path
import sys
import tempfile
import unittest
import hashlib
import zipfile
import json
import copy
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from run_validation import execute, steps, corpus_outcome, configuration, validate_lane_bundle
from run_validation import runtime_evidence
from compatibility_registry import canonical_hash
from prepare_spirv_tools import extract_pinned


class RunnerTests(unittest.TestCase):
    def test_successful_child_without_native_artifacts_is_rejected(self):
        cache=ROOT/'.cache/runner-tests';cache.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as d:
            directory=Path(d)
            self.assertTrue(runtime_evidence(directory,ROOT,'arc.runtime'))
            (directory/'runtime-native-manifest.json').write_text('{"status":"pass"}')
            self.assertTrue(runtime_evidence(directory,ROOT,'arc.runtime'))
            self.assertTrue(runtime_evidence(directory,ROOT,'arc.runtime_abi'))
    def test_runtime_gates_use_nested_workspace_and_are_required(self):
        allsteps=steps('combined',Path('validator'),Path('lock'))
        cases={name:command for name,_,command in allsteps}
        for name in ('cpu.runtime_fmt','cpu.runtime_clippy','cpu.runtime_rust','cpu.runtime_profile','arc.runtime_abi','arc.runtime'):
            self.assertIn(name,cases)
        for name in ('cpu.runtime_fmt','cpu.runtime_clippy','cpu.runtime_rust'):
            self.assertIn('crates/ct-cudart/Cargo.toml',cases[name])
        self.assertIn('--locked',cases['cpu.runtime_rust'])
        self.assertEqual(len(allsteps),52)
        for name in ('producer.nvcc_fatbin','arc.runtime_kernel_abi','arc.runtime_kernel','producer.default_device_runtime','arc.runtime_default_abi','arc.runtime_default'):
            self.assertIn(name,cases)

    def test_kernel_child_success_without_bound_artifacts_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as name:
            directory=Path(name)
            for case,label in [('arc.runtime_kernel_abi','kernel-abi'),('arc.runtime_kernel','kernel-native'),('arc.runtime_default_abi','default-abi'),('arc.runtime_default','default-native')]:
                (directory/('runtime-'+label+'-manifest.json')).write_text('{"status":"pass"}')
                self.assertTrue(runtime_evidence(directory,ROOT,case))

    def test_stale_kernel_evidence_pointer_is_cleared_before_execution(self):
        import run_validation as runner
        self.assertTrue(hasattr(runner,'clear_runtime_evidence'))
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as name:
            root=Path(name);(root/'.cache').mkdir()
            for case,pointer in [('arc.runtime_kernel_abi','p09a2-abi-latest.json'),('arc.runtime_kernel','p09a2-kernel-latest.json'),('arc.runtime_default_abi','p09a2c-abi-latest.json'),('arc.runtime_default','p09a2c-default-latest.json')]:
                p=root/'.cache'/pointer;p.write_text('{"status":"pass"}')
                runner.clear_runtime_evidence(root,case);self.assertFalse(p.exists())
    def test_combined_ignored_decoder_test_uses_configured_inputs(self):
        import run_validation as runner
        self.assertTrue(hasattr(runner,'execution_environment'))
        env=runner.execution_environment(ROOT,'combined.all')
        self.assertEqual(env['CT_NVCC_COMPRESSED'],str(ROOT/'.cache/p09a2-producer/keep-compressed/vector.fatbin'))
        self.assertEqual(env['CT_NVCC_PLAIN'],str(ROOT/'.cache/p09a2-producer/keep-plain/vector.fatbin'))

    def test_kernel_capture_requires_independent_reexecution_and_propagates_failure(self):
        import run_validation as runner
        for case,module,function,cache_name in [
            ('arc.runtime_kernel_abi','runtime_kernel_abi_evidence','audit','p09a2-build'),
            ('arc.runtime_kernel','p09a2_kernel_check','audit_manifest','p09a2-kernel'),
            ('arc.runtime_default_abi','runtime_default_abi_evidence','audit','p09a2c-build'),
            ('arc.runtime_default','p09a2c_default_check','audit_manifest','p09a2c-kernel'),
            ('arc.global_abi','p04a_abi_evidence','audit','p04a-abi'),
            ('arc.global_driver','p04a_evidence','audit_manifest','p04a-smoke'),
            ('arc.runtime_global','p04a_evidence','audit_manifest','p04a-smoke'),
            ('arc.runtime_symbol_abi','p04b_evidence','audit_abi','p04b-smoke'),
            ('arc.runtime_symbol','p04b_evidence','audit_manifest','p04b-smoke'),
            ('arc.runtime_global_u64','p04c_evidence','audit_manifest','p04c-smoke')]:
            with self.subTest(case=case),tempfile.TemporaryDirectory(dir=ROOT/'.cache') as name:
                root=Path(name);report=root/'report';report.mkdir();artifact=root/'.cache'/cache_name/'probe.json'
                artifact.parent.mkdir(parents=True);artifact.write_text('{"status":"pass"}')
                pointer=root/'.cache'/runner.RUNTIME_EVIDENCE[case][3]
                pointer.write_text(json.dumps({'manifest':artifact.relative_to(root).as_posix()}))
                with patch(module+'.'+function,return_value=['independent failure']) as audit:
                    self.assertEqual(runtime_evidence(report,root,case,capture=True),['independent failure'])
                    audit.assert_called_once_with(report/('runtime-'+runner.RUNTIME_EVIDENCE[case][2]+'-manifest.json'),root,execute=True)

    def test_default_producer_snapshot_rejects_new_child_claim(self):
        from run_validation import default_producer_evidence
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as name:
            root=Path(name);report=root/'report';report.mkdir();origin=root/'.cache/p09a2c-producer/manifest.json'
            origin.parent.mkdir(parents=True);origin.write_text('{"scope":"original"}')
            with patch('prepare_nvcc_default.audit_default_producer',return_value=[]):
                self.assertEqual(default_producer_evidence(report,root,capture=True),[])
                origin.write_text('{"status":"pass"}')
                self.assertEqual(default_producer_evidence(report,root),['default producer evidence changed'])

    def test_producer_snapshot_cannot_be_replaced_by_new_child_claim(self):
        from run_validation import producer_evidence
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as name:
            root=Path(name);report=root/'report';report.mkdir();origin=root/'.cache/p09a2-producer/manifest.json'
            origin.parent.mkdir(parents=True);origin.write_text('{"fixture":1}')
            with patch('prepare_nvcc_probe.audit_probe',return_value=[]):
                self.assertEqual(producer_evidence(report,root,capture=True),[])
                origin.write_text('{"fixture":2}')
                self.assertTrue(producer_evidence(report,root))

    def test_bundle_cannot_select_its_own_expected_toolchain(self):
        cache=ROOT/'.cache/runner-tests';cache.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as d:
            directory=Path(d)
            lock=json.loads((ROOT/'docs/compatibility/toolchain-lock-v1.json').read_text())
            coverage=json.loads((ROOT/'docs/compatibility/coverage-v1.json').read_text())
            config=configuration(ROOT,'validator',steps('validator',Path('tool'),Path('lock')))
            env=dict(schema_version=1,os='Windows',host_abi='x64',gpu_model=None,driver_version=None,
                     runtime_versions={},compiler_versions={})
            report=dict(schema_version=1,source_commit='a'*40,target_profile='arc-preview-foundation',lane='validator',
                environment_id=canonical_hash(env),toolchain_lock_sha256=canonical_hash(lock),
                test_catalog_sha256=canonical_hash(coverage['test_catalog']),configuration_sha256=canonical_hash(config),
                cases=[dict(case_id=c['case_id'],test_id=c['test_id'],execution_kind=c['execution_kind'],
                    application_id=None,status='pass',reason='passed',artifact_hashes={},tool_ids=c['tool_ids']) for c in config['cases']])
            source=dict(source_commit='a'*40,source_tree_sha256='b'*64,clean=True,release_claim=False)
            for name,value in [('report.json',report),('environment.json',env),('configuration.json',config),
                               ('toolchain-lock.json',lock),('source.json',source)]:
                (directory/name).write_text(json.dumps(value))
            kwargs=dict(expected_commit='a'*40,expected_tree='b'*64,expected_clean=True)
            self.assertEqual(validate_lane_bundle(directory,ROOT,'validator',**kwargs)[0],[])
            changed=copy.deepcopy(lock);changed['tools'][0]['artifact_sha256']='c'*64
            (directory/'toolchain-lock.json').write_text(json.dumps(changed))
            report['toolchain_lock_sha256']=canonical_hash(changed)
            (directory/'report.json').write_text(json.dumps(report))
            self.assertTrue(validate_lane_bundle(directory,ROOT,'validator',**kwargs)[0])

    def test_capture_and_negative_controls_keep_their_actual_meaning(self):
        child=[dict(case_id='scalar',status='not_run',reason='capture_only',feature_supported=False)]
        result=corpus_outcome(child,case_id='scalar',expected_class='unsupported',expected_hash='a'*64)
        self.assertEqual(result,dict(status='not_run',reason='capture_only'))
        child[0].update(status='pass',reason='passed',input_sha256='a'*64)
        self.assertEqual(corpus_outcome(child,case_id='scalar',expected_class='unsupported',expected_hash='a'*64)['status'],'pass')
        self.assertEqual(corpus_outcome(child,case_id='scalar',expected_class='supported',expected_hash='a'*64)['status'],'fail')
        self.assertEqual(corpus_outcome(child,case_id='scalar',expected_class='unsupported',expected_hash='b'*64)['status'],'fail')

    def test_producer_lane_builds_translator_and_excludes_capture_only(self):
        names=[name for name,_,_ in steps('producer',Path('validator'),Path('lock'))]
        self.assertIn('producer.build',names)
        self.assertNotIn('producer.capture',names)

    def test_source_archives_reject_tamper_and_escape(self):
        cache=ROOT/'.cache/runner-tests';cache.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as d:
            directory=Path(d);archive=directory/'source.zip';destination=directory/'extract'
            with zipfile.ZipFile(archive,'w') as z:z.writestr('source/file.txt','source')
            digest=hashlib.sha256(archive.read_bytes()).hexdigest()
            with self.assertRaises(ValueError):extract_pinned(archive,'0'*64,destination)
            extract_pinned(archive,digest,destination)
            self.assertEqual((destination/'source/file.txt').read_text(),'source')
            with zipfile.ZipFile(archive,'w') as z:z.writestr('../outside.txt','escape')
            with self.assertRaises(ValueError):
                extract_pinned(archive,hashlib.sha256(archive.read_bytes()).hexdigest(),destination)
            self.assertFalse((directory/'outside.txt').exists())

    def test_exit_timeout_and_unavailable_are_not_passes(self):
        cache=ROOT/'.cache/runner-tests';cache.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as d:
            log=Path(d)/'run.log'
            for command,reason in (([sys.executable,'-c','raise SystemExit(1)'],'test_failed'),
                ([sys.executable,'-c','import time; time.sleep(5)'],'tool_timeout'),
                ([str(Path(d)/'missing.exe')],'tool_unavailable')):
                result=execute(command,cwd=ROOT,log=log,timeout_s=1)
                self.assertEqual(result,dict(status='fail',reason=reason))
            self.assertEqual(execute([sys.executable,'-c','print(123)'],cwd=ROOT,log=log,timeout_s=10),
                             dict(status='pass',reason='passed'))


if __name__=='__main__':unittest.main()
