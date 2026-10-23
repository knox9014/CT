import sys,unittest,tempfile,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from prepare_nvcc_default import compiler_args,validate_observations,audit_default_producer
class DefaultProducerTests(unittest.TestCase):
 def test_default_recipe_cannot_hide_nodevrt_flag(self):
  argv=compiler_args(Path('out'),Path('base'),{'profile':'diagnostic','tools':{'cl.exe':{'path':'cc/cl.exe'}}})
  self.assertIn('--cudart=shared',argv);self.assertNotIn('--cudadevrt=none',argv);self.assertIn('--compiler-bindir',argv)
 def test_default_probe_requires_owned_observations(self):
  self.assertTrue(validate_observations([]));self.assertTrue(validate_observations([{'kind':'wrapper','version':2,'images':[]}]))
 def test_default_probe_rejects_mutated_dependencies(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as d:
   p=Path(d)/'manifest.json';p.write_text('{}');self.assertTrue(audit_default_producer(p))
 def test_default_probe_never_qualifies_diagnostic(self):
  self.assertTrue(validate_observations([{'status':'pass','host_profile':'qualified'}]))

class DefaultProducerArtifactTests(unittest.TestCase):
 def test_mutation_flags_and_qualification_are_independently_checked(self):
  from unittest.mock import patch
  import prepare_nvcc_default as d
  import struct
  with tempfile.TemporaryDirectory(dir=ROOT/'.cache') as temporary:
   root=Path(temporary);out=root/'.cache/p09a2c-producer';out.mkdir(parents=True);base=root/'.cache/base.json'
   host={'profile':'diagnostic','tools':{'cl.exe':{'path':'cc/cl.exe'}}};base.write_text(json.dumps({'host':host}))
   for name in (d.SOURCE,d.OBSERVER):
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'CT owned source')
   def raw(kind,count):
    records=b''.join(struct.pack('<HHIQ',kind,0x101,64,8)+bytes(48)+bytes(8) for _ in range(count))
    return struct.pack('<IHHQ',0xba55ed50,1,16,len(records))+records
   user=raw(1,1);empty=raw(2,0);linked=raw(2,9)
   names=['default.exe','observer.dll','observe/application.exe','observe/cudart64_12.dll','vector.cu','observer.cpp']+['keep/vector'+s for s in ('.fatbin','.ptx','.cudafe1.stub.c')]+['keep/default_dlink'+s for s in ('.fatbin','.fatbin.c','.reg.c')]
   for n in names:
    p=out/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'CT owned source')
   for n,data in [('keep/vector.fatbin',user),('keep/default_dlink.fatbin',empty),('observe/raw-0.bin',user),('observe/raw-1.bin',empty),('observe/raw-2.bin',linked)]: (out/n).write_bytes(data)
   rows=[{'kind':'wrapper','version':1},{'kind':'wrapper','version':2}]+[{'kind':'image','index':i,'size':len(v)} for i,v in enumerate((user,empty,linked))]+[{'kind':'linked','count':1}]
   rows += [{'kind':'function','limit':-1,'optional':0,'equal':1,'host':1} for _ in range(33)]
   rows += [{'kind':'variable','host':1,'external':0,'size':8,'constant':0,'global':0,'address':'76616c7565','name':'76616c7565'} for _ in range(11)]
   rows += [{'kind':'end'},{'kind':'end'},{'kind':'retire'},{'kind':'retire'}]
   (out/'observe/stdout.jsonl').write_text('\n'.join(json.dumps(r) for r in rows));(out/'observe/stderr.txt').write_bytes(b'')
   m={'schema_version':1,'base_producer':{'path':base.relative_to(root).as_posix(),'sha256':d.digest(base)},'source':{n:d.digest(root/n) for n in (d.SOURCE,d.OBSERVER)},'commands':d.commands(out,base.parent,host),'host_profile':'diagnostic','artifacts':d.artifacts(out),'observations':{'exit_code':11,'rows':rows}}
   manifest=out/'manifest.json'
   def save():manifest.write_text(json.dumps(m))
   save()
   with patch.object(d,'audit_probe',return_value=[]):
    self.assertEqual(d.audit_default_producer(manifest,root),[])
    (out/'observe/raw-2.bin').write_bytes(linked+b'changed');self.assertEqual(d.audit_default_producer(manifest,root),['default artifacts changed']);(out/'observe/raw-2.bin').write_bytes(linked)
    m['commands']['cuda'].append('--cudadevrt=none');save();self.assertEqual(d.audit_default_producer(manifest,root),['default compiler flags']);m['commands']['cuda'].pop()
    m['host_profile']='qualified';save();self.assertEqual(d.audit_default_producer(manifest,root),['default source/qualification'])
