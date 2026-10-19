"""Actual nvFatbin alternatives: baseline rejection and generic Arc semantics."""
import ctypes as c
import hashlib
import json
from pathlib import Path
import sys

from m3c_gpu_validation import Device, P, REPO
from m3d_fatbin_check import Producer


def load_code(device, image):
    output=P(1)
    code=device.dll.cuModuleLoadData(c.byref(output),c.cast(c.create_string_buffer(image),P))
    return code,output


def sources(entry):
    old=(REPO/'tests/fixtures/vector_add.ptx').read_bytes().replace(b'vector_add',entry.encode())
    new=old.replace(b'.version 7.0',b'.version 8.0').replace(b'sm_50',b'sm_52').replace(b'add.rn.f32',b'sub.rn.f32')
    # Different parameter names are ABI-compatible; rename declarations and uses.
    new=new.replace(b' 4 a,',b' 4 alpha,').replace(b'[a]',b'[alpha]')
    return old,new


def verify_baseline(image):
    baseline=REPO/'.cache/m3f-baseline/ct_cuda.dll'
    expected=(baseline.parent/'sha256.txt').read_text(encoding='utf-8-sig').strip().lower()
    if hashlib.sha256(baseline.read_bytes()).hexdigest()!=expected: raise RuntimeError('baseline DLL hash mismatch')
    device=Device(baseline)
    try:
        code,output=load_code(device,image)
        if code!=801 or output.value is not None: raise RuntimeError('baseline did not reject multiple PTX with null output')
    finally: device.close()
    return expected


def main(baseline_only=False):
    producer=Producer()
    old,new=sources('ct_choice')
    initial=producer.make_many([(old,b'50'),(new,b'52')],True)
    baseline_hash=verify_baseline(initial)
    if baseline_only:
        print(json.dumps(dict(status='expected_rejection',code=801,null_module=True,baseline_sha256=baseline_hash)))
        return
    device=Device()
    cases=outputs=guards=0
    hashes=[]
    cache=REPO/'.cache/reference/m3f';cache.mkdir(parents=True,exist_ok=True)
    try:
        for entry in ('ct_choice','arbitrary_name'):
            old,new=sources(entry)
            for compressed in (False,True):
                for reverse in (False,True):
                    entries=[(old,b'50'),(new,b'52')]
                    if reverse: entries.reverse()
                    image=producer.make_many(entries,compressed)
                    hashes.append(hashlib.sha256(image).hexdigest())
                    (cache/(entry+f'-{int(compressed)}-{int(reverse)}.fatbin')).write_bytes(image)
                    for count in (1,63,64,65,257,50000):
                        device.run(image,entry,count,expected_sub=True)
                        cases+=1;outputs+=count;guards+=64
        # Each malformed case has readable declared bytes; no invalid host pointer probes.
        old,new=sources('ct_choice')
        negatives=[
            ('duplicate-profile',producer.make_many([(old,b'50'),(old,b'50')],False),801),
            ('entry-mismatch',producer.make_many([(old,b'50'),(new.replace(b'ct_choice',b'different_entry'),b'52')],True),801),
            ('abi-mismatch',producer.make_many([(old,b'50'),(new.replace(b'.param .u32 n',b'.param .u32 n, .param .u32 extra'),b'52')],True),801),
            ('unselected-unsupported',producer.make_many([(old.replace(b'ret;',b'bar.sync 0; ret;'),b'50'),(new,b'52')],True),801),
        ]
        # These two are deliberately modified producer outputs, not genuine unmodified variants.
        mismatch=bytearray(producer.make_many([(old,b'50')],False));mismatch[42:44]=(8).to_bytes(2,'little');mismatch[44:48]=(52).to_bytes(4,'little')
        negatives.append(('modified-profile-mismatch',bytes(mismatch),218))
        unknown=bytearray(producer.make_many([(old,b'50')],False));unknown[44:48]=(90).to_bytes(4,'little')
        negatives.append(('modified-unknown-profile',bytes(unknown),801))
        for label,image,expected in negatives:
            code,output=load_code(device,image)
            if code!=expected or output.value is not None: raise RuntimeError('negative selection check failed: '+label)
        device.run(initial,'ct_choice',65,expected_sub=True)
        for _ in range(100): device.run(initial,'ct_choice',65,expected_sub=True)
        for _ in range(1000):
            code,module=load_code(device,initial)
            if code or module.value is None: raise RuntimeError('module cycle load failed')
            device.call('cuModuleUnload',module)
        if (cases,outputs,guards)!=(48,403600,3072): raise RuntimeError('unexpected selection test totals')
    finally: device.close()
    print(json.dumps(dict(status='pass',producer='NVIDIA nvFatbin12.4.99',baseline_code=801,
        baseline_sha256=baseline_hash,cases=cases,results=outputs,guards=guards,containers=len(hashes),
        container_sha256=hashes,negative_cases=len(negatives),null_outputs=True,
        recovery_results=65,recovery_guards=64,repeated_kernel_cases=100,repeated_kernel_results=6500,
        repeated_kernel_guards=6400,module_cycles=1000)))


if __name__=='__main__':
    try: main('--baseline-only' in sys.argv[1:])
    except (RuntimeError,OSError) as error:
        print(json.dumps(dict(status='error',reason=str(error) if isinstance(error,RuntimeError) else 'local selection test operation failed')))
        raise SystemExit(1)
