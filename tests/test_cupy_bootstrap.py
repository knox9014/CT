"""R2 diagnostic contracts never promote a blocked consumer to support."""
import copy
from pathlib import Path
import struct
import sys
import unittest
import hashlib
import json
import tempfile
from unittest.mock import patch
import zipfile
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import cupy_bootstrap_check as check
import run_cupy_bootstrap as runner


def image():
    data = bytearray(1536)
    data[:2] = b'MZ'
    struct.pack_into('<I', data, 60, 128)
    data[128:132] = b'PE\0\0'
    struct.pack_into('<HH', data, 132, 0x8664, 1)
    struct.pack_into('<H', data, 148, 240)
    struct.pack_into('<H', data, 152, 0x20b)
    struct.pack_into('<I', data, 152+56, 0x2000)
    struct.pack_into('<I', data, 152+108, 16)
    struct.pack_into('<II', data, 152+120, 0x1000, 40)
    struct.pack_into('<IIII', data, 392+8, 1024, 0x1000, 1024, 512)
    struct.pack_into('<IIIII', data, 512, 0x1080, 0, 0, 0x10c0, 0x1100)
    struct.pack_into('<Q', data, 640, 0x10a0)
    data[674:689] = b'GetProcAddress\0'
    data[704:717] = b'KERNEL32.dll\0'
    return data


