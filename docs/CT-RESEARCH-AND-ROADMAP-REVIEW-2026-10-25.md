# CT: CUDA 호환 기술 재조사와 향후 계획 검토

조사일: 2026-10-25. 목적은 기존 CUDA 프로그램을 Intel·AMD GPU에서 편리하고 정확하게 실행하는 것이다. 이번 작업은 공식 자료 조사와 저장소 검토이며, 외부 프로젝트 성능 측정이나 CT GPU 시험을 새로 실행한 작업은 아니다. 아래의 우선순위는 검토 제안이며 구현 완료 표시가 아니다.

## 1. 결론

CT의 CUDA API/ABI → PTX → SPIR-V → Level Zero 경로는 목표에 맞는다. 그러나 이 접근 자체가 최초는 아니다. 기존 실행 파일 호환성에서는 ZLUDA가 가장 가까운 비교 대상이고, CUDA 소스 재컴파일에서는 chipStar·SCALE·AdaptiveCpp가 중요한 비교 대상이다. 이들을 하나의 ‘CUDA 번역기’ 범주로만 비교하면 입력 조건과 실제 호환성을 잘못 판단하게 된다.

다음 작업의 중심은 **외부 프로그램을 고정하고 첫 실패를 재현하는 것**이어야 한다. 현재 구현에서 확인된 합법적인 nvcc PTX 수용 문제를 먼저 다루고, shared memory·동기화·비동기 자원 수명·수학 라이브러리를 단계적으로 연결한다. 기존 전체 계획의 의미론 검증도 함께 유지한다. 앱 하나를 위해 예외를 누적하거나 전체 컴파일러 완성을 기다리는 방식은 둘 다 피한다.

Rust 기반 Runtime/Driver와 자원 소유권 관리는 유지할 근거가 있다. LLVM 도입, 수학 라이브러리 연결, AMD 백엔드는 별도 타당성 시험을 거쳐 선택해야 하며 현재 번역 경로를 일괄 교체할 근거는 아직 없다.

## 2. 현재 CT가 증명한 범위

현재 개발 HEAD는 `219e6e5`이고, 실제 clean Arc 승인 코드 기준은 `5e2b302feb3b75d327710c95fc0c7cf574efe289`이다. 결과 문서와 실행된 코드 식별자는 구분한다. 상세 증거는 [P04c 결과](P04c-RESULTS.md)에 있다.

| 항목 | 확인된 상태 | 확대 해석하면 안 되는 부분 |
| --- | --- | --- |
| 실행 환경 | Windows x64 / Intel Arc B390 / Level Zero | AMD·다른 OS·다른 Arc 전체 검증 아님 |
| CUDA 연결 | Runtime26 / Driver39 export, 제한된 계약 | 함수 개수가 전체 CUDA 호환률을 뜻하지 않음 |
| 실제 producer | nvcc 12로 만든 제한 프로그램, default device-runtime 등록 메타데이터와 shared cudart 경로 검증 | device-runtime 함수 실행·일반 device linking·static cudart·임의 앱 지원 증거 아님 |
| PTX | 제한된 7.0/sm50 및 8.0/sm52 프로파일 | 현대 PTX 전체·SASS 해독 지원 아님 |
| 전역 변수 | scalar u32/u64, 초기화, 커널 접근과 호스트 심벌 복사의 저장소 공유 | 배열·구조체·일반 device 함수 지원 아님 |
| 승인 시험 | 필수 52/52, Rust137·Runtime77·Python152 등 이전 실행 증거 | 지원 앱 52개 또는 이번 조사에서 재실행한 결과 아님 |
| 도구 체인 | 진단용 MSVC override 경로 | 정식 지원 호스트 컴파일러·배포 자격 확보 아님 |

현재 launch 경로는 shared-memory 크기, non-null stream, 일부 packed 인자 경로를 거부하고 동기적으로 실행한다. PTX IR에는 shared/barrier/atomic 표현이 아직 없다. 버전 조회도 일반 앱이 기대하는 완전한 동작을 제공하지 않는다. 따라서 지금 단계는 **실제 CUDA 연결을 입증한 제한된 진단 프리뷰**라고 표현하는 것이 정확하다.

