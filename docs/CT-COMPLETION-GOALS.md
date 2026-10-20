# CT 범용 CUDA 번역기: 전체 목표와 완료 기준

작성: 2026-10-19. 기준 구현: M3e / `4b0c64f`.
후속 구현: [M3f](M3f-RESULTS.md)에서 P00 기능 추적과 P01의 제한된 복수 PTX 선택을 검증했다.
[M3g](M3g-RESULTS.md)는 P02의 제한된 여러 entry 모듈 실행을 검증했다.
아래 현재 위치 표는 M3e 시점의 기준 기록이며 최신 범위는 M3g 결과와 지원표를 따른다.
이 문서는 전체 제품의 목표 목록이다. 개별 기능의 상세 구현 계획은 아니다.
기존 M0~M6 명칭은 유지하고, 아래 G 번호는 구성요소별 추적에 사용한다.

후속 구체화: [26개 작업 묶음과 의존성](CT-EXECUTION-ROADMAP.md),
[첫 P00/P01 상세 계획](superpowers/plans/2026-10-19-m3f-selection.md),
[계획 검토 결과](CT-PLAN-REVIEW.md).

## 1. 최종 목표

같은 OS·호스트 아키텍처에서 기존 CUDA 프로그램의 실행 파일과 GPU 코드를
수정하지 않고, CT가 CUDA 호출과 GPU 코드의 의미를 구현하여 Intel·AMD GPU에서
실행한다. 사용자는 장치를 선택하고 실행하며, 프로그램별 커널 패치는 필요하지 않아야 한다.

범용성의 기준은 공통 명령·API 의미를 구현하는 것이다. 커널 이름·해시·모델명을
보고 준비한 정답이나 다른 커널로 대체하지 않는다. 공개 라이브러리 API를 대응
라이브러리에 연결하는 경우에도 그 API의 자료형·수치·실행 순서 계약을 검증한다.

CUDA는 버전별로 계속 확장되므로 '모든 CUDA'를 유한한 작업 하나로 완료했다고
표현하지 않는다. 릴리스마다 OS, 호스트 ABI, GPU/드라이버, CUDA API/ABI 버전,
입력 형식, PTX 명령과 라이브러리 버전을 고정한다. 그 범위의 지원/미지원/미검증을
공개하고, 새 버전과 기능은 다음 지원 범위로 확장한다.

제조사 드라이버·펌웨어 위의 사용자 공간 계층으로 개발한다. 새 디스플레이/커널
드라이버 개발은 필수 경로가 아니다. Windows x64와 Arc B390이 첫 기준 환경이며,
Linux 및 다른 하드웨어는 별도 검증한다. 서로 다른 OS의 실행 파일이 같다고 주장하지 않는다.

## 2. 현재 위치

| 구성요소 | M3e까지 확보한 것 | 아직 확보하지 못한 것 |
| --- | --- | --- |
| Intel 실행 기반 | Arc B390의 Level Zero 메모리·SPIR-V 실행 | 다른 Intel 모델/드라이버의 지원 보장 |
| CUDA 연결 | 제한된 Driver ABI 26개 export, 앱별 DLL 로딩, 버전별 함수 조회 | 전체 Driver API, 일반 앱 자동 호환 |
| PTX 번역 | 제한된 PTX7.0/sm_50·PTX8.0/sm_52 문법과 연산 | 각 PTX 버전 전체 의미, 여러 entry, 고급 병렬 기능 |
| fatbin | 측정된 형식의 압축/비압축 PTX 모듈 하나 | 복수 PTX 선택, 일반 내장 등록, 장치 코드 링킹 |
| 외부 코드 검증 | 원본 공식 샘플 소스를 빌드하고 조정한 모듈 생성 경로로 실행 | 배포된 일반 CUDA 앱/원래 nvcc 전체 빌드의 호환 보장 |
| 실행 의미 | 명시적 장치 할당, 동기 복사, 1차원 동기 커널 | 스트림·이벤트·비동기·shared/warp·primary context |
| AMD·AI | 아직 없음 | AMD 백엔드·CUDA 라이브러리·실제 AI 프레임워크 |

