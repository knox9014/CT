# CT 구현 로드맵: 작업 묶음·의존성·완료 판정

> 2026-11-06 검토 후에는 NVIDIA 드라이버 공존과 GPU 선택 일치를 먼저 해결한다. 다른 Intel 모델에서 공개 예제를 재현한 뒤 실사용 앱의 차단점과 Intel 시험 배포 기준을 검증한다. [최신 Intel 실행 순서](superpowers/plans/2026-10-27-intel-qualification-next.md#2026-11-06-검토-후-실행-순서)

> 2026-10-27 현재 상태와 우선순위는 [전체 재검토](CT-REVIEW-2026-10-27.md)와 [Intel 후속 실행 계획](superpowers/plans/2026-10-27-intel-qualification-next.md)을 따른다. 아래 P 번호·의존성·과거 완료 기록은 보존하며, 머리말의 M3 기준을 최신 구현 범위로 읽지 않는다.

2026-11-06 공개 Driver 경로를 현재 CT 빌드에서 재검증했다. `pwsh -NoProfile -File scripts/run_m3e_smoke.ps1`에서 NVIDIA 원본 vectorAddDrv 호스트가 압축 fatbin으로 50,000개 계산을 통과했다. 공개 CLI가 실행 파일과 fatbin을 그대로 전달했고, 별도 GPU 검증 14건도 통과했다. 이 예제를 공개 Driver 경로의 대조군으로 사용한다.

비샘플 후보는 Numba의 공개 Driver 경로다. [Numba 장치 생성 코드](https://github.com/numba/numba/blob/main/numba/cuda/cudadrv/driver.py#L3043-L3122)는 장치 번호, compute capability, 이름, UUID를 조회한다. 먼저 Windows 배포본과 의존성을 고정하고, 프로세스별 Driver 경로 설정으로 장치 열거와 첫 실패를 기록한다. 위 소스 검토는 후보 선정에만 사용한다. 장치 선택이 통과하면 작은 원본 CUDA 계산과 독립 CPU 정답을 비교한다. CuPy의 미확정 초기화 계약은 [별도 조사 기록](superpowers/plans/2026-10-28-r2b-static-runtime-contract.md)에 유지한다.

Numba 0.65.1 Windows x64 배포본의 첫 실행을 확인했다. CPython 3.14.3의 격리 환경에 공식 wheel 세 개를 설치하고 `NUMBA_CUDA_DRIVER`로 새로 빌드한 CT DLL을 지정했다. 원본 패키지의 `numba.cuda.cudadrv.driver.driver.get_device_count()`는 `cuInit(0)`을 통과한 뒤, `_initialize_extras`에서 `cuIpcOpenMemHandle_v2` 및 구형 이름의 주소를 찾는 과정에서 멈췄다. 두 이름이 모두 없어 Python 대체 함수가 반환됐고, Numba가 그 함수를 C 포인터로 등록하다 `ctypes.ArgumentError`를 냈다. strict와 `ct-sm52-subset-v1`은 같은 지점에서 멈췄다. 동일 DLL의 별도 직접 호출은 Arc B390 한 개를 열거했다.

사용한 wheel SHA-256은 Windows x64 CPython 3.14 배포본 기준이다.

| 패키지 | SHA-256 |
| --- | --- |
| numba 0.65.1 | `2a20fcdabdefbdacf88d85caf70c3b18c4bcb7ebb8f82e6a19486383dd26ab63` |
| llvmlite 0.47.0 | `694e3c2cdc472ed2bd8bd4555ca002eec4310961dd58ef791d508f57b5cc4c94` |
| numpy 2.4.4 | `715d1c092715954784bc79e1174fc2a90093dc4dc84ea15eb14dad8abdcdeb74` |

다음 검증에서는 정확한 Windows x64 ABI로 주소 조회와 실제 IPC 호출을 구분한다. Numba가 관찰된 경로에서 요구한 것은 등록할 함수 주소다. 별도 네이티브 호출로 미지원 IPC가 오류를 반환하는지 확인한 뒤, 원본 Numba의 장치 열거를 재실행한다. [CUDA Driver IPC 규약](https://docs.nvidia.com/cuda/archive/12.9.0/cuda-driver-api/group__CUDA__MEM.html)

후속 실행에서 CT는 직접 조회용 `cuIpcOpenMemHandle_v2`를 제공했다. NVIDIA 헤더로 컴파일한 Windows x64 호출 시험에서 출력 초기화, 미지원 오류, 널 출력 오류를 확인했다. 원본 Numba 0.65.1은 두 모드 모두 장치 1개를 열거했다. strict에서는 compute capability 조회가 801로 끝났다. 기존 실험 타깃에서는 compute capability와 장치 이름 조회를 지나 `cuDeviceGetUuid` 주소 조회에서 멈췄다. 다음 장치 식별 시험은 네이티브 UUID의 출처와 수명을 검증하고 공개 기록에서 식별자 원문을 제외해야 한다.

`cuDeviceGetUuid` 추가 후 기존 실험 타깃에서 원본 Numba의 장치 상세 조회가 통과했다. Level Zero 기본 시험이 별도 프로세스에서 선택한 UUID와 CT 조회 결과를 비교했고, 식별자 원문은 출력하지 않았다. 이어서 `cuda.current_context()`는 기본 컨텍스트를 확보하고 스레드에 올린 뒤 `cuMemGetInfo` 조회에서 멈췄다. 다음 단계는 실제 가용 메모리의 출처를 확인하는 것이다. 기존 총량 조회만으로 가용 메모리를 구할 수 없다.

Arc B390의 Windows 시스템 Level Zero 로더에서 Sysman 메모리 모듈 한 개를 확인했다. `zesMemoryGetState`는 성공을 반환하고 크기 필드를 채웠지만, 서로 다른 초기값을 넣어 두 번 시험했을 때 `free`를 모두 그대로 두었다. Core의 현재 가용 메모리 확장도 드라이버 목록에 없었고, `zeDeviceGetProperties`에 확장 구조체를 연결한 두 호출은 가용량 필드를 채우지 않았다. 이 구성에서 두 경로 모두 실제 가용량을 제공하지 않아 `cuMemGetInfo`의 구현 근거가 부족하다. [Level Zero Sysman 메모리 규약](https://oneapi-src.github.io/level-zero-spec/level-zero/latest/sysman/api/apis/memory.html) · [Level Zero 가용 메모리 확장](https://oneapi-src.github.io/level-zero-spec/level-zero/1.18.31/core/api/extensions/device.html) · [CUDA 메모리 조회 규약](https://docs.nvidia.com/cuda/cuda-driver-api/cuda_driver_api/group__CUDA__MEM.html)

Windows DXGI 대조 시험에서는 Level Zero가 공개한 LUID와 노드 마스크로 같은 Intel 어댑터의 로컬 메모리 예산을 조회했다. LUID 원문은 출력하지 않았다. 새 프로세스 두 개에서 각각 CT로 32 MiB를 할당하고 전체를 채웠다. 두 실행 모두 DXGI 프로세스 사용량은 39,284,736바이트에서 76,271,616바이트로 증가했다. CT에서 할당을 해제하고 컨텍스트를 닫은 직후와 500ms 뒤에도 같은 사용량이 보고됐다. 이 실험에서 DXGI는 CT 메모리 사용을 관측할 수 있었지만, 관측한 프로세스 예산과 사용량으로 장치 전체의 가용량을 확인할 수는 없었다. `cuMemGetInfo`는 운영체제가 보고하는 장치 가용량을 요구하므로 이 수치로 성공 응답을 제공할 근거는 아직 없다. [DXGI 조회 계약](https://learn.microsoft.com/en-us/windows/win32/api/dxgi1_4/nf-dxgi1_4-idxgiadapter3-queryvideomemoryinfo) · [CUDA 메모리 조회 규약](https://docs.nvidia.com/cuda/cuda-driver-api/cuda_driver_api/group__CUDA__MEM.html)

작성: 2026-10-19. 구현 기준 `4b0c64f` / M3e.
상태: P00/P01을 [M3f](M3f-RESULTS.md), P02를 M3g로 구현·Arc 검증했다. 나머지 P 작업은 계획이며,
첫 구현으로 전체26개 작업 또는 기존 M3/M4 릴리스 문턱을 통과한 것은 아니다.
후속 P02: [M3g](M3g-RESULTS.md)로 제한 프로파일의 여러 entry/함수별 ABI/수명을 구현·검증했다.
P03a의 다차원 실행은 [M3h](M3h-RESULTS.md)로 구현·Arc 검증했다. P03의 정수·비트 연산과 인자 형식 확장은 남아 있다. 저장된 전역 변수와 device 함수는 P04다.
후속 [M3i](M3i-RESULTS.md)는 P19의 기본 오류 주입·실패 차단을 검사했다. 실제 장치 장애·자동 복구 또는 P19 전체 완료는 아니며, 다음 기능 작업은 P03의 정수·비트 연산 확장이다.
P03b의32/64비트 정수 변환·비트·시프트 연산은 [M3j](M3j-RESULTS.md)로 구현·Arc 검증했다. 추가 정수 연산·작은 정수 타입·벡터/구조체 ABI는 후속 P03 작업이다.
P03c의 정수 global 메모리와 명시적 scalar64 ABI는 [M3k](M3k-RESULTS.md)로 검증했다. 암묵적 scalaru64 분류, wide entry의 혼합 포인터 정렬, 작은 정수·벡터/구조체 ABI는 남아 있다.
요구사항: [전체 목표 G0~G14](CT-COMPLETION-GOALS.md).
P03g의 제한된 부호 있는 정수 상수와 signed mov 별칭은 [M3o](M3o-RESULTS.md)로 Arc 검증했다. 일반 상수 수식과 작은 정수·구조체 ABI는 후속 작업이다.
P03f의 정수 min/max·abs/neg는 [M3n](M3n-RESULTS.md)으로 Arc 검증했다. 나머지 P03과 일반 Runtime·병렬 기능은 후속 작업이다.
P03e의32/64비트 정수 비교6종과 정수 선택은 [M3m](M3m-RESULTS.md)으로 Arc 검증했다. 작은 정수·벡터/구조체 ABI 등은 후속 작업이다.
P03d의32/64비트 modular add/sub/mul.lo/mad.lo는 [M3l](M3l-RESULTS.md)로 Arc 검증했다. 작은 정수·벡터/구조체 ABI와 나머지 연산은 후속 작업이다.
첫 실행 명세: [M3f 명세](superpowers/specs/2026-10-19-m3f-selection-design.md).
첫 실행 계획: [P00/P01 상세 계획](superpowers/plans/2026-10-19-m3f-selection.md).

Numba의 메모리 조회 이후 경로를 확인하기 위해 별도 시험용 DLL을 빌드했다. 기존 CT 호출을 전달하고 `cuMemGetInfo_v2`에는 같은 어댑터의 DXGI 프로세스 예산과 예산 잔여량을 반환한다. 원본 Numba 0.65.1은 실험 타깃에서 컨텍스트 초기화와 메모리 조회를 통과했고, 정수 16개를 GPU로 복사했다가 호스트로 가져와 전부 일치함을 확인했다. JIT 계산은 로컬 환경의 NVVM 라이브러리 부재에서 멈췄다. 프로세스 예산 응답은 시험용 DLL의 동작이며 장치 전체 가용량과는 의미가 다르다.

다음 실행에서는 로컬에 준비된 NVIDIA NVVM과 libdevice를 자식 프로세스에 연결했다. 원본 Numba의 JIT 경로는 컴파일러 부재 오류를 지나 `cuLinkCreate` 주소 조회에서 멈췄다. 같은 정수 증가 커널을 Numba의 `compile_ptx`로 별도 컴파일해 PTX 8.0 / sm_52 입력을 생성했다. 링크 단계를 건너뛴 별도 진단에서 CT의 `cuModuleLoadData`도 그 입력을 218로 거부했다. 따라서 Driver 링크 API와 생성 PTX 수용 범위를 각각 검증해야 한다. 커널 실행과 정답 검사는 아직 이뤄지지 않았다.

PTX 파서에 원본 출력을 직접 넣으니 첫 실패는 128바이트 제한을 넘는 컴파일러 생성 전역 이름이었다. 이 출력의 가장 긴 이름은 173바이트다. 이름 한도를 256바이트로 늘리고, 단일 모듈에서 초기값이 없는 정렬 8바이트 `.common .global .u64` 선언을 허용했다. 이후 원본 입력은 포인터 추론에서 멈췄다. 진단 복사본에서 배열 데이터 주소를 제외한 여섯 매개변수 선언만 같은 폭의 `.b64`로 표시하자 파싱이 통과했다. 원본 Numba 출력은 배열 길이, 스트라이드, 쓰이지 않는 슬롯도 `.u64`로 선언하므로 CT가 사용처로 구분해야 한다. 진단 복사본은 GPU에서 실행하지 않았다.

후속 구현은 선언의 사용처를 검사한다. 읽지 않는 슬롯과 한정된 정수 연산에만 쓰이는 슬롯을 스칼라로 분류하고, 명시적인 전역 주소 변환에 쓰이는 인자에는 기존 포인터 검증을 적용한다. Intel 백엔드의 전역 이름 한도도 256바이트로 맞췄다. 수정하지 않은 Numba PTX를 CT Driver로 직접 로드해 Arc B390에서 입력 크기 1, 16, 37을 실행했다. 증가 결과 54개와 경계 검사값 96개가 모두 일치했다. 이 시험은 별도 호스트에서 커널을 실행했으므로 원본 Numba의 JIT 호출 경로에는 Driver 링크 API가 남아 있다.

별도 시험용 DLL에 단일 PTX 입력용 Driver 링크 경로를 연결했다. 링크 결과는 소유권을 관리하는 NUL 종료 PTX이며, CT의 기존 모듈 로더로 전달한다. 원본 Numba 0.65.1의 JIT 실행에서 링크 상태 생성, PTX 입력, 결과 복사, 상태 해제, 모듈 로드와 커널 핸들 조회까지 통과했다. 다음 실제 실패는 `cuFuncGetAttribute` 주소 조회다. 설치된 Numba의 코드에서 첫 요청은 레지스터 수이며, 이어서 상수·로컬·공유 메모리 크기와 최대 스레드 수를 요청한다. 해당 값의 출처를 확인해야 하며, 이 실행에서는 커널을 아직 제출하지 않았다.

2026-11-08에는 Numba의 커널 속성 사용처를 검사했다. 고정된 블록 크기로 실행하는 시험에서 속성들은 리소스 정보 조회용으로 보관된다. 시험 프로세스에서만 Numba의 속성 조회를 `None` 값으로 대체하고, 같은 시험용 메모리·링크 DLL로 JIT 실행을 검증했다. Arc B390에서 크기 1, 16, 37, 257의 정수 증가 계산 311개와 경계 검사값 128개가 일치했다. 이 결과에는 Numba 메타데이터 어댑터와 DXGI 프로세스 예산 정책이 필요하다. 재현 명령은 `.cache/numba-0651/env/Scripts/python.exe -I -B scripts/numba_jit_experiment.py --provider .cache/numba-0651/dxgi/link-probe.dll --toolkit .cache/p09a2-producer/toolkit`이다. 실행기는 종료 시 Numba의 조회 메서드를 복원한다. 초기 실행기의 명시적 컨텍스트 종료는 살아 있는 장치 배열보다 먼저 일어나 해제 오류 201을 냈고, 종료 순서를 Numba의 기존 수명 관리에 맡겨 재실행을 통과했다.

같은 실행기를 두 커널과 반복 실행으로 확장했다. 정수 증가와 정수 affine 커널을 동일 GPU 배열에서 번갈아 총 28번 실행했다. 입력 길이 0, 1, 16, 32, 33, 37, 257을 포함해 빈 입력, 블록 경계와 블록보다 큰 입력을 확인했다. 별도 프로세스 두 번 모두 정답 비교 752개와 경계 검사값 448개가 일치했다. 이 총계는 반복 실행마다 다시 확인한 결과를 포함한다. 두 실행 모두 기존 메타데이터 어댑터와 프로세스 예산 정책을 사용했다.

## 1. 실행 원칙

- 전체 제품을 한 번에 상세 코딩 계획으로 고정하지 않는다. 전체 작업의 입력·출력·문턱은
  이 문서에 고정하고, 실제 착수할 묶음만 파일·서명·실패 시험까지 확정한다.
- 선행 작업의 출력이 확인되지 않으면 후속 작업은 상세 설계만 가능하며 구현 완료로 세지 않는다.
- 미지원/실패/장비 미확보를 구분한다. 준비된 샘플만으로 일반 앱 호환을 선언하지 않는다.
- 기존 M3/M4 릴리스 문턱을 유지한다. P 번호는 별도 기능 추적 번호이며 버전 번호가 아니다.
- 개인정보 보호, 진단, 회귀 시험은 마지막 단계가 아니라 매 작업의 필수 조건이다.

## 2. 전체 작업과 의존성

| ID | 선행 작업 | 산출물·범위 | 완료 증거 |
| --- | --- | --- | --- |
| P00 | M3e | 버전 있는 기능/ABI/시험 추적표; 기존26 export와 현재 PTX 프로파일 고정 | 헤더와 export 일치; 시험 참조 유효; 미실행을 pass로 기록 못함 |
| P01 | P00 | M3f: 제한된 복수 PTX 선택, 메타데이터/본문 프로파일 확인, 누적 해제 크기 제한 | 순서 독립 선택, 모호성/오류 거부, 실제 압축/비압축 producer와 Arc 검사 |
| P02 | P01 | 여러 entry가 있는 모듈 IR와 함수별 ABI; module 소유권과 function handle 수명 | add/sub 등 다른 entry 동시 조회; ABI 혼동·중복·unload 후 접근 거부; 구조체 추가 전 offset/size/alignment/address-space 비교 확장 |
| P03 | P02 | 2D/3D 실행, s/u32/64 변환·비트 연산; 이후8/16비트·벡터/구조체 ABI | 비정렬 크기의2D 행렬/3D 인덱스, signed 경계, 인자 배치와 overflow 시험 |
| P04 | P02/P03 | global/constant 저장소·초기값·조회, local/generic 주소, device 함수·수학 함수 연결 | 여러 커널이 공유한 global 값, constant 읽기, 함수 호출/인자/반환 정답 |
| P05 | P00 | primary context·참조 수·reset·TLS 상태, Driver/Runtime 공유 계약 | 두 호스트 스레드/독립 소비자의 retain/release/reset와 stale handle 검사 |
| P06 | P05 | D2D·memset·pinned host·pointer 속성, pitched/2D/3D 전송 단계별 확장 | 교차 context/범위/정렬/크기0/해제 시험, 독립 byte 기준값 |
| P07 | P05/P06 | 비동기 기반: submission/completion, queue/event 소유권, in-flight 자원 보존 | 완료 전 free/unload/destroy, event 재기록, 실패·대기 중 재진입 검증 |
| P08 | P07 | stream/event API·기본 stream 규칙·비동기 복사·callback/host function | 두 stream 의존 그래프, NOT_READY, pageable/pinned 계약, 지연 오류 시험 |
| P09 | P02/P05/P06 | 일반 Runtime 연결의 첫 동기 프로파일, 내장 fatbin·kernel/global 등록 | 변경 없는 동적 cudart 대상 호스트, Driver 혼용, 초기화/해제·TLS 오류 검사 |
| P10 | P03/P04 | shared memory·dynamic shared·block barrier, 협력 block 알고리즘 | 타일 GEMM/reduction; 부분 block·분기 참여·자원 제한 검사 |
| P11 | P10 | atomic·reduction·fence·메모리 순서/scope | 경쟁하는 카운터/histogram, 허용 결과 집합을 정의한 memory litmus 시험 |
| P12 | P10/P11 | 논리 warp의 vote/shuffle/ballot/mask, subgroup 차이 보존 | 분기 mask·부분 warp·다양한 block 크기의scan/reduction; 장치별 교차 결과 |
| P13 | P04 | Runtime에 의존하지 않는 NVRTC/JIT/분리 컴파일·장치 링킹 경로 | 런타임 생성 커널과 두 object의 device 함수 참조, 미해결 심볼 진단 |
| P14 | P00; 장비 접근 | AMD 경로 실현성: 정확한 OS/GPU/툴체인 고정, 네이티브 실행·인자 ABI | 실제 AMD 메모리 왕복/커널 정답; 불가 조합과 원인 문서화 |
| P15 | P14 및 기존 M3e IR; 확장은 P03/P04 | 공통 의미와 AMD 코드 생성/실행 연결; 비동기/병렬은 P08/P10~12 결과별 추가 | 최초 제한 프로파일부터 같은 OS/ABI의 동일 앱/PTX가 Intel·AMD 공통 시험 통과 |
| P16 | P05/P06; P08은 비동기 확장 시 | cuBLAS FP32 GEMM부터 library ABI·handle·pointer mode·stride/batch | transpose/leading dimension/NaN·수치 오차/workspace·오류 검사 |
| P17 | P16; 연산별 P03/P08/P10~13 | cuBLASLt·cuFFT·cuRAND·cuSPARSE·cuSOLVER·cuDNN, 저정밀/FP64 | 라이브러리별 독립 정답과 실제 소비자; 단순 DLL 이름 치환 금지 |
| P18 | P00부터 조사; 실행은 앱별 필요 P | 외부 앱/AI 의존성 목록과 고정 버전; 추론→학습→프레임워크/JIT 확장 | 아래 앱 선정 문턱과 동일 artifact의 실행/정확성/반복성 검사 |
| P19 | P00부터 누적; 출시는 선택 P 전부 | doctor/inspect/run·캐시·패키징·공존·fault injection·성능·배포 조건 | 아래 공통 검증 문턱과 릴리스 증거표 |
| P20 | P00; 관련 P05~08 | CUDA array·texture/surface, VMM/pool·Unified Memory | 기능별 주소/일관성/수명 시험; 불가능 기능은 명시적으로 비지원 |
| P21 | P03/P08/P10~12 | MMA/저정밀·Graph/capture·cooperative/cluster·device 비동기·동적 병렬 실행 | 각 기능의 실현성 실험→별도 명세→의미/수치/성능 시험 |
| P22 | P08/P15; 다중 장치 접근 | multi-GPU/peer/IPC·external memory/semaphore·NCCL·분산 | 실제 다중 장치의 전송·순서·통신·실패 회복, 동일 앱 시험 |
| P23 | P00; 해당 도구/장비 | graphics/video interop·CUPTI/profiling/debugging·NVML 등 주변 의존 | API별 기능 범위, 원래 도구/소비자의 명시적 지원 또는 진단 |
| P24 | P00/P03/P04; 연구 경로 | PTX 없는 cubin/SASS: 명령/재배치/호출 ABI와 메모리 의미의 별도 엔진 | 한 아키텍처/좁은 명령 집합의 feasibility 실험 후 go/no-go; 성공 추정 금지 |
| P25 | P00; 해당 OS/장비 | Linux ABI/로더·Intel 추가 모델/드라이버·추가 호스트 아키텍처 | OS별 같은 artifact의 NVIDIA/CT 비교 및 모델별 실제 실행 |

P03/P04/P17/P20~25는 각각 여러 하위 PR로 나눈다. 첫 하위 PR의 명세에는 입력 집합,
API/명령 변형, 변경 파일, 오류·자원 한계와 재현 시험을 반드시 고정한다.
특히 P17/P21~25는 아직 실행 가능한 코드 명세가 아니라 연구/확장 작업의 경계다.

## 3. 전체 목표의 누락 방지

| 요구사항 | 담당 작업 |
| --- | --- |
| G0 지원 계약 | P00 및 모든 작업의 지원 표 갱신 |
| G1 로딩/모듈 | P01/P02/P04/P09/P13 |
| G2 PTX 일반화 | P02/P03/P04/P13/P17/P21 |
| G3 병렬 의미 | P03/P10/P11/P12/P21 |
| G4 Driver/컨텍스트 | P00/P05 및 P06/P08/P09의 ABI 추가 |
| G5 메모리 | P06/P07/P20/P22 |
| G6 stream/event | P07/P08 |
| G7 Runtime | P09, P08 완료 후 비동기 Runtime 확장 |
| G8 JIT/링킹 | P13; LTO IR는 같은 작업의 별도 feasibility gate |
| G9 Intel/AMD | P14/P15/P25 |
| G10 라이브러리 | P16/P17; Thrust/CUB 생성 커널은 P03/P10~12/P18 |
| G11 실제 앱/AI | P18; TensorRT는 별도 의존성/실현성 조사로 편입 |
| G12 제품/보호 | P19 및 모든 PR의 공개 검사 |
| G13 검증/성능 | P00/P19 및 모든 작업의 의미 시험 |
| G14 장기 확장 | P20~25; P17의 저정밀과 P13의 LTO IR 포함 |

## 4. 첫 착수 순서와 병행 가능 작업

주 실행선은 P00 → P01 → P02 → P03이다. P04는 이후 함수/주소 공간 확장을 맡는다.
P05는 P00 뒤 독립적으로 설계할 수 있으며, P06 → P09로 **동기식 Runtime**을 먼저 연결한다.
P07 → P08로 비동기 의미를 구현한 뒤 Runtime에도 연결한다. warp 전체 구현을 Runtime의
불필요한 선행 조건으로 두지 않는다. 복합 커널은 P10 → P11 → P12 순서다.

AMD 조사 P14와 앱 의존성 조사 P18은 P00 뒤 병행 가능하다. 장비·원본 NVIDIA 대조가
불가능하면 조사 가능한 코드/명세 작업은 계속하되 해당 하드웨어 문턱은 통과시키지 않는다.
실제 병렬 에이전트 실행이나 장비 구매를 이 문서가 지시하지는 않는다.

## 5. 앱 선정과 실험 규칙

- P18의 첫 산출물은 `docs/compatibility/applications.json`의 고정 앱 목록이다.
  각 항목은 저장소/태그/커밋, 라이선스, 빌드/배포 artifact 해시, 의존 API/PTX/라이브러리,
  예상 정답과 필요한 장비를 포함한다. 앱/버전 선정 전에는 그 앱의 구현 작업을 착수하지 않는다.
- 첫 집합은 Driver 외부 모듈 소비자, 일반 Runtime 내장 모듈 소비자, 서로 다른 분야의
  공개 앱 등 최소3개 실행 경로를 포함한다. 준비한 공식 vectorAddDrv는 첫 경로의 기준이다.
- source build 시험과 원래 배포 실행 파일 시험을 구분한다. 재빌드가 필요하면 미수정
  실행 파일 호환성 문턱의 증거로 세지 않는다. 실행 파일뿐 아니라 GPU 코드/의존 파일도 고정한다.
- AI는 작은 일반 GEMM 소비자 → MLP → CNN/Transformer 추론 → 학습 순으로 확대한다.
  필요한 기능이 많으면 앱을 임의 수정하지 않고 최초 공통 실패 기능을 별도 작업으로 만든다.

## 6. 공통 검증과 PR 문턱

1. 변경 전에 새 동작의 실패 시험을 확인한다. 코드/헤더/호출 규약과 명세를 대조한다.
2. pure byte/IR 시험, invalid/unsupported/overflow/수명 시험을 먼저 통과시킨다.
3. GPU 입력은 NaN 초기 출력과64개 guard를 기본으로 하고, 형식에 맞는 독립 정답을 사용한다.
4. 원소 단위 정수는 정확 일치. 기존 유한 FP32 add/sub 입력은 정확 표현 가능한 값으로
   정확 일치시킨다. 누적·초월함수는 오류 예산을 실행 전에 시험 명세에 고정한다.
5. 고정 seed 변형 시험과 block 경계1/63/64/65/257/50000을 기본으로 하되 기능별 경계를 추가한다.
6. 원본 NVIDIA가 필요한 정확한 CUDA 의미는 CPU 식만으로 완료 처리하지 않는다.
   장비 미확보면 해당 사례는 skip이고, 독립 정답 검증 결과와 분리한다.
7. 관련 기능이 바뀐 경우 기존 native M1~M3e와 새 검사를 실행한다. 반복 실행은
   커널 정답용100회, 자원 생성/해제용1000회부터 시작한다. 횟수는 내구성 보장이 아니다.
8. OOM/실패/완료 불명확 상황은 fault injection으로 검증한다. 안전한 실패/자원 보존과
   정상 복구를 구분한다. untrusted GPU 코드의 메모리 안전을 이 계약으로 보장하지 않는다.
9. 순차 구현 후 전체 차이 리뷰. 소스·합성 시험·문서만 공개하고 staged/history/identity 검사.
10. 기존 정책대로 검토 가능한 기능 브랜치/초안 PR. main 병합은 별도 결정이다.

현재 재현 명령은 각 결과 문서를 따른다. `cargo test --workspace -- --include-ignored`는
GPU와 로컬 vendor parity fixture 준비 후 실행한다. 일반 CI는 ignored 시험을 pass로 세지 않는다.

## 7. 비동기·성능·운영에서 먼저 결정할 계약

- 현재 전역 mutex와 동기 immediate-list 경로를 그대로 비동기라고 부르지 않는다.
  P07에서 submission 자원, completion, 동기 free와 pending work의 관계를 설계한다.
  GPU 완료를 기다리는 동안 callback 재진입에 필요한 전역 잠금을 보유하지 않아야 한다.
- 완료 전 module/kernel/allocation/pinned staging의 실제 자원은 유지한다.
  event 재기록은 이전 대기자의 완료 대상을 바꾸지 않도록 generation을 구분한다.
- P09의 CT Runtime shim은 같은 프로세스의 **하나의 CT Driver 상태**를 호출한다.
  Rust crate를 각 DLL에 정적으로 포함해 서로 다른 context 목록을 만드는 구성을 피한다.
- static cudart의 코드가 실행 파일에 들어 있으면 CT Runtime DLL로 이름만 바꿔 해결할 수 없다.
  원래 static runtime의 Driver 요구를 충족하는 경로를 별도 검증하고, 실패하면 비지원으로 남긴다.
- 캐시가 생기면 입력·CT/IR 버전·옵션·GPU·드라이버/컴파일러·프로파일이 키에 포함된다.
- 성능은 warmup5회/측정30회부터 시작해 첫 번역·cache hit·전송·kernel·전체 중앙값과
  변동을 보고한다. 초기에는 속도 동등성 문턱을 만들지 않는다. 실사용 릴리스의 성능 목표는
  선정 앱/장비의 네이티브 기준 측정 후, 최적화 실험 전에 별도 프로파일로 고정한다.

## 8. 단계별 출시 판단

| 문턱 | 필요한 증거 | 남으면 차단되는 주장 |
| --- | --- | --- |
| Intel 일반 커널 | P00~04의 선택 프로파일, 실제 Arc·SPIR-V 검증 | 일반 명령/모듈 처리 완료 |
| Intel 앱 alpha | 필요한 P05~13/P18/P19; 미수정 앱·NVIDIA 대조·공존 | 기존 M3/v0.1 전체 완료 |
| 두 제조사 alpha | P14/P15와 동일 OS/ABI artifact의 공통 시험 | Intel·AMD 범용 실행 |
| 라이브러리/AI beta | 선택 P16/P17/P18의 고정 버전·수치/순서 시험 | 해당 AI 프레임워크/라이브러리 지원 |
| 실사용 릴리스 | 프로파일 필수 시험 전부, 패키징·장기 반복·진단·성능 보고 | 안정적 제품 배포 |
| 장기 기능 편입 | P20~25 기능별 별도 gate | 모든 cubin/최신 CUDA/모든 장치 지원 |

## 9. 위험과 재계획 조건

- AMD의 선택 OS/드라이버에 코드 로딩 경로가 없으면 P14가 대체 조합을 제안한다.
  다른 OS에서 새로 빌드한 성공은 동일 Windows 실행 파일의 성공으로 대체하지 않는다.
- 논리 warp, atomics 또는 수치 의미가 target 명령으로 보존되지 않으면 비용이 들더라도
  의미 보존 분해를 검토하고, 불가하면 해당 기능을 명시적으로 지원하지 않는다.
- 새 외부 앱이 PTX 없이 SASS만 제공하면 P24 의존으로 분류한다. 소스 재빌드 결과는 별도 경로다.
- LLVM/SPIR-V/벤더 도구·SDK 파일을 배포할 때 버전/라이선스/NOTICE 검토를 출시에 포함한다.
- 어느 단계든 기존 정확성이 깨지면 성능 개선보다 회귀 원인 수정이 우선이다.
- 전체 완료일/완료 비율은 추정하지 않는다. 상세 계획 단위의 실제 변경·실패·검증 시간을
  기록한 후 다음 묶음의 범위를 조정한다.

## 10. 공식 명세 확인

설계는 CUDA12.0.1의 [primary context](https://docs.nvidia.com/cuda/archive/12.0.1/cuda-driver-api/group__CUDA__PRIMARY__CTX.html),
[stream 규칙](https://docs.nvidia.com/cuda/archive/12.0.1/cuda-runtime-api/stream-sync-behavior.html),
[PTX ISA](https://docs.nvidia.com/cuda/archive/12.0.1/parallel-thread-execution/index.html)를 기준으로
필요 의미를 대조한다. 이 참조 버전 전체를 지원한다는 뜻은 아니다.
