"""Run the bounded Numba JIT experiment with an explicitly supplied test DLL."""
import argparse
import ctypes
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", type=Path, required=True)
    parser.add_argument("--toolkit", type=Path, required=True)
    args = parser.parse_args()
    provider = args.provider.resolve(strict=True)
    toolkit = args.toolkit.resolve(strict=True)
    os.environ["NUMBA_CUDA_DRIVER"] = str(provider)
    os.environ["CUDA_HOME"] = str(toolkit)
    os.environ["CT_VIRTUAL_TARGET"] = "ct-sm52-subset-v1"
    os.environ["NUMBA_CUDA_USE_NVIDIA_BINDING"] = "0"
    os.environ["NUMBA_ENABLE_CUDASIM"] = "0"

    with os.add_dll_directory(str(provider.parent)), os.add_dll_directory(
        str(toolkit / "nvvm/bin")
    ):
        native = ctypes.WinDLL(str(provider.with_name("ct_cuda.dll")))
        from numba import cuda
        from numba.cuda.cudadrv import driver
        import numba
        import numpy as np

        if numba.__version__ != "0.65.1":
            raise RuntimeError("This experiment requires Numba 0.65.1")

        # Select the tested physical model without printing its unique identifier.
        name = ctypes.create_string_buffer(256)
        native.cuDeviceGetName.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_int
        ]
        if native.cuInit(0) or native.cuDeviceGetName(name, len(name), 0):
            raise RuntimeError("CT device initialization failed")
        if b"B390" not in name.value:
            raise RuntimeError("This experiment was qualified for Arc B390")

        original = driver.CtypesFunction.read_func_attr_all

        def unknown_attributes(self):
            return driver.FuncAttr(
                regs=None, shared=None, local=None, const=None, maxthreads=None
            )

        driver.CtypesFunction.read_func_attr_all = unknown_attributes
        try:
            @cuda.jit
            def add_one(data, count):
                index = cuda.grid(1)
                if index < count:
                    data[index] += 1

            @cuda.jit
            def affine(data, count, scale, bias):
                index = cuda.grid(1)
                if index < count:
                    data[index] = data[index] * scale + bias

            counts = (0, 1, 16, 32, 33, 37, 257)
            results = 0
            guards = 0
            for count in counts:
                host = np.full(count + 32, -9999, dtype=np.int32)
                host[:count] = np.arange(-8, count - 8, dtype=np.int32)
                device = cuda.to_device(host)
                blocks = max(1, (count + 31) // 32)
                expected = host[:count].copy()
                # Alternate compiled kernels on the same device allocation.
                for scale, bias in ((3, -7), (-2, 5)):
                    add_one[blocks, 32](device, np.int64(count))
                    affine[blocks, 32](
                        device, np.int64(count), np.int32(scale), np.int32(bias)
                    )
                    expected = (expected + 1) * scale + bias
                    result = device.copy_to_host()
                    if not np.array_equal(result[:count], expected):
                        raise RuntimeError("GPU calculation differs from CPU oracle")
                    if not np.array_equal(result[count:], host[count:]):
                        raise RuntimeError("Kernel modified the guard region")
                    results += count
                    guards += 32
        finally:
            driver.CtypesFunction.read_func_attr_all = original
        print(json.dumps(dict(
            status="experimental_pass", cases=len(counts), results=results,
            guards=guards, kernels=2, launches=len(counts) * 4,
            metadata_adapter=True, memory_policy="dxgi-process-budget",
            device=name.value.decode("utf-8"),
        )))


if __name__ == "__main__":
    main()
