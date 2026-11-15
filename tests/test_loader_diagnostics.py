import contextlib
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_ct_loader import image
from ct import LoaderError, inspect_pe, prepare_bundle, main


def mixed_runtime():
    data=bytearray(image(symbol=b'cudaMalloc',library=b'cudart64_12.dll'))
    struct.pack_into('<Q',data,648,0x1140)
    struct.pack_into('<Q',data,656,0)
    symbol=b'cudaNotImplemented\0'
    data[834:834+len(symbol)]=symbol
    return bytes(data)


class LoaderDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.cache=Path(__file__).resolve().parents[1]/'.cache/loader-diagnostic-tests'
        self.cache.mkdir(parents=True,exist_ok=True)

    def test_cli_reports_missing_runtime_without_execution(self):
        with tempfile.TemporaryDirectory(dir=self.cache) as d:
            p=Path(d)/'app.exe';p.write_bytes(mixed_runtime())
            run=subprocess.run([sys.executable,'scripts/ct.py','inspect','--runtime','--diagnostic',str(p)],
                               cwd=self.cache.parents[1],capture_output=True,timeout=30)
            self.assertEqual(run.returncode,0)
            value=json.loads(run.stdout)
            self.assertEqual(value['compatibility'],'blocked')
            self.assertIs(value['execution_performed'],False)
            self.assertEqual(value['unsupported_imports'],[dict(library='cudart64_12.dll',symbols=['cudaNotImplemented'])])

    def test_driver_and_runtime_defaults_stay_strict(self):
        for data, kwargs in ((image(symbol=b'cuNotImplemented'),{}),(mixed_runtime(),{'runtime':True})):
            with self.assertRaises(LoaderError):inspect_pe(data,**kwargs)
            report=inspect_pe(data,diagnostic=True,**kwargs)
            self.assertEqual(report['compatibility'],'blocked')
        value=inspect_pe(image(symbol=b'cudaMalloc',library=b'cudart64_12.dll'),runtime=True,diagnostic=True)
        self.assertEqual(value['unsupported_imports'],[])
        self.assertEqual(value['compatibility'],'unproven')

    def test_diagnostic_does_not_relax_pe_validation_or_runtime_version(self):
        bad=[]
        for kind in ('x86','delay','iat'):
            data=bytearray(image())
            if kind=='x86':struct.pack_into('<H',data,132,0x14c)
            if kind=='delay':struct.pack_into('<II',data,368,0x1100,32)
            if kind=='iat':struct.pack_into('<I',data,528,0xfffffff0)
            bad.append(bytes(data))
        bad += [image()[:530],image(ordinal=True),image(symbol=b'cudaMalloc',library=b'cudart64_110.dll')]
        for data in bad:
            with self.assertRaises(LoaderError):inspect_pe(data,runtime=True,diagnostic=True)

    def test_diagnosed_application_still_cannot_be_bundled_or_run(self):
        with tempfile.TemporaryDirectory(dir=self.cache) as d:
            folder=Path(d);app=folder/'app.exe';driver=folder/'driver.dll';runtime=folder/'runtime.dll'
            app.write_bytes(mixed_runtime());driver.write_bytes(image(dll=True));runtime.write_bytes(image(dll=True))
            report=inspect_pe(app.read_bytes(),runtime=True,diagnostic=True)
            self.assertEqual(report['compatibility'],'blocked')
            with self.assertRaises(LoaderError):prepare_bundle(app,driver,[],folder/'runs',runtime_dll=runtime)
            args=['ct','run','--ct-dll',str(driver),'--runtime-dll',str(runtime),str(app)]
            with patch('sys.argv',args),patch('ct.run_child') as child,contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(),2)
            child.assert_not_called()


if __name__=='__main__':unittest.main()
