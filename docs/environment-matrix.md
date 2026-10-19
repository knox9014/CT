# CT environment matrix

Observed on 2026-10-19. This records M0 native execution, not CUDA support.

| Item | Observed value |
| --- | --- |
| Host OS | Windows x64, 25H2, build 26200.9711 |
| OS identification caveat | Registry ProductName reports Windows 10 Home; use build/display version to identify this environment rather than trusting that legacy label. |
| Connected display device | Intel(R) Arc(TM) B390 GPU, Started |
| Vendor / PCI device | 0x8086 / 0xb080; Level Zero agrees with connected-device enumeration |
| Installed display-driver entry | 32.0.101.8622 |
| System32 ze_loader.dll file version | 1.27.0 |
| Driver-reported Level Zero API | 1.14 |
| Driver-reported opaque version | 17010935; not interpreted as a display-driver version |
| Compute queue ordinal | 0 |
| Maximum total group size | 1024 |
| Maximum X group count | 4294967295 |
| Rust / Cargo | rustc 1.96.1, cargo 1.96.1, stable-x86_64-pc-windows-msvc |
| MSVC tools | Visual Studio 18 Community x64 C++ tools |
| Python | 3.14 installation; standard library only |
| Official ABI reference | oneapi-src/level-zero v1.27.0, include/ze_api.h |
| SPIR-V encoding reference | KhronosGroup/SPIRV-Headers vulkan-sdk-1.4.328.1 grammar |
| Native module | SPIR-V 1.0, Kernel/OpenCL, Physical64 |
| CUDA execution | Not implemented / not tested |
| AMD execution | No device verified; not tested |
| Linux / WSL | Not tested |

Device UUID, machine name, user paths and other machine-specific identifiers are excluded from this public record. CIM queries are unavailable in this session; display-device/driver observations came from pnputil and selected registry properties. No driver installation, update, OS change or system DLL replacement was performed.
