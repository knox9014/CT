"""Runtime native evidence must be tied to artifacts and full observations."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import hashlib
import struct
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
sys.path.insert(0,str(ROOT/'tests'))
from p09a_runtime_check import audit_manifest

class EvidenceTests(unittest.TestCase):
    def test_complete_observations_are_bound_to_bytes_and_counters(self):
        from p09a_runtime_check import MODES
        from run_validation import source_fingerprint
        from check_runtime_profile import SIGNATURES
        from test_ct_loader import image
        cache=ROOT/'.cache/p09a-build';cache.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as name:
            d=Path(name);app=bytearray(image(symbol=b'cudaMalloc',library=b'cudart64_12.dll'))
            struct.pack_into('<I',app,512,0x1100);struct.pack_into('<I',app,528,0x1100)
            offset=1024
            for i,symbol in enumerate(SIGNATURES):
                struct.pack_into('<Q',app,768+i*8,0x1000+offset-512)
                raw=symbol.encode()+b'\0';app[offset:offset+2]=b'\0\0';app[offset+2:offset+2+len(raw)]=raw;offset+=2+len(raw)
            struct.pack_into('<Q',app,768+14*8,0)
            artifacts={}
            for role in ('application','driver','runtime','fake','noop_copy','noop_fill','underlying'):
                path=d/(role+'.bin');path.write_bytes(app if role=='application' else image(dll=True,library=b'kernel32.dll',symbol=b'GetCurrentProcess'))
                artifacts[role]=dict(path=path.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            value=dict(schema_version=1,case_id='arc.runtime',source_tree=source_fingerprint(ROOT),artifacts=artifacts,modes=[])
            for mode,expected in MODES.items():
                bundle=d/mode;bundle.mkdir();payloads={'host.exe':'application','cudart64_12.dll':'runtime'}
                if mode not in ('pure_no_driver','missing_driver'):payloads['nvcuda.dll']='fake' if mode=='missing_export' else mode if mode.startswith('noop_') else 'driver'
                if mode.startswith('noop_'):payloads['ct_underlying.dll']='underlying'
                for file,role in payloads.items():(bundle/file).write_bytes((ROOT/artifacts[role]['path']).read_bytes())
                out=d/(mode+'.stdout');err=d/(mode+'.stderr')
                out.write_text(json.dumps(dict(mode=mode,status='pass',checked_bytes=expected[0],observations=expected[1],seed=1)) if expected else '')
                err.write_bytes(b'oracle mismatch: copy' if mode=='noop_copy' else b'oracle mismatch: fill' if mode=='noop_fill' else b'')
                value['modes'].append(dict(mode=mode,seed=1,exit_code=0 if expected else 42,bundle=bundle.relative_to(ROOT).as_posix(),stdout=out.relative_to(ROOT).as_posix(),stderr=err.relative_to(ROOT).as_posix(),payloads=payloads))
            p=d/'manifest.json';p.write_text(json.dumps(value));self.assertEqual(audit_manifest(p),[])
            # Structurally complete claims still cannot pass required execution:
            # these synthetic PE bytes contain no executable consumer code.
            self.assertTrue(audit_manifest(p,execute=True))
            bad=copy.deepcopy(value);bad['modes'].pop();p.write_text(json.dumps(bad));self.assertTrue(audit_manifest(p))
            p.write_text(json.dumps(value));first=value['modes'][0];out=ROOT/first['stdout'];observed=json.loads(out.read_text());observed['observations']=0;out.write_text(json.dumps(observed));self.assertTrue(audit_manifest(p))
            observed['observations']=5;out.write_text(json.dumps(observed));self.assertEqual(audit_manifest(p),[])
            (ROOT/first['bundle']/'cudart64_12.dll').write_bytes(b'changed');self.assertTrue(audit_manifest(p))

    def test_forged_missing_mode_and_changed_payload_cannot_pass(self):
        folder=ROOT/'.cache/p09a-implementation/evidence-test';folder.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=folder) as name:
            d=Path(name); p=d/'manifest.json'
            for value in ({'status':'pass'},{'schema_version':1,'modes':[],'artifacts':{}}):
                p.write_text(json.dumps(value)); self.assertTrue(audit_manifest(p,ROOT))
            # A self-attested success, without actual executable observations, is never enough.
            p.write_text(json.dumps({'status':'pass','modes':[{'mode':'shared_primary','status':'pass'}]}))
            self.assertTrue(audit_manifest(p,ROOT))

if __name__=='__main__':unittest.main()