현재 증거는 [M3e 결과](M3e-RESULTS.md)와 각 [지원 표](compatibility/)를 따른다.
이 문서 작성 중 GPU 검사를 새로 실행한 것은 아니며, 기능 완료 비율은 산정하지 않는다.

## 3. 전체 구현 목표

### G0. 버전별 호환성 계약과 시험 목록 — 일부 있음, 계속 유지

- 지원 CUDA ABI/PTX/입력/OS/GPU 조합을 릴리스 프로파일로 정의한다.
- 선택한 NVIDIA 헤더·PTX 명세의 항목을 추출해 구현·시험·미지원 사유를 대응시킨다.
- export 존재와 동작 검증, 헤더 인식과 명령 지원, 장비 미확보와 성공을 분리한다.
- 장치 속성과 버전 조회가 실제 기능보다 높은 호환성을 광고하지 않도록 한다.

통과 기준: 선언한 지원 항목마다 시험 또는 명확한 검증 근거가 있고, 누락 항목도 조회 가능하다.

### G1. CUDA 프로그램과 모듈 로딩 — 일부 있음

- 실행 파일의 정적/동적 CUDA 의존성, ABI 버전과 로딩 방식 분석.
- 복수 아키텍처 fatbin에서 지원 가능한 PTX를 결정적으로 선택.
- 같은 모듈의 대체 이미지 선택과 서로 다른 모듈의 링킹을 구분.
- 여러 kernel entry, 모듈/함수 속성, global/constant 심볼 조회 및 초기화.
- 실행 파일·공유 라이브러리 내장 fatbin과 등록/해제 수명 처리.
- PTX 파일/메모리 로딩, JIT 옵션·진단, 관련 버전별 모듈 로딩 API.
- 중복/충돌/불완전 이미지와 자원 크기 제한 처리.

통과 기준: 같은 실행 파일/모듈을 보존한 채 여러 커널이 정확히 조회·실행되고,
이미지 순서 변경이나 지원 불가 이미지 혼재가 잘못된 모듈 선택으로 이어지지 않는다.

### G2. PTX 컴파일러의 일반화 — 제한된 기반 있음

- 모듈·함수·심볼·호출 규약을 담는 타입 있는 내부 표현 확장.
- 일반 device 함수 호출, 인자/반환값, 외부 함수 참조·재배치·링킹.
- 정수 8/16/32/64비트와 signed/unsigned, 비트 연산·shift·변환.
- FP16/BF16/FP32/FP64 등 대상별 수치 형식, 비교·변환·수학 연산.
- predication, 복잡한 분기/루프, 여러 함수/entry와 도달 가능한 제어 흐름.
- generic/global/local/shared/constant/parameter 주소 공간과 포인터 변환.
- 배열·벡터·정렬·구조체 인자, 실제 사용되는 global/constant 저장소.
- libdevice 등 device 수학 함수의 필요한 의미와 연결 경로.
- 명령의 modifier별 반올림·포화·FMA·NaN/Inf/부호 있는 0·denormal 처리.
- 공식 SPIR-V 검증과 백엔드 검증, 입력 위치를 보존한 미지원 진단.

통과 기준: 커널·레지스터·심볼 이름과 상수·입력 크기를 바꿔도 같은 의미를 보존하고,
지원 프로파일의 컴파일러 생성 코드가 독립 정답 및 NVIDIA 기준과 일치한다.

### G3. 병렬 실행과 메모리 모델 — 대부분 미구현

- 1D/2D/3D grid/block, 관련 특수 레지스터와 장치 제한.
- static/dynamic shared memory, block barrier와 부분 참여 규칙.
- atomic/reduction, 메모리 순서·scope·fence·가시성.
- warp vote/shuffle/ballot/active mask와 분기된 실행의 참여 규칙.
- NVIDIA 논리 warp와 Intel subgroup/AMD wave 차이를 보존하는 변환.
- 정합성이 검증된 협력 실행 경로와 자원 제한/실패 처리.

