"""Independent full-buffer/guard checks, including signed integer edge cases."""
import ctypes as c
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
P = c.c_void_p
U64 = c.c_uint64
U32 = c.c_uint32


class Device:
    def __init__(self, dll_path: Path | None = None):
        self.dll = c.WinDLL(str(dll_path if dll_path is not None else REPO / "target/debug/ct_cuda.dll"))
        signatures = {
            "cuInit": [U32], "cuDeviceGet": [c.POINTER(c.c_int), c.c_int],
            "cuCtxCreate_v2": [c.POINTER(P), U32, c.c_int], "cuCtxDestroy_v2": [P],
            "cuDeviceGetAttribute": [c.POINTER(c.c_int), c.c_int, c.c_int],
            "cuMemAlloc_v2": [c.POINTER(U64), c.c_size_t], "cuMemFree_v2": [U64],
            "cuMemcpyHtoD_v2": [U64, P, c.c_size_t], "cuMemcpyDtoH_v2": [P, U64, c.c_size_t],
            "cuModuleLoadData": [c.POINTER(P), P], "cuModuleGetFunction": [c.POINTER(P), P, c.c_char_p],
            "cuModuleUnload": [P], "cuLaunchKernel": [P, U32, U32, U32, U32, U32, U32, U32, P, c.POINTER(P), P],
        }
        for name, args in signatures.items():
            f = getattr(self.dll, name); f.argtypes = args; f.restype = c.c_int
        self.call("cuInit", 0)
        device = c.c_int(); self.call("cuDeviceGet", c.byref(device), 0)
        mode = c.c_int(-1); self.call("cuDeviceGetAttribute", c.byref(mode), 20, device)
        assert mode.value == 0
        self.context = P(); self.call("cuCtxCreate_v2", c.byref(self.context), 0, device)

    def call(self, name, *args):
        code = getattr(self.dll, name)(*args)
        if code: raise RuntimeError(f"independent GPU API check failed: {name}, code {code}")

    def run(self, source, entry, n, expected_one=False, expected_sub=False):
        left = (c.c_float * n)(*(i * 0.25 for i in range(n)))
        right = (c.c_float * n)(*(-i * 0.125 for i in range(n)))
        output = (c.c_float * (n + 64))(*([-12345.25] * (n + 64)))
        for i in range(n): output[i] = float("nan")
        addresses, module = [], P()
        try:
            for array in (left, right, output):
                pointer = U64(); self.call("cuMemAlloc_v2", c.byref(pointer), c.sizeof(array))
                addresses.append(pointer)
                self.call("cuMemcpyHtoD_v2", pointer, c.cast(array, P), c.sizeof(array))
            self.call("cuModuleLoadData", c.byref(module), c.cast(c.create_string_buffer(source), P))
            function = P(); self.call("cuModuleGetFunction", c.byref(function), module, entry.encode())
            count = U32(n)
            arguments = (P * 4)(*(c.cast(c.pointer(v), P) for v in (*addresses, count)))
            self.call("cuLaunchKernel", function, (n + 63)//64, 1, 1, 64, 1, 1, 0, None, arguments, None)
            self.call("cuMemcpyDtoH_v2", c.cast(output, P), addresses[2], c.sizeof(output))
            for i in range(n):
                expected = 1.0 if expected_one else (left[i] - right[i] if expected_sub else left[i] + right[i])
                assert output[i] == expected, "GPU output mismatch or missing write"
            assert all(output[i] == -12345.25 for i in range(n, n + 64)), "GPU output guard modified"
        finally:
            if module.value: self.call("cuModuleUnload", module)
            for pointer in addresses: self.call("cuMemFree_v2", pointer)

    def close(self):
        self.call("cuCtxDestroy_v2", self.context)


def validate(compiled_ptx):
    device = Device()
    cases = results = guards = 0
    try:
        for n in (1, 63, 64, 65, 257, 50000):
            device.run(compiled_ptx, "VecAdd_kernel", n)
            cases += 1; results += n; guards += 64
        base = (REPO / "tests/fixtures/vector_add.ptx").read_text()
        # Comparisons use raw two's-complement bits. Expected booleans are checked
        # independently; wide multiply never feeds an address in these tests.
        replacements = [
            "setp.lt.s32 %p0, 0xffffffff, 0; selp.f32 %f2, 0f3f800000, 0f00000000, %p0;",
            "setp.ge.s32 %p0, 0x80000000, 0; selp.f32 %f2, 0f00000000, 0f3f800000, %p0;",
            "setp.ge.s32 %p0, 0x7fffffff, 0xffffffff; selp.f32 %f2, 0f3f800000, 0f00000000, %p0;",
            "mul.wide.s32 %rd0, 0xffffffff, 4; setp.eq.u64 %p0, %rd0, 0xfffffffffffffffc; selp.f32 %f2, 0f3f800000, 0f00000000, %p0;",
            "mul.wide.s32 %rd0, 0x80000000, 2; setp.eq.u64 %p0, %rd0, 0xffffffff00000000; selp.f32 %f2, 0f3f800000, 0f00000000, %p0;",
            "mul.wide.s32 %rd0, 0xffffffff, 0xffffffff; setp.eq.u64 %p0, %rd0, 1; selp.f32 %f2, 0f3f800000, 0f00000000, %p0;",
            "mad.lo.s32 %r0, 0xffffffff, 2, 1; setp.eq.u32 %p0, %r0, 0xffffffff; selp.f32 %f2, 0f3f800000, 0f00000000, %p0;",
            "add.s64 %rd0, 0xffffffffffffffff, 1; setp.eq.u64 %p0, %rd0, 0; selp.f32 %f2, 0f3f800000, 0f00000000, %p0;",
        ]
        for replacement in replacements:
            source = base.replace("add.rn.f32 %f2, %f0, %f1;", replacement)
            device.run(source.encode(), "vector_add", 65, expected_one=True)
            cases += 1; results += 65; guards += 64
    finally: device.close()
    return {"cases": cases, "results": results, "guards": guards, "signed_cases": len(replacements)}
