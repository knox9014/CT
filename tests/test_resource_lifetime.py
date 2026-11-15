import copy,hashlib,json,sys,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import lifecycle_check as c

class LifetimeTests(unittest.TestCase):
    def test_driver_rejects_changed_ptx_before_native_device_creation(self):
        import lifecycle_driver_worker as worker
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as name:
            folder=Path(name);(folder/'vector.ptx').write_bytes(b'changed PTX')
            with patch.object(worker.Path,'cwd',return_value=folder),patch.object(worker,'Device') as device:
                with self.assertRaises(worker.ContractError):worker.execute(193,8)
                device.assert_not_called()

    def test_raw_observation_refuses_fake_completion_provider_drift_and_extra_files(self):
        import run_resource_lifetime as r
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as name:
            folder=Path(name);bundle=folder/'resource-lifetime-runs/record';bundle.mkdir(parents=True)
            contents={'ct_cuda.dll':b'driver','lifetime-runtime.dll':b'runtime','lifecycle.exe':b'executable'}
            sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
            files={n:hashlib.sha256(b).hexdigest() for n,b in contents.items()}
            pins=r.payloads(files,'runtime','positive')
            for n,b in [('nvcuda.dll',b'driver'),('cudart64_12.dll',b'runtime'),('lifecycle.exe',b'executable')]:(bundle/n).write_bytes(b)
            value=c.runtime_header(193,256);value['rows']=[c.runtime_row(193,i,'positive') for i in range(256)]
            stdout=bundle/'stdout.json';stdout.write_text(json.dumps(value));(bundle/'stderr.txt').write_bytes(b'')
            row=dict(kind='runtime',mode='positive',seed=193,cycles=256,bundle='resource-lifetime-runs/record',command=r.argv(bundle,'runtime',193,256),files=pins,observations={n:sha(bundle/n) for n in ('stdout.json','stderr.txt')},exit_code=0,numerical=True)
            r.verify_run(folder,files,row)
            for fake in ({'status':'completed'},dict(value,rows=[c.runtime_row(193,i,'noop_launch') for i in range(256)])):
                stdout.write_text(json.dumps(fake));row['observations']['stdout.json']=sha(stdout)
                with self.assertRaises(ValueError):r.verify_run(folder,files,row)
            stdout.write_text(json.dumps(value));row['observations']['stdout.json']=sha(stdout)
            bad=copy.deepcopy(row);bad['files']['cudart64_12.dll']='f'*64
            with self.assertRaises(ValueError):r.verify_run(folder,files,bad)
            bad=copy.deepcopy(row);bad['exit_code']=True
            with self.assertRaises(ValueError):r.verify_run(folder,files,bad)
            (bundle/'unrecorded.txt').write_text('extra')
            with self.assertRaises(ValueError):r.verify_run(folder,files,row)

    def test_source_and_parent_drift_are_rejected_before_parent_audit(self):
        import run_resource_lifetime as r
        cache=ROOT/'.cache/runtime-attribute-runs';cache.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as name:
            folder=Path(name);(folder/'matrix-rounding-manifest.json').write_text('synthetic parent')
            value=dict(schema_version=1,scope=r.SCOPE,release_claim=False,source_fingerprint='a'*64,parent_sha256='b'*64,case_profile=r.PROFILE,commands={},files={},runs=[])
            p=folder/'resource-lifetime-manifest.json';p.write_text(json.dumps(value))
            for fp in ('a'*64,'c'*64):
                with patch.object(r,'source_fingerprint',return_value=fp),patch.object(r,'audit_parent') as parent:
                    with self.assertRaises(ValueError):r.audit(p)
                    parent.assert_not_called()

    def test_runtime_bundle_uses_separately_pinned_parent_nominal_runtime(self):
        import run_resource_lifetime as runner
        files={'ct_cuda.dll':'a'*64,'lifetime-runtime.dll':'b'*64,'lifecycle.exe':'c'*64}
        self.assertEqual(runner.payloads(files,'runtime','positive'),{'nvcuda.dll':'a'*64,'cudart64_12.dll':'b'*64,'lifecycle.exe':'c'*64})

    def test_worker_refuses_unqualified_cycles_before_loading_driver(self):
        import lifecycle_driver_worker as worker
        with patch.object(worker,'Device') as device:
            with self.assertRaises(ValueError):worker.execute(193,161)
            device.assert_not_called()
        with self.assertRaises(worker.ContractError):worker.expected(0,400,'duplicate_unload')

    def test_observation_set_and_scope_are_closed(self):
        import run_resource_lifetime as runner
        rows=[dict(kind=k,mode=m,seed=s,cycles=n) for k,m,s,n in runner.SCENARIOS]
        with patch.object(runner,'verify_run'):
            runner.check_runs(Path('.'),{},rows)
            for bad in (rows[:-1],list(reversed(rows)),[dict(r,cycles=1) for r in rows]):
                with self.assertRaises(ValueError):runner.check_runs(Path('.'),{},bad)
        cache=ROOT/'.cache/runtime-attribute-runs';cache.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as name:
            profile=copy.deepcopy(runner.PROFILE);profile['runtime_cycles']=1
            value=dict(schema_version=1,scope=runner.SCOPE,release_claim=False,source_fingerprint='a'*64,parent_sha256='b'*64,case_profile=profile,commands={},files={},runs=[])
            p=Path(name)/'resource-lifetime-manifest.json';p.write_text(json.dumps(value))
            with patch.object(runner,'source_fingerprint') as source,patch.object(runner,'audit_parent') as parent:
                with self.assertRaises(ValueError):runner.audit(p)
                source.assert_not_called();parent.assert_not_called()

    def test_runtime_raw_oracle_requires_all_words_errors_and_reclaimed_quotas(self):
        for mode in ('positive','noop_launch','noop_copy'):
            n=256 if mode=='positive' else 8
            v=c.runtime_header(193,n);v['rows']=[c.runtime_row(193,i,mode) for i in range(n)]
            self.assertTrue(c.validate_runtime(v,193,n,mode))
            self.assertEqual(c.validate_runtime(v,193,n,'positive'),mode=='positive')
            for key in ('stale_checks','recoverable_errors','budget_errors','replacements'):
                bad=copy.deepcopy(v);bad[key]-=1;self.assertFalse(c.validate_runtime(bad,193,n,mode))
            bad=copy.deepcopy(v);bad['rows'][-1][-1]^=1;self.assertFalse(c.validate_runtime(bad,193,n,mode))
            bad=copy.deepcopy(v);bad['rows'][0][1]=True;self.assertFalse(c.validate_runtime(bad,193,n,mode))
    def test_runtime_formula_has_independent_literal_expected_word_and_guards(self):
        row=c.runtime_row(193,0,'positive')
        expected=((193*7919)^0xa5a55a5a)&0xffffffff
        self.assertEqual(row[:3],[c.GUARD,c.GUARD,expected])
        self.assertEqual(row[36],(expected+17)&0xffffffff)
        self.assertEqual(len(row),70)
        self.assertTrue(all(row[i]==c.GUARD for i in (0,1,34,35,68,69)))
    def test_driver_oracle_rejects_omissions_corruption_and_short_cycles(self):
        for mode in ('positive','noop_launch','noop_copy'):
            n=160 if mode=='positive' else 8
            v=c.driver_header(731,n);v['rows']=[c.driver_row(731,i,mode) for i in range(n)]
            self.assertTrue(c.validate_driver(v,731,n,mode))
            self.assertEqual(c.validate_driver(v,731,n,'positive'),mode=='positive')
            bad=copy.deepcopy(v);bad['rows'][-1][0]^=1;self.assertFalse(c.validate_driver(bad,731,n,mode))
            bad=copy.deepcopy(v);bad['rows'].pop();self.assertFalse(c.validate_driver(bad,731,n,mode))
            bad=copy.deepcopy(v);bad['cleanup']=False;self.assertFalse(c.validate_driver(bad,731,n,mode))
    def test_closed_profiles_and_empty_completed_message_fail(self):
        for fn in (c.validate_runtime,c.validate_driver):
            self.assertFalse(fn({'status':'completed'},193,8,'positive'))
            self.assertFalse(fn({},True,8,'positive'))
        with self.assertRaises(ValueError):c.runtime_header(193,4097)
        with self.assertRaises(ValueError):c.driver_header(999,160)

if __name__=='__main__':unittest.main()