통과 기준: reduction/scan/histogram/타일 행렬곱 등 공유·동기화 커널을
다양한 block 크기와 분기 패턴에서 검증한다. 단순 subgroup 이름 치환으로 통과시키지 않는다.

### G4. CUDA Driver API와 컨텍스트 — 일부 있음

- primary context 유지/해제/reset과 Driver·Runtime 간 공유.
- 스레드별 current context, 여러 context와 장치별 자원 소유권.
- 필요한 장치/함수 속성, 버전별 진입점·구조체·호출 규약 확장.
- 모듈/메모리/실행 API, 오류 우선순위와 지연 오류 전달.
- 호스트 여러 스레드에서의 동시 호출과 안전한 생성/종료 수명.

통과 기준: 독립 CUDA 헤더로 만든 소비자가 올바른 서명으로 동작하고,
Driver/Runtime 혼용·스레드 이동·중복 해제·잘못된 소유권의 동작이 계약과 일치한다.

### G5. 메모리 관리와 전송 — 기본 동기 경로 있음

- device-to-device, 2D/3D/pitched 복사, memset 계열.
- pinned host allocation/registration, mapped host memory와 주소 조회.
- 비동기 복사의 버퍼 수명·완료 보장, 할당 실패와 overflow 처리.
- CUDA array, texture/surface 객체와 관련 접근 의미.
- virtual address 관리와 포인터 속성; 필요 범위의 메모리 풀/비동기 할당.
- Unified Memory의 기능별 계약: 공유 가상주소와 자동 migration을 같은 것으로 취급하지 않는다.

통과 기준: 비정렬·경계·크기 0·큰 전송·재사용·해제 경쟁을 검사하고,
지원할 수 없는 메모리 기능은 잘못된 성공 대신 명시적으로 실패한다.

### G6. 스트림·이벤트·비동기 실행 — 미구현

- stream 생성/해제/조회/동기화, default stream과 per-thread default stream.
- event 기록/대기/조회/시간 측정, stream 간 의존성.
- 복사와 커널의 실행 순서, 동시 실행, 비동기 오류의 전달 시점.
- callback/host function의 실행 규칙, 완료 전 자원 해제 방지.

통과 기준: 여러 stream의 데이터 의존성 시험에서 완료 순서가 보장되고,
비동기 API를 단순 동기화로 바꾼 경로는 그 제약과 성능을 명시한다.

### G7. CUDA Runtime와 일반 nvcc 프로그램 — 미구현

- cudaMalloc/cudaMemcpy/cudaLaunchKernel 등 Runtime API의 필요한 집합.
- 정적/동적 cudart의 연결 경로를 각각 설계하고 시험.
- fatbin·함수·전역 변수 등록, 초기화/해제 순서와 DLL 수명.
- cudaGetLastError/cudaPeekAtLastError 등 Runtime 오류 상태.
- primary context, device 선택/reset, stream/event와 Driver API 상호운용.
- 선택한 컴파일러 버전별 등록 ABI 차이와 내부 심볼 의존성 관리.

통과 기준: 외부 PTX를 읽는 특수 호스트뿐 아니라 일반 nvcc 프로그램을
지원 범위 안에서 실행한다. 빌드한 대조군 시험 후, 별도 기존 실행 파일을 변경 없이 시험한다.

### G8. 실행 중 컴파일과 장치 코드 링킹 — 미구현

- NVRTC로 실행 중 커널을 만드는 앱의 호출/결과 연결.
- NVIDIA 라이브러리 의존을 재사용할지, CT 호환 API/다른 컴파일러로 대체할지 경로 선정.
- cuLink 계열, nvJitLink 및 relocatable device code 중 목표 앱에 필요한 집합.
- 외부 device 함수, libdevice 참조와 링크 오류 진단.
- LTO IR 등 PTX 외 입력은 명세·도구·배포 조건과 실현성을 별도로 평가.