class BootstrapTests(unittest.TestCase):
    def test_changed_observation_prevents_workload_child(self):
        calls=[]
        def run(argv,**kwargs):
            if argv[0]=='cargo':return SimpleNamespace(returncode=0)
            self.assertEqual(argv[1:3],['-I','-S'])
            mode=argv[-1];calls.append(mode)
            value=(dict(status='cpu_pass',stage='complete',words=check.expected_words()) if mode=='cpu'
                   else dict(status='blocked',stage='device_count',error_type='CUDARuntimeError',error_code=35))
            if mode=='observe':value.update(trace=[],restored=False,patches=1)
            return SimpleNamespace(returncode=0,stdout=json.dumps(value).encode(),stderr=b'')
        with tempfile.TemporaryDirectory(dir=runner.ROOT/'.cache') as directory:
            root=Path(directory)
            with patch.object(runner,'ROOT',root),patch.object(runner,'installed',return_value={}), \
                 patch.object(runner,'digest',return_value='hash'),patch.object(runner,'source_fingerprint',return_value='source'), \
                 patch.object(runner.shutil,'copyfile'),patch.object(runner.subprocess,'check_output',return_value='(3, 14):8'), \
                 patch.object(runner.subprocess,'run',side_effect=run):
                with self.assertRaises(ValueError):runner.capture(root/'env',root/'wheels')
        self.assertEqual(calls,['cpu','prefix','observe'])

    def test_source_edit_during_build_prevents_children(self):
        with tempfile.TemporaryDirectory(dir=runner.ROOT/'.cache') as directory:
            root=Path(directory)
            with patch.object(runner,'ROOT',root),patch.object(runner,'installed',return_value={}), \
                 patch.object(runner,'source_fingerprint',side_effect=['before','after']), \
                 patch.object(runner.subprocess,'check_output',return_value='(3, 14):8'), \
                 patch.object(runner.subprocess,'run') as run:
                with self.assertRaises(ValueError):runner.capture(root/'env',root/'wheels')
                self.assertEqual(run.call_count,1)
                self.assertEqual(run.call_args.args[0][0],'cargo')

    def test_changed_nominal_workload_prevents_observed_workload(self):
        calls=[]
        def run(argv,**kwargs):
            if argv[0]=='cargo':return SimpleNamespace(returncode=0)
            mode=argv[-1];calls.append(mode)
            value=dict(status='blocked',stage='device_count',error_type='CUDARuntimeError',error_code=35)
            if mode=='cpu':value=dict(status='cpu_pass',stage='complete',words=check.expected_words())
            if mode=='observe':value.update(trace=[dict(kind='call',symbol='cuDriverGetVersion',result=801,value=0)],restored=True,patches=1)
            if mode=='workload':value=dict(status='gpu_pass',stage='complete',words=check.expected_words())
            return SimpleNamespace(returncode=0,stdout=json.dumps(value).encode(),stderr=b'')
        with tempfile.TemporaryDirectory(dir=runner.ROOT/'.cache') as directory:
            root=Path(directory)
            with patch.object(runner,'ROOT',root),patch.object(runner,'installed',return_value={}), \
                 patch.object(runner,'digest',return_value='hash'),patch.object(runner,'source_fingerprint',return_value='source'), \
                 patch.object(runner.shutil,'copyfile'),patch.object(runner.subprocess,'check_output',return_value='(3, 14):8'), \
                 patch.object(runner.subprocess,'run',side_effect=run):
                with self.assertRaises(ValueError):runner.capture(root/'env',root/'wheels')
        self.assertEqual(calls,['cpu','prefix','observe','workload'])

    def test_wheel_internal_data_pinned_and_extra_payload_rejected(self):
        with tempfile.TemporaryDirectory(dir=runner.ROOT/'.cache') as directory:
            root=Path(directory);site=root/'env/Lib/site-packages';site.mkdir(parents=True)
            wheel=root/'example.whl'
            with zipfile.ZipFile(wheel,'w') as z:
                z.writestr('example/__init__.py',b'')
                z.writestr('example/.data/config.json',b'{}')
            (site/'example/.data').mkdir(parents=True)
            (site/'example/__init__.py').write_bytes(b'')
            (site/'example/.data/config.json').write_bytes(b'{}')
            pins=root/'pins.json';pins.write_text(json.dumps(dict(packages=[dict(filename=wheel.name,sha256=hashlib.sha256(wheel.read_bytes()).hexdigest())])))
            with patch.object(runner,'PINS',pins):
                self.assertEqual(runner.installed(root/'env',root)['files'],2)
                (site/'example/extra.py').write_bytes(b'pass')
                with self.assertRaises(ValueError):runner.installed(root/'env',root)
                (site/'example/extra.py').unlink()
                (site/'example/.data/config.json').write_bytes(b'[]')
                with self.assertRaises(ValueError):runner.installed(root/'env',root)

    def test_import_slot_is_rva_not_raw_offset(self):
        self.assertEqual(check.import_slots(bytes(image())), (0x2000, [0x1100]))

    def test_verified_windows_loader_api_set_is_supported(self):
        data=image();name=b'api-ms-win-core-libraryloader-l1-2-0.dll\0'
        data[704:704+len(name)]=name
        self.assertEqual(check.import_slots(bytes(data)),(0x2000,[0x1100]))
        data=image();data[704:717]=b'UNTRUSTEDdll\0'
        with self.assertRaises(ValueError):check.import_slots(bytes(data))

    def test_reject_truncated_or_wrong_machine_or_bad_rva(self):
        for offset, value in ((132, 0), (152, 0x10b), (512, 0x90000000), (392+20, 0x90000000)):
            data = image()
            struct.pack_into('<I', data, offset, value)
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                check.import_slots(bytes(data))
        with self.assertRaises(ValueError):
            check.import_slots(b'MZ')

    def test_ordinal_not_treated_as_name(self):
        data=image(); struct.pack_into('<Q', data, 640, 1 << 63 | 3)
        self.assertEqual(check.import_slots(bytes(data))[1], [])

    def test_unterminated_descriptor_rejected(self):
        data=image(); struct.pack_into('<II',data,272,0x1000,20)
        with self.assertRaises(ValueError):check.import_slots(bytes(data))

    def test_cpu_oracle_independent_and_sensitive(self):
        words=check.expected_words()
        self.assertEqual(len(words),64)
        self.assertEqual(words[:31], [0]*31)
        self.assertEqual(words[-1],struct.unpack('<I',struct.pack('<f',97/16))[0])
        self.assertTrue(check.numerical(words))
        for bad in (words[:-1], [0]*64, [True]*64, words[:63]+[0x7fc00000]):
            self.assertFalse(check.numerical(bad))

    def test_observation_requires_call_not_lookup_or_message(self):
        nominal=dict(status='blocked',stage='device_count',error_type='CUDARuntimeError',error_code=35)
        observed=dict(nominal,trace=[dict(kind='call',symbol='cuDriverGetVersion',result=801,value=0)],restored=True,patches=1)
        self.assertTrue(check.bootstrap_blocker(nominal,observed))
        for key,value in [('trace',[]),('restored',False),('patches',0),('error_code',0)]:
            changed=copy.deepcopy(observed);changed[key]=value
            self.assertFalse(check.bootstrap_blocker(nominal,changed))
        changed=copy.deepcopy(observed);changed['trace'][0]['kind']='lookup'
        self.assertFalse(check.bootstrap_blocker(nominal,changed))
        self.assertFalse(check.bootstrap_blocker(dict(nominal,error_code=True), observed))

    def test_workload_trace_must_match_workload_stage(self):
        nominal=dict(status='blocked',stage='input_creation',error_type='CUDARuntimeError',error_code=35)
        observed=dict(nominal,trace=[dict(kind='call',symbol='cuDriverGetVersion',result=801,value=0)],restored=True,patches=1)
        self.assertTrue(check.bootstrap_blocker(nominal,observed,stage='input_creation'))
        self.assertFalse(check.bootstrap_blocker(nominal,dict(observed,stage='device_count'),stage='input_creation'))


if __name__=='__main__':unittest.main()
