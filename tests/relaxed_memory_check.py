"""Synthetic, guarded native Driver regression; not upstream app acceptance."""
import ctypes as c
import hashlib
import json
from pathlib import Path
import argparse

from m3c_gpu_validation import Device, P, U32, U64, REPO


def run(driver=None):
    fixture = (REPO / 'tests/fixtures/relaxed_memory.ptx').read_bytes()
    guard = 0xcafebabe
    cases = 0
    driver = driver or REPO / 'target/debug/ct_cuda.dll'
    device = Device(driver)
    try:
        device.dll.cuDeviceGetName.argtypes = [P, c.c_int, c.c_int]
        device.dll.cuDeviceGetName.restype = c.c_int
        name = c.create_string_buffer(256)
        device.call('cuDeviceGetName', c.cast(name, P), len(name), 0)
        device_name = name.value.decode('utf-8')
        for major in (7, 8):
            source = fixture if major == 8 else fixture.replace(
                b'.version 8.0', b'.version 7.0').replace(b'sm_52', b'sm_50')
            for a, b in ((0, 1), (0x7fffffff, 0x80000000),
                         (0x80000001, 0xffffffff)):
                for wide in (0, 1, 0xdeadbeef80000001, 0xffffffffffffffff):
                    owner = P()
                    pointers = []
                    try:
                        image = c.create_string_buffer(source)
                        device.call('cuModuleLoadData', c.byref(owner), c.cast(image, P))
                        kernel = P()
                        device.call('cuModuleGetFunction', c.byref(kernel), owner, b'relaxed_memory')
                        host_input = (U32 * 6)(guard, guard, a, b, guard, guard)
                        host_output = (U32 * 16)(*([guard] * 16))
                        original = bytes(host_input)
                        for array in (host_input, host_output):
                            pointer = U64()
                            device.call('cuMemAlloc_v2', c.byref(pointer), c.sizeof(array))
                            pointers.append(pointer)
                            device.call('cuMemcpyHtoD_v2', pointer, c.cast(array, P), c.sizeof(array))
                        values = [U64(p.value + 8) for p in pointers] + [U64(wide)]
                        arguments = (P * 3)(*(c.cast(c.pointer(v), P) for v in values))
                        device.call('cuLaunchKernel', kernel, 1, 1, 1, 1, 1, 1, 0, None, arguments, None)
                        device.call('cuMemcpyDtoH_v2', c.cast(host_output, P), pointers[1], c.sizeof(host_output))
                        low = wide & 0xffffffff
                        expected = [guard, guard, a, 0, low, guard, b, 0, low,
                                    guard, 0x80000001, 0, low, 0, guard, guard]
                        if list(host_output) != expected:
                            raise RuntimeError('relaxed memory result or neighboring guard mismatch')
                        device.call('cuMemcpyDtoH_v2', c.cast(host_input, P), pointers[0], c.sizeof(host_input))
                        if bytes(host_input) != original:
                            raise RuntimeError('read-only source changed')
                        cases += 1
                    finally:
                        if owner.value:
                            device.call('cuModuleUnload', owner)
                        for pointer in pointers:
                            device.call('cuMemFree_v2', pointer)
    finally:
        device.close()
    return {'status': 'pass', 'synthetic': True, 'cases': cases,
            'device': device_name,
            'checked_output_words': cases * 16,
            'fixture_sha256': hashlib.sha256(fixture).hexdigest(),
            'driver_sha256': hashlib.sha256(driver.read_bytes()).hexdigest()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--driver', type=Path)
    print(json.dumps(run(parser.parse_args().driver)))