통과 기준: 실행 시 생성하거나 여러 단위로 나눈 GPU 코드가 CT에서 연결·실행된다.
기존 NVIDIA 도구를 쓴 시험과 CT 자체 제공 기능을 구분한다.

### G9. Intel·AMD 백엔드와 장치 확장 — Intel 한 모델만 검증

- 공통 실행 의미와 벤더별 코드 생성/자원 관리 경계를 정리.
- Intel 경로의 추가 장비·드라이버, 컴파일러 제한과 기능 질의 검증.
- AMD 실장비·OS·드라이버·컴파일러/런타임 조합 선정 및 네이티브 실행.
- CT 내부 표현에서 AMD 대상 코드를 생성하고 메모리·모듈·launch 연결.
- 동일 OS/호스트 ABI의 같은 앱·GPU 코드로 Intel/AMD 공통 시험 실행.
- 장치 선택, 실제 기능 기반 지원 판정과 백엔드 오류의 공통 변환.

통과 기준: 실제 Intel·AMD 장치가 공통 프로파일 시험을 통과한다.
한 모델의 결과를 모든 제품으로 일반화하지 않는다. 장비 부재는 미검증이다.

### G10. CUDA 라이브러리 호환 — 미구현

- cuBLAS/cuBLASLt: GEMM부터 전치·stride·batch·pointer mode·정밀도·stream 확장.
- cuRAND/cuFFT/cuSPARSE/cuSOLVER: 목표 앱에 필요한 연산·자료형·오류 동작부터 확대.
- cuDNN: convolution·activation·normalization·attention 등 선택한 앱의 의존 범위.
- 대응 Intel/AMD 라이브러리 또는 자체 일반 연산 구현과 연결.
- handle/descriptor·workspace·알고리즘 선택·동기화·수치 허용오차 검증.
- Thrust/CUB처럼 코드로 생성되는 기능은 별도 라이브러리 DLL 구현만으로
  해결되지 않으므로 G2/G3의 실제 생성 커널로 시험.

통과 기준: 선택한 라이브러리 API의 의미와 오류 시험을 통과하고,
그 API를 이용하는 변경 없는 외부 앱이 실행된다. GEMM 하나를 전체 AI 호환이라 부르지 않는다.

### G11. 실제 프로그램·AI 생태계 — 공식 소형 샘플만 검증

- 공식 샘플의 기본 연산 → 영상/수치 계산 등 서로 다른 외부 앱 → AI 순으로 확대.
- 외부 앱의 최초 실패 지점을 분석해 공통 기능으로 수정; 앱별 커널 치환 금지.
- 작은 MLP/CNN/Transformer 추론, 이후 학습과 optimizer까지 별도 목표로 검증.
- PyTorch CUDA 패키지 등의 정확한 배포 버전·의존성·GPU 기능 조회 경로 분석.
- JIT/custom extension/Triton 등 앱이 실제로 사용하는 생성 경로를 각각 연결.
- TensorRT 같은 별도 런타임은 독립 호환 과제로 평가.

통과 기준: 사전에 고정한 서로 다른 기존 앱에서 정확성·반복 실행·메모리 안정성을
검증하고, 앱/버전별 지원 조건을 공개한다. 성공 앱 목록과 엔진 자체 지원 범위를 함께 제공한다.

### G12. 진단·패키징·운영 안정성 — 일부 있음