## 3. ‘CUDA 지원’이라는 말의 입력 조건부터 구분

1. **배포된 실행 파일·라이브러리 호환**: 원래 CUDA API/ABI 호출과 포함된 커널을 받아야 한다. CT의 최종 목표다.
2. **동일 CUDA 소스 재컴파일**: 원래 EXE 대신 다른 컴파일러로 다시 빌드한다. 소스가 있다면 매우 유용하지만 1번과는 다른 계약이다.
3. **소스 이식**: CUDA를 HIP·SYCL 등으로 바꾸고 수정·재검증한다.
4. **네이티브 실행 환경**: torch.xpu·SYCL·Level Zero 등으로 직접 실행한다. CT 비교 기준이나 부품은 될 수 있지만 기존 CUDA 바이너리 호환을 증명하지 않는다.

또한 ‘동일 바이너리를 여러 GPU에서 실행’한다는 말은 **특정 컴파일러로 새로 만든 범용 바이너리**를 뜻할 수도 있다. 임의의 기존 nvcc 실행 파일을 수용한다는 뜻인지 반드시 확인해야 한다.

## 4. 관련 프로젝트 비교

아래의 프로젝트 상태는 읽은 공식 문서에 대한 요약이다. 이 노트북에서 각 프로젝트를 설치·실행하여 검증한 결과는 아니다.

| 프로젝트 | 주 입력·접근 | 공식 자료에서 확인한 범위 | CT에 주는 의미 |
| --- | --- | --- | --- |
| ZLUDA | 기존 CUDA 앱 호환 계층 | 현재 문서는 AMD 중심. 과거 Intel 백엔드와 현재 지원은 구분 필요 | 바이너리 호환성에서 가장 직접적인 비교 대상 |
| chipStar | CUDA/HIP 소스 → SPIR-V → OpenCL/Level Zero | Intel 실행 경로, HIP 라이브러리 생태계와 앱 사례 | SPIR-V 의미 차이·라이브러리 연결·시험 설계 참고 |
| SCALE | CUDA 소스 재컴파일, 자체 툴킷 | AMD/NVIDIA 대상, CUDA API·수학 라이브러리 지원 | 소스 호환성과 라이브러리 제공의 중요성 참고 |
| AdaptiveCpp/PCUDA | CUDA 방언 소스 → 범용 컴파일/JIT | PCUDA는 실험적 부분집합, 여러 GPU/CPU 대상 | 범용 IR/JIT 설계 참고, 기존 nvcc EXE 호환과 구분 |
| SYCLomatic | CUDA 소스 → SYCL 변환 | 자동 변환 후 수동 보완·검증 필요 | 이식 경로와 지원 API 목록 참고 |
| HIPIFY/HIP | CUDA 소스 → HIP, 재빌드 | 소스 이식 도구·호환 API | AMD 생태계 활용 후보, 바이너리 호환 엔진 아님 |
| BarraCUDA | CUDA 소스 → 자체 IR → GPU 코드 | AMD/NVIDIA 등, Intel Arc는 장기 계획으로 서술 | 별도 컴파일러 사례, 현재 Intel 지원으로 세면 안 됨 |
| VUDA | CUDA와 유사한 Runtime + Vulkan | 헤더 변경과 SPIR-V 커널 사용 예제 | Vulkan 실행 부품 참고, 일반 PTX 번역기와 구분 |
| GPUOcelot | PTX 동적 컴파일·에뮬레이션 | 오래된 PTX 2.2/Fermi 기준 설명 | 의미론·에뮬레이터·시험의 역사적 참고 |
| Coriander | CUDA 소스 → OpenCL | 오래된 환경 및 라이브러리 어댑터 사례 | 설계 참고, 현대 Arc 호환 실증으로 보지 않음 |

### 4.1 ZLUDA: 오래된 설명을 그대로 재사용하면 안 됨

