"""Actual official-validator controls; mocks never satisfy this command."""
import argparse
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from validate_spirv import run_validator
from compatibility_registry import validate_toolchain


def main():
    root=Path(__file__).resolve().parents[1]
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tool',type=Path,required=True)
    parser.add_argument('--lock',type=Path,default=root/'docs/compatibility/toolchain-lock-v1.json')
    args=parser.parse_args()
    try:
        lock=json.loads(args.lock.read_text())
        if validate_toolchain(lock): raise ValueError('invalid lock')
        entry=next(t for t in lock['tools'] if t['id']=='spirv-val')
        tool=root/'target/debug/examples/translate_module.exe'
        cache=root/'.cache/validator-controls';cache.mkdir(parents=True,exist_ok=True)
        results=[]
        with tempfile.TemporaryDirectory(dir=cache) as d:
            directory=Path(d)
            for name in ('integer_bits','integer_memory','matmul','multi_entry','multidimensional','relu','saxpy','vector_add'):
                output=directory/(name+'.spv')
                completed=subprocess.run([str(tool),str(root/'tests/fixtures'/ (name+'.ptx')),str(output)],
                                         capture_output=True,timeout=30)
                if completed.returncode:
                    raise ValueError('positive translation failed')
                result=run_validator(output,args.tool,entry,required=True)
                results.append(dict(case_id=name,expected='accepted',**result))
            good=(directory/'multi_entry.spv').read_bytes()
            words=list(struct.unpack('<'+'I'*(len(good)//4),good));i=5
            while i<len(words):
                if words[i]&65535==32:
                    words[i+3]=words[3]+42;break
                i+=words[i]>>16
            for name,data in (('truncated',good[:-3]),('invalid_type',struct.pack('<'+'I'*len(words),*words))):
                output=directory/(name+'.spv');output.write_bytes(data)
                results.append(dict(case_id=name,expected='rejected',
                                    **run_validator(output,args.tool,entry,required=True)))
        print(json.dumps(dict(cases=results)))
        return int(any((r['status']!='pass' if r['expected']=='accepted' else
                        r['status']!='fail' or r['reason']!='validation_rejected') for r in results))
    except (OSError,ValueError,StopIteration,subprocess.SubprocessError):
        print(json.dumps(dict(status='fail',reason='validation_controls_failed')))
        return 1


if __name__=='__main__':raise SystemExit(main())
