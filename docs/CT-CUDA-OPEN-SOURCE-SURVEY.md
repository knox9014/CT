# CUDA 오픈소스 생태계 조사

2026-11-06 기준. 기존 Windows CUDA 앱을 Intel GPU에서 실행하려는 CT의 목표에 영향을 주는 프로젝트를 우선 조사했다. 공개 문서와 저장소를 바탕으로 입력, 필요한 변경, 실행 대상, CT에 적용할 검증 방법을 비교했다. CUDA를 사용하는 모든 앱과 포크를 열거하는 대신, 호환 계층과 그 경계를 검증할 대표 프로젝트를 포함했다. 외부 프로젝트의 실행 결과는 출처의 보고이며, 이번 조사에서 직접 벤치마크한 값은 없다.

## 기존 앱 실행과 소스 이식

| 프로젝트 | 입력과 결과 | CT에 주는 기준 |
| --- | --- | --- |
| ZLUDA | 기존 CUDA 앱이 대체 Driver DLL 또는 공유 라이브러리를 로드한다. 현행 문서의 Windows 경로는 AMD 드라이버와 HIP SDK를 요구한다. FAQ는 Intel 백엔드를 과거 지원으로 분류한다. | 가장 가까운 비교 대상이다. DLL 로드 방식, 실제 호출을 바탕으로 한 호환성 확대, 수학 라이브러리 로딩을 비교한다. [실행 가이드](https://zluda.readthedocs.io/stable/) · [하드웨어 FAQ](https://zluda.readthedocs.io/latest/faq.html) |
| chipStar | CUDA 또는 HIP 소스에서 SPIR-V를 만들어 OpenCL 또는 Level Zero에서 실행한다. 논문은 GAMESS-GPU-HF 이식 사례를 보고한다. | CT와 같은 Intel 백엔드를 쓰는 재컴파일 대조군이다. 커널 동기화, 메모리, 라이브러리 매핑을 조사할 수 있다. [저장소](https://github.com/CHIP-SPV/chipStar) · [논문](https://doi.org/10.1177/10943420261423001) |
| HIP / HIPIFY | CUDA 소스를 HIP으로 변환하고 대상 백엔드용으로 다시 빌드한다. | 소스가 있는 경우의 AMD 비교 경로다. API 대응표는 변환 후보를 찾는 데 쓰고, 바이너리 ABI는 별도로 검증한다. [HIPIFY 문서](https://rocm.docs.amd.com/projects/HIPIFY/en/latest/) · [HIP 저장소](https://github.com/ROCm/HIP) |
| SYCLomatic | CUDA 소스를 SYCL로 옮겨 타깃별로 빌드한다. | Intel에서 같은 알고리즘을 실행하는 대조군을 만들 수 있다. 자동 변환 뒤 진단과 수동 수정 범위를 기록해야 한다. [변환 과정](https://oneapi-src.github.io/SYCLomatic/dev_guide/migration/migration-workflow.html) |
| CU2CL | Clang 도구로 CUDA 소스를 OpenCL 소스로 변환한다. | 소스 변환 방식의 연구 사례다. 현재 Windows 앱의 바이너리 호환성을 판단하는 자료로는 범위가 다르다. [프로젝트 개요](https://chrec.cs.vt.edu/cu2cl/overview.php) |
| GPUOcelot | PTX를 읽어 다시 컴파일하는 연구 프레임워크다. | PTX 명령, 메모리 공간, 테스트 구성의 참고 대상이다. 현행 CUDA 앱이나 Windows 패키지 지원은 개별 검증이 필요하다. [저장소](https://github.com/gpuocelot/gpuocelot) |
| SCALE | CUDA 소스 재컴파일로 AMD와 NVIDIA를 타깃으로 삼는 별도 라이선스 제품이다. | 오픈소스 구현 조사 범위 밖의 시장 비교군이다. 소스 재컴파일로 가능한 범위와 기존 바이너리가 요구하는 범위를 비교한다. [제품 문서](https://docs.scale-lang.com/) |

ZLUDA 개발자는 2026년 1월 업데이트에서 llama.cpp 지원을, 6월 업데이트에서 제한된 텍스처 경로를 통한 Blender 실행과 Windows 로더 개선을 보고했다. 문서에 소개된 범위는 프로젝트 자체 보고이며 모든 모델, 렌더링 모드, 프레임워크 버전에 적용할 수 없다. 현행 AMD 중심 ZLUDA와 Arc B390의 CT 결과는 하드웨어가 달라 속도 순위를 매길 수 없다. [1월 업데이트](https://vosen.github.io/ZLUDA/blog/zluda-update-q4-2025/) · [6월 업데이트](https://vosen.github.io/ZLUDA/blog/zluda-update-q1q2-2026/)

## 컴파일러, 런타임, 검증 자산

| 공개 프로젝트 | CT에서 확인할 부분 |
| --- | --- |
| LLVM NVPTX / Clang CUDA | CUDA 소스와 LLVM IR에서 만들어지는 PTX를 비교해 CT가 받는 입력의 버전과 명령 분포를 넓힌다. [LLVM NVPTX](https://llvm.org/docs/NVPTXUsage.html) · [Clang CUDA](https://llvm.org/docs/CompileCudaWithLLVM.html) |
| Khronos SPIRV-LLVM-Translator / SPIRV-Tools | IR 변환의 참고 구현과 SPIR-V 검증 도구다. 검증기 통과, Intel 드라이버의 모듈 수락, 실제 계산 정답은 각각 기록한다. [변환기](https://github.com/KhronosGroup/SPIRV-LLVM-Translator) · [도구](https://github.com/KhronosGroup/SPIRV-Tools) |
| Intel Level Zero / compute-runtime | CT의 Intel 실행 경로를 검증할 공개 규약과 구현이다. 메모리 조회, 장치 식별, 큐와 이벤트의 범위를 구체적인 버전에서 확인한다. [Level Zero](https://github.com/oneapi-src/level-zero) · [Intel compute-runtime](https://github.com/intel/compute-runtime) |
| Mesa Rusticl / PoCL | OpenCL 구현이다. OpenCL 대조군과 SPIR-V 실행 조건을 검토할 수 있다. [Rusticl](https://docs.mesa3d.org/rusticl.html) · [PoCL](https://github.com/pocl/pocl) |
| Accel-Sim / GPGPU-Sim | GPU 아키텍처와 커널 동작의 시뮬레이션 자료다. CT의 Windows 초기화나 Intel 실기기 성능은 실험 대상이 다르다. [Accel-Sim](https://github.com/accel-sim/accel-sim-framework) · [GPGPU-Sim](https://github.com/gpgpu-sim/gpgpu-sim_distribution) |
| CUDA Samples / Rodinia | 원본 소스, 정답 확인 절차, 병렬 패턴을 고정할 수 있는 검증용 워크로드다. [CUDA Samples](https://github.com/NVIDIA/cuda-samples) · [Rodinia 배포 페이지](https://www.cs.virginia.edu/~skadron/lava/rodinia/) |
| CCCL / CUTLASS | 정렬, 리덕션, 행렬 곱 등 컴파일된 커널의 실제 요구를 드러낸다. 템플릿과 장치 코드 범위, 호스트에서 로드되는 라이브러리 범위를 따로 추적한다. [CCCL](https://github.com/NVIDIA/cccl) · [CUTLASS](https://github.com/NVIDIA/cutlass) |
| NCCL / cuDNN Frontend | 집단 통신과 신경망 연산의 호출 경계를 살필 수 있다. cuDNN Frontend와 그 아래 cuDNN 라이브러리는 별도 구성요소다. [NCCL](https://github.com/NVIDIA/nccl) · [cuDNN Frontend](https://github.com/NVIDIA/cudnn-frontend) |
| CUDA Python / Numba / CuPy | 공개 소스를 가진 실제 호출자다. Driver 바인딩, 컨텍스트 초기화, JIT, 내장 Runtime의 차이를 확인할 수 있다. [CUDA Python](https://github.com/NVIDIA/cuda-python) · [Numba](https://github.com/numba/numba) · [CuPy](https://github.com/cupy/cupy) |
| Triton / Rust CUDA / CUDA Tile IR | CUDA를 대상으로 새로운 커널을 생성하는 경로다. PTX와 Tile IR은 입력 형식부터 구분해서 조사한다. [Triton](https://github.com/triton-lang/triton) · [Rust CUDA](https://github.com/Rust-GPU/Rust-CUDA) · [CUDA Tile IR](https://github.com/NVIDIA/cuda-tile) |
| NVIDIA Open GPU Kernel Modules | NVIDIA GPU용 Linux 커널 모듈 소스다. 공개 범위는 커널 모듈이며 CT가 Windows에서 대체하는 사용자 공간 Driver ABI와 계층이 다르다. [NVIDIA 설치 가이드](https://docs.nvidia.com/datacenter/tesla/driver-installation-guide/610/kernel-modules.html) |

## CT에 적용할 순서

1. **앱이 실행 중 호출한 기능을 기준으로 호환 범위를 정한다.** Numba에서 장치 열거와 상세 조회까지 확인했고, 실제 컨텍스트 초기화는 `cuMemGetInfo`에서 멈췄다. Arc B390의 현재 Windows 드라이버가 두 Level Zero 경로에서 가용량 필드를 채우지 않은 것이 당장 해결해야 할 지점이다. 다른 프로젝트에서 동일한 API 이름을 찾더라도 백엔드가 제공하는 값의 의미가 같아야 적용할 수 있다. [CT 실행 기록](CT-EXECUTION-ROADMAP.md) · [CUDA 메모리 계약](https://docs.nvidia.com/cuda/cuda-driver-api/cuda_driver_api/group__CUDA__MEM.html)
2. **실행 방식별로 대조군을 고정한다.** 원본 CUDA 바이너리의 결과는 NVIDIA 환경에서 확인한다. Intel에서는 같은 알고리즘의 네이티브 Level Zero 또는 SYCL 실행을 확보하고, 가능한 경우 chipStar 재컴파일 결과를 별도 열에 기록한다. ZLUDA의 실행은 지원되는 AMD 장비가 확보됐을 때 비교하며, 다른 GPU의 결과를 번역 비용으로 해석하지 않는다.
3. **작업의 결과와 비용을 같이 기록한다.** 같은 입력과 정답을 사용하고, 앱 로드, 첫 컴파일, 반복 실행의 시간을 구분한다. 실패 시 앱 버전, 첫 실패 호출과 오류를 남긴다. Windows의 다른 Intel 모델에서 같은 절차가 재현돼야 모델 지원 범위를 넓힐 수 있다.
4. **조사와 코드 도입을 구분한다.** 외부 프로젝트를 설계 참고나 독립 검증에 먼저 사용한다. 실제로 코드를 가져올 때는 선택한 커밋과 파일의 라이선스 및 고지 요건을 확인한다.
