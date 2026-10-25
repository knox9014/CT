"""Boundary and tamper tests; mocks here never count as native evidence."""
import copy,json,sys,tempfile,unittest,shutil
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from p04a_evidence import audit_manifest, expected_payloads, verify_mode,ARTIFACTS,MODES,DIRECT
from run_p04a_smoke import SOURCES,CASES,compiler_commands,rust_commands
from prepare_nvcc_probe import digest
from run_validation import source_fingerprint
from p04a_runtime_check import expected
class GlobalEvidenceTests(unittest.TestCase):
    def test_closed_schema_cannot_accept_child_success(self):
        cache=ROOT/'.cache/p04a-smoke';cache.mkdir(exist_ok=True,parents=True)
        with tempfile.TemporaryDirectory(dir=cache) as d:
            p=Path(d)/'manifest.json';p.write_text(json.dumps(dict(status='pass',scope='diagnostic_p04a_globals')))
            self.assertTrue(audit_manifest(p,ROOT))
    def test_noop_must_be_numeric_and_have_intact_guards(self):
        value=expected(19);self.assertTrue(verify_mode('noop',value,19))
        initial=[((19*3+i*11)^0x13579bdf)&0xffffffff for i in range(145)]
        value['runs']=[initial.copy() for _ in range(100)]
        self.assertEqual(verify_mode('noop',value,19),[])
        bad=copy.deepcopy(value);bad['errors'][0]=35;self.assertTrue(verify_mode('noop',bad,19))
        bad=copy.deepcopy(value);bad['runs'][99][144]^=1;self.assertTrue(verify_mode('noop',bad,19))
        bad=copy.deepcopy(value);bad['inputs'][64]^=1;self.assertTrue(verify_mode('noop',bad,19))
    def test_bundle_roles_are_fixed(self):
        self.assertEqual(expected_payloads('positive'),{'host.exe':'host.exe','nvcuda.dll':'ct_cuda.dll','cudart64_12.dll':'ct_cudart.dll'})
        self.assertIn('global_runtime.fatbin',expected_payloads('forwarded'))
        self.assertEqual(expected_payloads('old_missing')['compressed.exe'],'producer_application')
if __name__=='__main__':unittest.main()