[공식 README](https://github.com/vosen/ZLUDA)는 수정하지 않은 CUDA 앱 실행을 지향한다. 다만 ‘near-native’는 프로젝트의 설명이며 모든 워크로드에 대한 보장이 아니다. [2026-06-29 개발 보고](https://vosen.github.io/ZLUDA/blog/zluda-update-q1q2-2026/)는 v6 발표, Blender에 필요한 기본 texture 지원, Windows 로더 개선과 PyTorch 작업을 설명한다. PhysX 32비트 작업은 당시 초기 단계로 읽어야 한다.

[FAQ](https://zluda.readthedocs.io/latest/faq.html)는 현재 AMD 지원과 과거 Intel 경로를 구분하지만, 자금 지원·Blender 계획 등 일부 설명은 날짜가 있는 개발 보고와 충돌한다. 따라서 ‘개발 중단’, ‘Windows 미지원’, ‘Blender 계획 없음’ 같은 예전 요약은 재사용하지 않는다. 이 조사에서 모든 배포 파일의 최신 버전과 기능을 직접 검증한 것은 아니다.

CT는 ZLUDA보다 우월하다고 말할 근거가 없다. 현재 Intel/Windows 실증을 쌓는 것은 타당하지만 다른 GPU에서 나온 ZLUDA 측정을 Arc CT와 직접 비교할 수는 없다.

### 4.2 chipStar: Intel 경로와 라이브러리 연결에서 특히 중요

[README](https://github.com/CHIP-SPV/chipStar)는 CUDA/HIP 소스를 SPIR-V로 컴파일하고 Level Zero/OpenCL에서 실행하는 경로를 설명한다. rocPRIM·hipCUB·rocThrust·rocRAND 및 Intel MKL을 사용하는 H4I 계열 연결, 여러 실제 앱 사례가 있다. [릴리스 페이지](https://github.com/CHIP-SPV/chipStar/releases)는 조사 시점 v1.3.0을 Latest로 표시했다.

그러나 [기능 표](https://github.com/CHIP-SPV/chipStar/blob/main/docs/Features.md)에는 미지원·제약이 남아 있다. HIP 지원 목록을 CUDA 전체 지원으로 바꾸어 읽으면 안 된다. CT가 참고할 것은 언어 의미 차이를 보정하는 방법과 시험·라이브러리 구조다. 기존 nvcc EXE를 chipStar가 자동으로 받아 준다고 가정하면 안 된다.

### 4.3 SCALE과 PCUDA: ‘재컴파일 없이’와 혼동 금지

[SCALE 문서](https://docs.scale-lang.com/stable/)는 CUDA 소스를 다시 컴파일하는 AMD/NVIDIA 툴킷과 라이브러리 지원을 설명한다. 확인한 대상 표에는 Intel이 없다. [공식 사이트](https://scale-lang.com/)의 2026년 성능 자료는 특정 AMD/NVIDIA 장치와 워크로드의 공급자 측정이므로 CT Arc 성능 예측에 사용할 수 없다. 라이선스와 재사용 권한도 별도 확인 대상이다.

[AdaptiveCpp](https://github.com/AdaptiveCpp/AdaptiveCpp)의 [PCUDA 설명](https://github.com/AdaptiveCpp/AdaptiveCpp/blob/develop/doc/pcuda.md)은 CUDA/HIP 방언을 범용 컴파일 경로로 처리하는 실험적 부분집합이다. 여러 장치용 단일 바이너리는 그 도구로 새로 빌드하는 계약이며 기존 nvcc 바이너리 호환 증거가 아니다.

### 4.4 이식 도구와 역사적 프로젝트

[SYCLomatic](https://github.com/oneapi-src/SYCLomatic)과 [HIPIFY](https://github.com/ROCm/HIPIFY)는 소스를 변환하고 다시 빌드하는 방법이다. 전자는 SYCL, 후자는 HIP 생태계로 이동한다. 기존 CUDA 배포 파일만 가진 사용자의 문제를 직접 해결하는 방식과 구분한다.

[BarraCUDA](https://github.com/AmesianX/barracuda)는 별도의 CUDA 소스 컴파일러이며 Intel Arc는 README의 장기 목표다. [VUDA](https://github.com/jgbit/vuda)는 CUDA와 비슷한 API와 Vulkan 실행의 사례다. [GPUOcelot](https://github.com/gpuocelot/gpuocelot), [Coriander](https://github.com/hughperkins/coriander)는 PTX 처리·소스 번역·라이브러리 대체의 참고 사례지만, 오래된 프로파일·환경을 현대 CUDA 전체 지원으로 인용하지 않는다.

## 5. 재사용할 부품과 직접 책임져야 할 계약

- [LLVM SPIR-V backend](https://llvm.org/docs/SPIRVUsage.html)는 LLVM IR을 SPIR-V로 내리는 도구다. PTX 파서·CUDA API·메모리 모델을 대신 구현해 주지 않는다. 현재 직접 SPIR-V 생성과 동일 소규모 코퍼스로 비교한 뒤 채택 여부를 정한다.
- [Level Zero](https://oneapi-src.github.io/level-zero-spec/level-zero/latest/core/PROG.html)는 제출·메모리·이벤트의 네이티브 기반이다. CUDA stream 순서와 자원 수명은 CT의 책임이다.
- [SPIR-V 사양](https://registry.khronos.org/SPIR-V/specs/unified1/SPIRV.html)에는 실행 환경·메모리 모델·scope 구분이 있다. SPIR-V라는 이름만 같다고 Vulkan shader와 OpenCL Kernel 모듈을 교환할 수 있는 것은 아니다.
- [oneMath](https://github.com/uxlfoundation/oneMath)는 여러 수학 백엔드의 인터페이스이며 CUDA ABI 대체품이 아니다. [oneDNN](https://github.com/uxlfoundation/oneDNN)은 DNN 연산 후보지만 cuDNN 호출을 그대로 받는 어댑터는 CT가 따로 설계해야 한다.
- [PyTorch Intel GPU 공식 안내](https://docs.pytorch.org/docs/2.14/notes/get_start_xpu.html)의 torch.xpu는 네이티브 기준선 후보다. XPU에서 모델이 실행됐다고 CT에서 CUDA wheel이 실행된 것으로 기록하지 않는다.

코드를 가져올 경우 라이선스·NOTICE·재배포 조건·의존성 버전을 구성요소별로 검토한다. 이번 조사에서는 외부 코드를 복사하거나 도구를 설치하지 않았다.

## 6. 기존 계획의 좋은 부분과 수정할 부분

[전체 계획](CT-UNIVERSAL-PLAN.md)은 이미 앱 첫 실패와 의미론 검증을 함께 진행하고, 전체 컴파일러 완성을 앱 시험의 선행 문턱으로 삼지 않도록 한다. 이 원칙은 유지한다. 이번 검토가 새로 발명한 원칙이라고 표현하지 않는다.

| 자료 | 현재 확인 | 후속 정리 방식 |
| --- | --- | --- |
| [실행 로드맵](CT-EXECUTION-ROADMAP.md) | 머리말이 M3e~M3o 중심으로 최신 Runtime·P04c 진전을 충분히 반영하지 않음 | P 번호를 유지하고 현재 상태 인덱스에서 최신 증거 연결 |
| [2026-10-20 검토](CT-REVIEW-2026-10-20.md) | 당시의 Runtime·primary context·validator·CI 부족 설명을 현재 상태로 읽으면 오류 | 역사 기록 유지, 현재 상태와 날짜 구분 |
| [앱 목록](compatibility/applications.json) | 파일은 존재. 후보 6개이며 실행 파일 해시가 비어 있고 availability가 missing | 후보 목록을 출처·빌드·실행 증거가 연결된 코퍼스로 발전 |
| [PTX 프로파일](compatibility/ptx-profile.md) | scalar32/64 설명과 일반 nvcc/cudart 미지원 문구의 경계를 명확히 할 필요 | 제한된 producer 지원과 일반 프로그램 미지원을 구분 |
| CPU CI | Windows CPU·SPIR-V validator 경로 존재 | GPU 승인·다중 제조사 CI와 분리 표기 |

가장 큰 계획상 위험은 세부 단계의 통과를 범용성의 증가량으로 오해하는 것이다. P04c의 성공은 저장소 공유·64비트 정확성에 대한 중요한 증거지만, shared/barrier·수학 라이브러리·비동기 실행의 공백을 줄여 주지는 않는다.

## 7. 권장 실행 순서와 완료 문턱

R 번호는 이번 검토의 작업 순서이며 기존 P00~P25를 대체하지 않는다. 각 단계 착수 시에만 파일·API·실패 시험을 포함한 상세 계획을 만든다.

### R0. 현재 상태와 외부 프로그램 증거 고정

- 최신 구현·테스트·환경·지원/미지원 표를 하나의 현재 상태 인덱스로 연결한다.
- 앱 목록에 upstream revision, 원래/수정 빌드 방식, compiler flags, artifact SHA256, 실행 환경, 기대 출력, 첫 실패 API/PTX를 기록한다.
- cudart의 shared/static 연결 방식과 PTX 포함 여부도 기록한다. static cudart는 CT Runtime DLL 교체만으로 해결되지 않으며 원래 Runtime이 호출하는 Driver API를 충족해야 한다. shared로 재빌드한 결과를 원래 static 배포 바이너리의 성공으로 세지 않는다.
- 증거 등급은 CT fixture / upstream 소스 수정 빌드 / upstream 원래 레시피 / 배포 바이너리로 구분한다. 소스를 고친 결과는 원본 앱 무수정 호환으로 세지 않는다.
- 첫 대상 후보는 기존 vectorAddDrv와 Runtime vectorAdd 계열, 이후 reduction·shared-memory 예제, BLAS 예제, 하나의 고정된 외부 앱이다. 이 목록은 선정 제안이며 실행 완료 목록이 아니다.
- 완료: 최소 하나의 Driver와 Runtime 외부 경로에서 재현 가능한 성공 또는 정확한 첫 실패가 기록되고, 비밀값·사용자 경로 없이 공유할 수 있어야 한다.

### R1. 실제 nvcc 입력을 막는 작은 의미론·ABI 간격

- P04c 과정에서 만난 `ld.global.u32` → 64비트 레지스터 문제를 우선 재현한다. [PTX 12.0.1 사양 9.4.1](https://docs.nvidia.com/cuda/archive/12.0.1/parallel-thread-execution/index.html)은 일부 ld/st/cvt에서 더 넓은 레지스터를 허용한다. 현재 거부를 입력 오류라고 취급하면 안 된다.
- 부호 확장·영 확장·저장 절단을 명령별로 구현한다. 단순히 타입 검사를 제거하지 않는다. signed 경계·상위 비트·잘못된 타입과 폭을 함께 검사한다.
- 64비트 메모리 접근이 있다는 이유로 모든 포인터에 align8을 요구하는 제약은 주소별 실제 접근과 provenance에 따라 다룬다. 검증 없이 일괄 정렬 완화하지 않는다.
- 버전·장치 기능 조회는 실제 보장 범위를 정하고 구현한다. 실행시키기 위해 버전 번호만 높이거나 미지원 기능을 있다고 응답하지 않는다.
- 완료: 실제 producer가 만든 입력, 의미론 경계 시험, validator, Arc 재현을 연결한다. 허용한 프로파일과 남은 미지원 항목을 갱신한다.
- R1 전체를 한 번에 구현하지 않는다. 첫 실행 문턱은 widened-register 재현과 해당 명령의 의미론 수정으로 한정하고, 주소 provenance와 기능 조회는 독립 후속 문턱으로 나눈다.

### R2. P10 shared memory + 제한된 전체 block barrier

- 우선 정적 shared allocation과 block 전체가 참여하는 동기화로 범위를 정한다. 동적 shared allocation은 별도 계약으로 확장한다.
- 주소 공간·초기화 규칙·크기/정렬·block별 격리·메모리 가시성을 함께 설계한다.
- 완료: 서로 다른 block의 간섭 없음, 비정렬 데이터 길이의 reduction·타일 연산 결과, shared 용량 초과 거부, barrier 이전 쓰기의 이후 가시성.
- 발산 barrier를 무작정 실행해 노트북을 멈추게 하지 않는다. 첫 프로파일에서 지원 가능한 형태를 명시하고 입증하지 못한 형태는 번역 단계에서 거부한다.

### 병행 A. P07/P08 제출·완료·수명 → stream/event

- 현재 동기 실행을 비동기로 바꾸기 전에 command/event/queue 소유권과 완료 후 정리를 설계한다.
- in-flight allocation 해제, module unload, context destroy, 오류 지연 보고, default stream과 legacy/PTDS 의미를 정의한다.
- 완료: 여러 제출의 순서·event dependency·동시 수명 경계·실패 정리가 재현된다. 단순 synchronize 삭제만으로 비동기 지원이라고 하지 않는다.
- shared-memory 번역과 설계 검토는 병행 가능하지만, 같은 Runtime 상태를 동시에 수정하는 구현은 소유 파일과 통합 순서를 먼저 정한다.

### 병행 B. P16 BLAS 연결 타당성 시험

- 첫 후보는 `cublasSgemm_v2`의 제한된 계약과 Intel oneMKL/oneMath 연결이다. 전체 cuBLAS 구현을 약속하는 단계가 아니다.
- Level Zero와 SYCL 쪽 context·USM·native handle·queue 상호 운용과 순서를 먼저 입증한다. 기존 포인터를 곧바로 전달해도 된다고 가정하지 않는다.
- 열 우선 배열, transpose, lda/ldb/ldc, alpha/beta, host/device pointer mode, 수치 허용 오차와 handle/context 수명을 검사한다.
- 완료: 같은 GPU와 데이터에서 정확한 GEMM을 실행하고 복사·동기화 비용을 분리한다. CPU fallback은 명시적 정책이며 GPU 통과로 기록하지 않는다.

### R3. P11/P12 atomics·memory scope·warp

- atomic 연산은 타입·주소 공간·순서·scope와 함께 추가하고, fence 및 barrier와의 상호작용을 검사한다.
- CUDA 논리 warp32와 mask/shuffle 규칙을 구현한다. Intel subgroup 크기를 그대로 CUDA warp로 취급하면 안 된다. [CUDA 실행 설명](https://docs.nvidia.com/cuda/cuda-programming-guide/03-advanced/advanced-kernel-programming.html)을 기준으로 독립 스레드 진행·참여 조건을 구분한다.
- 완료: reduction/scan 계열의 경계·부분 warp·mask 시험과 가시성 시험. 이 단계만으로 cooperative groups 전체 지원을 선언하지 않는다.

### R4. device 함수·수학·JIT와 producer 확대

- P04의 남은 device function, 호출 ABI, 필요한 libdevice 연산을 앱 추적으로 선정한다. NVRTC는 PTX를 만드는 frontend이고 Intel GPU 실행 backend는 계속 필요하다.
- 새 PTX 버전·fatbin 형식·연결 방식을 코퍼스로 확장한다. 버전 문자열만 허용 범위에 추가하지 않는다.
- [CUDA 13.0 릴리스 노트](https://docs.nvidia.com/cuda/archive/13.0.0/cuda-toolkit-release-notes/)는 Maxwell/Pascal/Volta의 offline compilation 및 라이브러리 지원 제거를 명시한다. 기존 sm52 생산 경로를 유지하면서 새 producer 시험 경로를 병행한다.
- [nvcc 문서](https://docs.nvidia.com/cuda/cuda-compiler-driver-nvcc/index.html)의 fatbinary는 PTX만을 뜻하지 않는다. PTX가 없는 CUBIN/SASS-only 배포물은 P24의 별도 연구 대상이다. PTX 변환으로 자동 해결된다고 약속하지 않는다.

### R5. 실제 앱과 프레임워크

- 하나의 upstream 앱을 버전 고정하여 수정 범위·의존성·실행 재현성을 기록한다. 지원 행렬은 앱/버전/빌드/장치 단위로 작성한다.
- PyTorch는 CUDA wheel·CUDA 수학 라이브러리·allocator·stream·JIT/custom kernel 등의 의존성을 먼저 추적한다. torch.xpu 성공과 CT CUDA 경로 성공을 별도로 기록한다.
- 작은 정수·FP16/BF16·FP64·벡터/구조체 ABI와 부동소수점 NaN/무한대/비정규수·반올림 규칙도 별도 계약이 필요하다. scalar u64 지원을 이들의 기반 검증까지 끝난 것으로 해석하지 않는다.
- P17/P18/P20~P22의 라이브러리·프레임워크·메모리·고급 실행·다중 장치 범위를 유지한다. MMA/저정밀, Graph/capture, texture/surface, cooperative 실행, 외부 메모리/IPC, NCCL은 실제 앱 요구에 따라 별도 타당성을 판단하며 이번 순서표에서 생략됐다고 완료·불필요로 간주하지 않는다.
- 완료: 고정된 실제 작업이 CUDA 경로로 실행되고 결과·메모리·수명·재실행이 검증된다. 한 모델 성공을 전체 PyTorch 지원으로 확대하지 않는다.

### R6. AMD·OS·배포 확장

- AMD 장치가 없으므로 지금은 backend 계약·오프라인 번역·CPU 검증까지 가능하다. 실제 AMD 실행은 not_run으로 둔다.
- Linux 및 다른 Arc 세대, 지원 호스트 컴파일러, 설치/진단/제거 경로를 별도 검증한다.
- 시스템 CUDA 설치를 덮어쓰지 않는 앱 단위 배포를 우선한다. 기존 NVIDIA 환경과 충돌·복구 절차도 제품 요구사항이다.
- 사용자 PC의 CUDA 입력은 신뢰하지 않는 데이터로 취급한다. fatbin 해제 한도·오버플로·파서 오류·stale handle·native 메모리 수명을 기능 확장마다 회귀 검사한다.

## 8. 성능을 언제, 어떻게 말할 것인가

현재 증거로 최종 성능이나 완성률을 숫자로 예측할 수 없다. 정확성 통과 후 **같은 Arc, 같은 연산·입력·정밀도**에서 CT와 네이티브 Level Zero/SYCL 경로를 비교한다. 가능하면 같은 알고리즘을 사용하고 라이브러리·컴파일 옵션 차이도 기록한다.

- cold compile, cache hit, host/device transfer, submission, GPU kernel, end-to-end를 구분한다.
- 초기 제안은 warm-up 5회와 측정 30회이며 실행 시간과 변동성에 따라 조정한다. 중앙값·꼬리 지연·실행 조건을 함께 남긴다.
- GPU timestamp가 없으면 CPU wall time을 kernel time으로 부르지 않는다.
- CUDA/NVIDIA 결과와 비교할 때는 장치·전력·라이브러리 차이를 공개한다. 제조사가 다른 장치의 비율을 번역 오버헤드로 해석하지 않는다.
- ZLUDA/SCALE/chipStar의 발표 수치는 비교 설계 참고이며 CT의 예상 배속이 아니다.

## 9. 바로 다음 작업 권고

**R0의 최소 앱 증거 고정과 R1의 relaxed operand width 문제를 하나의 작은 실행 계획으로 묶는 것이 우선이다.** 기존 P04c 승인 자료를 보존하고, nvcc가 만든 재현 입력을 통해 parser → IR → SPIR-V → CUDA 실행 연결을 검증한다. 이어 P10 shared/barrier를 설계하고, 제출 수명과 BLAS 상호 운용은 별도 타당성 조사로 병행한다.

이 순서는 목표를 축소하지 않는다. ‘어떤 CUDA 프로그램을 왜 실행하지 못하는가’를 증거로 쌓아 범용성에 필요한 기능을 순서대로 구현하기 위한 것이다. 범용 드라이버라는 제품 표현과 별개로 현재 CT는 사용자 공간 CUDA 호환 계층이며, Intel의 실제 장치 드라이버 위에서 실행된다는 구조도 명확히 설명해야 한다.
