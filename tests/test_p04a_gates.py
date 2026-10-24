from pathlib import Path
import sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from run_validation import steps,runtime_evidence,clear_runtime_evidence
OLD_CASES=('cpu.fmt', 'cpu.clippy', 'cpu.rust', 'cpu.python', 'cpu.registry', 'cpu.profile', 'cpu.publication', 'cpu.runtime_fmt', 'cpu.runtime_clippy', 'cpu.runtime_rust', 'cpu.runtime_profile', 'validator.build', 'validator.real', 'producer.build', 'producer.scalar', 'producer.multi_entry', 'producer.address_control', 'producer.block_candidate', 'producer.vector_add', 'producer.nvcc_fatbin', 'producer.default_device_runtime', 'arc.build', 'arc.levelzero.abi', 'arc.cuda.abi', 'arc.native', 'arc.m3k_memory', 'arc.m3l_arithmetic', 'arc.m3m_predicates', 'arc.m3n_minmax', 'arc.m3o_immediates', 'arc.consumers', 'arc.primary', 'arc.reset', 'arc.libraries', 'arc.context_destroy', 'arc.device_memory', 'arc.memory_queries', 'arc.runtime_abi', 'arc.runtime', 'arc.runtime_kernel_abi', 'arc.runtime_kernel', 'arc.runtime_default_abi', 'arc.runtime_default', 'combined.all')
NEW={'validator.global_u32','arc.global_abi','arc.global_driver','arc.runtime_global'}
class GlobalGateTests(unittest.TestCase):
    def test_exact_48_retains_every_old_id(self):
        selected=steps('combined',Path('validator'),Path('lock'));ids=[n for n,_,_ in selected]
        self.assertEqual(len(ids),48);self.assertEqual(set(ids),set(OLD_CASES)|NEW)
        commands={n:c for n,_,c in selected};self.assertIn('scripts/check_global_spirv.py',commands['validator.global_u32'])
    def test_forged_success_and_stale_pointers(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as d:
            folder=Path(d)
            for case,label in [('arc.global_abi','global-abi'),('arc.global_driver','global-driver'),('arc.runtime_global','global-runtime')]:
                (folder/('runtime-'+label+'-manifest.json')).write_text('{"status":"pass"}')
                self.assertTrue(runtime_evidence(folder,ROOT,case))
            fake=folder/'root';(fake/'.cache').mkdir(parents=True)
            for case,pointer in [('arc.global_abi','p04a-abi-latest.json'),('arc.global_driver','p04a-driver-latest.json'),('arc.runtime_global','p04a-runtime-latest.json')]:
                p=fake/'.cache'/pointer;p.write_text('{"manifest":"old"}');clear_runtime_evidence(fake,case);self.assertFalse(p.exists())
if __name__=='__main__':unittest.main()
