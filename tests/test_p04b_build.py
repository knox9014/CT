import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import run_p04b_smoke as build
class SymbolBuildTests(unittest.TestCase):
    def test_original_symbol_build_is_default_device_runtime(self):
        root=Path('repository').resolve();producer=root/'.cache/base/manifest.json';folder=root/'.cache/p04b-smoke/id'
        host={'host':{'tools':{'cl.exe':{'path':str(root/'host/cl.exe')}}}}
        commands=build.compiler_commands(producer,folder,host,root)
        self.assertEqual(len([c for c in commands if c['name']=='host']),1)
        args=next(c['argv'] for c in commands if c['name']=='host')
        self.assertIn('--cudart=shared',args)
        self.assertNotIn('--cudadevrt=none',args)
        self.assertIn('symbol_runtime.cu',args)
        for name in ('reference','declared','native','noop','missing','forwarded','ct_foreign'):
            self.assertIn(name,[c['name'] for c in commands])