- ct doctor/inspect/run: 환경, 입력 형식, 의존성, 필요한 기능과 실패 위치 제공.
- 자동 진단은 정적 분석 결과와 실제 실행 성공을 구분.
- 프로세스별 설치/제거, NVIDIA와 공존, 시스템 드라이버를 덮어쓰지 않는 배포.
- 버전 고정·업그레이드·호환성 회귀, crash/device loss/timeout/OOM 처리.
- 신뢰 경계를 명시하고, 비신뢰 코드는 필요 시 별도 프로세스로 격리.
- 공개 라이선스/NOTICE/의존성 목록 및 배포물 검토.
- .gitignore, 공개 내용/히스토리/신원 검사; 로그·캐시의 개인정보 제거.

통과 기준: 사용자 PC에서 재현 가능한 설치/실행/제거가 가능하고,
오류 진단에 충분한 기술 정보가 있으면서 개인 경로·토큰·원본 로그는 유출하지 않는다.

### G13. 정확성·성능·출시 검증 — 초기 시험 있음, 계속 확대

- 명령/API/복합 커널/앱으로 이어지는 자동화된 회귀 시험.
- 독립 CPU 정답과 원본 NVIDIA 실행의 차등 검사, Intel/AMD 교차 검사.
- 수치·경계·동시성·메모리 수명·무작위/변형 입력·장시간 시험.
- 입력 parser/decompressor fuzzing, fault injection과 누수/오류 복구 시험.
- 첫 번역/캐시 hit/전송/커널/앱 전체 시간을 분리 측정.
- 올바른 캐시 키, 무효화, 손상/다른 장치 캐시의 재사용 방지.
- 같은 GPU의 네이티브 기준과 CT 오버헤드를 비교하고 최적화 전후 정확성 재검사.
- 공개 CI와 검토한 코드만 실행하는 GPU 검증 경로 분리.

통과 기준: 릴리스 프로파일의 필수 시험이 실제 지정 장비에서 통과하고,
재현 명령·CT 커밋·환경·입력 해시와 실패/미검증 목록이 함께 남는다.

### G14. 완전 범용성에 가까워지기 위한 장기 확장 — 미착수

- PTX가 없는 SASS/cubin 전용 프로그램: 명령 해석/변환·재배치·ABI·메모리 의미를
  다루는 별도 엔진 연구. PTX 추출만으로 해결할 수 없으며 지원 가능 범위를 먼저 실험.
- Tensor Core/MMA 및 저정밀 연산: 다른 장치의 행렬 연산 또는 의미 보존 분해,
  수치와 속도를 각각 검증.
- CUDA Graphs/capture, cooperative groups/launch, 동적 병렬 실행, cluster,
  고급 비동기 장치 명령 등 세대별 실행 기능.
- multi-GPU, peer access, IPC·external memory/semaphore, NCCL·분산 실행.
- graphics/video interop, profiling/debugging/CUPTI, 관리 API/NVML 등 앱의 주변 의존성.
- Linux ABI/로더와 장비별 지원 확대; 추가 호스트 아키텍처는 별도 프로파일.

통과 기준: 각 기능을 독립 하위 프로젝트로 정의하고 의미·실현성·성능·배포 조건을
검증한 후 지원 표에 편입한다. 초기 릴리스에서 제외해도 장기 요구 목록에서 삭제하지 않는다.

## 4. 개발 순서와 릴리스 문턱

| 단계 | 선행 조건과 주요 작업 | 단계 통과 시 말할 수 있는 것 |
| --- | --- | --- |
| A. 일반 커널 번역 기반 | G0/G1/G2 확대: 복수 이미지, 여러 entry, ABI/주소 공간, 연산, 다차원 실행 | 제한 프로파일의 여러 CUDA 커널을 일반적으로 번역 |
| B. 일반 CUDA 실행 | G3~G7: primary context, 메모리, stream/event, shared/barrier/atomic/warp, Runtime 등록 | 지정한 일반 nvcc/Driver 앱 집합의 Intel 실행 |
| C. 두 제조사 검증 | G9, 공통 의미가 안정되는 시점부터 병행; AMD 실장비 필수 | 같은 OS/ABI의 동일 앱을 Intel·AMD에서 실행 |
| D. 생태계 연결 | G8/G10/G11: JIT·링킹·라이브러리·외부 앱 | 고정한 라이브러리/AI 앱 프로파일 실행 |
| E. 제품 출시 | G12/G13은 처음부터 병행; 설치·공존·장기 안정성·성능 문턱 충족 | 지원 범위와 제한이 공개된 실사용 CT 릴리스 |
| F. 장기 확장 | G14를 기능별 추진; 최신 CUDA는 프로파일을 추가해 확장 | SASS 전용·고급 실행·멀티 GPU 등 지원 범위 확대 |