class GlobalArtifactTamperTests(unittest.TestCase):
    def setUp(self):
        cache=ROOT/'.cache/p04a-smoke';cache.mkdir(exist_ok=True,parents=True)
        self.temp=tempfile.TemporaryDirectory(dir=cache);self.addCleanup(self.temp.cleanup);self.folder=Path(self.temp.name)
        f=self.folder;producer=f/'producer';producer.mkdir();(producer/'compressed.exe').write_bytes(b'old executable')
        self.producer=producer/'manifest.json';base={'host':{'profile':'diagnostic','tools':{'cl.exe':{'path':str(f/'compiler/cl.exe')}}}};self.producer.write_text(json.dumps(base))
        self.pe=patch('p04a_evidence.inspect_pe',return_value={'imports':[{'library':'cudart64_12.dll','symbols':['__cudaRegisterVar','cudaLaunchKernel','__cudaRegisterFatBinary','__cudaRegisterFunction']}]});self.pe.start();self.addCleanup(self.pe.stop)
        self.auth=patch('p04a_evidence.audit_probe',return_value=[]);self.auth.start();self.addCleanup(self.auth.stop)
        for name in ARTIFACTS:(f/name).write_bytes(name.encode())
        self.item=lambda p:dict(path=p.relative_to(ROOT).as_posix(),sha256=digest(p))
        for source in SOURCES[:2]:shutil.copyfile(ROOT/source,f/Path(source).name)
        outputs={}
        for stem,_,_ in CASES:
            (f/('keep-'+stem)).mkdir()
            for suffix in ('.ptx','.fatbin','.cudafe1.stub.c'):
                name=f'keep-{stem}/{stem}{suffix}';(f/name).write_text('ct_counter ct_zero ct_unused ld.volatile.global st.volatile.global __cudaRegisterVar .global .align 8 .b8 ct_used_global[16]; ld.volatile.global.u8 __cudaRegisterVariable(t, ct_used_global, 0, 16Ui64, 0, 0)',encoding='utf-8');outputs[name]=digest(f/name)
        for stem,exe,default in CASES:
            if default:
                name=f'keep-{stem}/{exe}_dlink.fatbin';(f/name).write_bytes(b'device runtime image');outputs[name]=digest(f/name)
        for target,name in [('driver-target','ct_cuda.dll'),('runtime-target','ct_cudart.dll')]:
            (f/target/'debug').mkdir(parents=True);shutil.copyfile(f/name,f/target/'debug'/name)
        m=dict(schema_version=1,scope='diagnostic_p04a_globals',release_claim=False,source_tree=source_fingerprint(ROOT),inputs={n:digest(ROOT/n) for n in SOURCES},producer=self.item(self.producer),commands=compiler_commands(self.producer,f,base),rust_commands=rust_commands(f),artifacts={n:self.item(f/n) for n in ARTIFACTS},compiler_outputs=outputs,runs=[])
        files={n:f/n for n in ARTIFACTS};files.update(producer_application=producer/'compressed.exe',image=f/'keep-global_runtime/global_runtime.fatbin')
        for i,mode in enumerate(MODES):
            seed=19+i;value=expected(seed)
            if mode=='noop':value['runs']=[[((seed*3+j*11)^0x13579bdf)&0xffffffff for j in range(145)]]*100
            elif mode in ('missing','forwarded'):value=dict(error=35,memory_roundtrip=1)
            elif mode=='unsupported':value=dict(seed=seed,mode='used_global',errors=[801],runs=[],main_entered=1)
            out=f/(mode+'.stdout');err=f/(mode+'.stderr');out.write_bytes(b'vector results correct' if mode.startswith('old_') else json.dumps(value).encode());err.write_bytes(b'')
            bundle=f/('bundle-'+mode);bundle.mkdir();roles=expected_payloads(mode)
            for name,role in roles.items():shutil.copyfile(files[role],bundle/name)
            m['runs'].append(dict(mode=mode,seed=seed,exit_code=0,stdout=self.item(out),stderr=self.item(err),bundle=bundle.relative_to(ROOT).as_posix(),payloads={n:digest(files[r]) for n,r in roles.items()}))
        (f/'driver.stdout').write_text(json.dumps(DIRECT));(f/'driver.stderr').write_bytes(b'')
        m['direct_driver']=dict(exit_code=0,stdout=self.item(f/'driver.stdout'),stderr=self.item(f/'driver.stderr'))
        self.manifest=f/'manifest.json';self.good=m;self.save(m)
    def save(self,m):self.manifest.write_text(json.dumps(m),encoding='utf-8')
    def test_fixture_then_metadata_forgery_rejected(self):
        self.assertEqual(audit_manifest(self.manifest,ROOT),[])
        for mutate in [lambda m:m.update(source_tree='a'*64),lambda m:m['inputs'].update({SOURCES[0]:'b'*64}),lambda m:m['commands'][0]['argv'].append('--cudadevrt=none'),lambda m:m['runs'][0].update(exit_code=True),lambda m:m['runs'].pop(),lambda m:m['artifacts']['ct_cuda.dll'].update(path='../escape.dll'),lambda m:m.update(status='pass')]:
            bad=copy.deepcopy(self.good);mutate(bad);self.save(bad);self.assertTrue(audit_manifest(self.manifest,ROOT))
    def test_exe_dll_descriptors_and_raw_bytes_are_bound(self):
        for relative in ['host.exe','ct_cuda.dll','keep-global_runtime/global_runtime.ptx','positive.stdout','driver.stdout','bundle-noop/nvcuda.dll']:
            p=self.folder/relative;original=p.read_bytes();p.write_bytes(original+b'changed');self.assertTrue(audit_manifest(self.manifest,ROOT));p.write_bytes(original)
        self.assertEqual(audit_manifest(self.manifest,ROOT),[])
    def test_fresh_replay_uses_new_bundle_and_rehashes_originals(self):
        # A forged exit-zero/empty output cannot satisfy the replay oracle.
        import subprocess
        with patch('p04a_evidence.subprocess.run',return_value=subprocess.CompletedProcess([],0,b'{}',b'')) as child:
            self.assertTrue(audit_manifest(self.manifest,ROOT,execute=True));self.assertNotEqual(child.call_args.kwargs['cwd'],self.folder/'bundle-positive')
    def test_rehashed_forged_readback_still_fails_oracle(self):
        m=copy.deepcopy(self.good);p=self.folder/'positive.stdout';value=json.loads(p.read_bytes());value['runs'][2][65]^=1;p.write_text(json.dumps(value));m['runs'][0]['stdout']=self.item(p);self.save(m)
        self.assertTrue(audit_manifest(self.manifest,ROOT))

    def test_rehashed_binary_must_match_actual_rust_build_output(self):
        m=copy.deepcopy(self.good);p=self.folder/'ct_cuda.dll';p.write_bytes(b'substituted DLL');m['artifacts']['ct_cuda.dll']=self.item(p)
        for row in m['runs']:
            for name,role in expected_payloads(row['mode']).items():
                if role=='ct_cuda.dll':
                    target=ROOT/row['bundle']/name;shutil.copyfile(p,target);row['payloads'][name]=digest(p)
        self.save(m);self.assertTrue(audit_manifest(self.manifest,ROOT))

    def test_default_linker_images_are_required_artifacts(self):
        m=copy.deepcopy(self.good)
        for stem,exe,default in CASES:
            if default:
                name=f'keep-{stem}/{exe}_dlink.fatbin';(self.folder/name).write_bytes(b'device runtime image');m['compiler_outputs'][name]=digest(self.folder/name)
        self.save(m);self.assertEqual(audit_manifest(self.manifest,ROOT),[])