이 표는 기존 M3 Intel alpha와 M4 dual-vendor alpha의 통과 선언이 아니다.
각 마일스톤의 NVIDIA 대조·공존·미수정 앱 등의 미검증 조건은 그대로 남는다.
모든 단계를 완전 직렬로 진행하지 않는다. 검증/진단/개인정보 보호는 상시 작업이며,
AMD 네이티브 실험은 장비를 확보하면 Intel 확장과 병행할 수 있다.

## 5. 바로 다음 구현 묶음

1. G0: 현재 프로파일/시험 목록과 기능 요청의 추적표를 고정.
2. G1: 복수 PTX 선택 정책 — 버전 숫자만 보지 않고 의미 지원·모듈 식별·ABI·오류 규칙 정의.
3. G1/G2: 여러 kernel entry와 함수별 인자 ABI, 공통 global 심볼 수명.
4. G2/G3: 2D/3D 실행과 필요한 기본 변환/정수/비트 연산 확대.
5. G4/G7: primary context와 Driver/Runtime의 공통 상태를 구현.
6. G5/G7: device 복사·pinned 메모리와 내장 등록을 바탕으로 동기식 Runtime부터 연결.
7. G6: 비동기 자원 수명 기반 → stream/event → Runtime 비동기 확장.
8. G3: shared memory/barrier → atomic → warp 순으로 일반 병렬 알고리즘 검증.

각 묶음은 필요한 실패 시험 → 공통 의미 구현 → GPU 정답/경계 검사 →
독립 리뷰 → 지원 표 갱신으로 마친다. 상세 작업량은 각 설계와 첫 실패 분석 후 산정한다.

## 6. 완료 선언에 필요한 증거

- 선택한 릴리스 범위의 API·명령·입력 조합에 추적되지 않은 빈칸이 없다.
- 여러 기존 프로그램을 앱별 커널 패치 없이 실행한다.
- 같은 OS/ABI의 동일 실행 파일과 GPU 코드가 Intel·AMD 실장비에서 통과한다.
- NVIDIA 기준 및 독립 정답과 비교하고 수치 예외·실행 순서·수명도 검증한다.
- 미지원 입력은 명시적으로 실패하며 CPU 대체 실행을 GPU 성공으로 세지 않는다.
- 설치·제거·NVIDIA 공존·반복 실행·문제 진단과 개인정보 보호가 검증된다.
- 성능은 실측 수치로 공개하고, 다른 GPU와의 성능 동등성을 추정으로 보장하지 않는다.

## 7. 명세 근거

2026-10-19 공식 문서 확인. 문서의 최신 버전을 CT 지원 버전으로 선언한 것은 아니다.
위 항목은 그 문서의 기능 분류와 현재 CT의 공백을 바탕으로 정리한 개발 목표다.

- [CUDA Driver API 목록](https://docs.nvidia.com/cuda/cuda-driver-api/cuda_driver_api/apis.html)
- [CUDA Runtime API 목록](https://docs.nvidia.com/cuda/cuda-runtime-api/cuda_runtime_api/apis.html)
- [PTX ISA: 타입·메모리·명령·병렬 의미](https://docs.nvidia.com/cuda/parallel-thread-execution/)
- [nvcc: PTX/CUBIN/fatbin·분리 컴파일과 링킹](https://docs.nvidia.com/cuda/cuda-compiler-driver-nvcc/index.html)
