# P09a1: 첫 동기 CUDA Runtime 연결 설계

상태: 구현 전 검토용 설계. 2026-10-21.
기준: `4c60225d027be1c8b5d969096fe2bef877f72a70` / Driver38개 export.
이번 문서는 Runtime 구현·ABI 통과·GPU 실행·일반 nvcc 호환성의 증거가 아니다.
사용자 목적은 기존 CUDA 앱을 Intel/AMD GPU에 연결하는 범용 계층이다.
첫 메모리 소비자는 그 목표의 중간 단계이며, 커널 등록·Runtime 전체를 대신하지 않는다.

## 1. 선택과 범위

추천은 CT 소유 `ct-cudart` DLL을 만들고, 프로세스에 있는 단일 CT Driver
`nvcuda.dll`의 C ABI를 호출하는 방식이다. 첫 P09a1은 아래14개 공개 Runtime
함수의 제한된 메모리·장치·오류 경로를 연다. 이후 P09a2가 compiler host stub,
내장 fatbin, 함수 등록·launch를 담당한다. P09b 정적 cudart 경로는 별도다.

검토한 대안:

| 접근 | 장점 | 선택하지 않은 이유/제약 |
| --- | --- | --- |
| 별도 CT Runtime → 단일 Driver ABI | Driver/Runtime 자원·TLS 공유, 역할 분리 | 새 로더·참조·오류 정책과 검증 필요; 추천 |
| 원본 NVIDIA cudart → CT Driver 확장 | 원본 Runtime 자체의 의미 활용 가능 | 실제 원본 Runtime 요구 API와 초기화 진단이 필요. 버전을 높게 위장해 우회하지 않음; 별도 탐색 보존 |
| 같은 Rust Driver 코드를 두 DLL에 포함 | 초기 코드 공유가 쉬움 | 각 DLL에 별도 OnceLock/TLS가 생겨 같은 CUcontext를 공유하지 못함; 금지 |

별도 DLL 안에 `ct-cuda` rlib를 정적으로 링크하지 않는다. API 이름·함수 포인터
선언만 공유할 수 있다. 지원 대상은 Windows x64, app-local `cudart64_12.dll`과
`nvcuda.dll`, eager/serialized completion이다. CUDA12 전체 구현이나 버전 지원을
뜻하지 않는다. AMD/NVIDIA 실행은 장비가 없어 미검증이다.

## 2. 로딩과 빌드 경계

`ct-cudart`는 Rust cdylib이며 Win32 동적 호출로 Driver 함수 표를 구성한다.
경로는 Runtime DLL 자신의 디렉터리에서 절대 경로로 만든 `nvcuda.dll` 하나다.
CWD/PATH 검색이나 시스템 드라이버 덮어쓰기를 하지 않는다. 필수 함수가 하나라도
없으면 함수 표 전체를 공개하지 않고 초기화를 실패시킨다.

이미 다른 위치의 `nvcuda.dll`이 로드돼 있으면 해당 모듈과 새 복사본의 상태를
섞지 않고 `cudaErrorInsufficientDriver=35`로 거부한다. 이미 로드된 동일 모듈이면
같은 HMODULE을 사용한다. 주소·정규화 경로/파일 동일성 검사는 핸들 재사용과 경로
별칭을 고려하며, 단순 문자열 prefix나 파일명만으로 일치 처리하지 않는다.
프로세스의 다른 구성요소가 나중에 별도 Driver를 로드하는 공존은 보장하지 않는다.

첫 stateful 초기화에서 Runtime과 Driver 모듈을 process lifetime 동안 pin한다.
여기서 초기화는 Count/Get을 포함해 Driver 함수 표를 최초로 실제 로드하는 경로를
뜻한다. identity와 필수 함수 확인 뒤, 함수 표 게시 또는 Driver 함수 호출 전에 pin한다.
그 전에도 LoadLibraryEx로 소유한 module reference를 유지하고, unowned HMODULE의
수명이 계속 유효하다고 가정하지 않는다. bootstrap 실패는 고정된 실패 상태로 보존하며
같은 Runtime instance에서 자동 DLL 재검색·재초기화를 반복하지 않는다.
이를 일반 API 실행 중 수행하고 DllMain에서 GPU/Driver 초기화·정리를 하지 않는다.
실행 중 DLL unload/reload를 지원한다고 주장하지 않는다. 오류 문자열/last-error
같은 순수 함수는 Driver/GPU 초기화를 요구하지 않는다.
호출자가 다른 DLL의 DllMain/loader-lock 아래 정적 초기화에서 stateful Runtime
함수를 호출하는 경로도 P09a1에서 지원하지 않는다. 호출자는 loader lock이 없는 시점에
이 함수들을 호출해야 한다. 자동 lock 감지·회피·안전한 재진입을 약속하지 않는다.
순수 오류 helper의 Driver-free 성질을 stateful 초기화의 loader-lock 안전성으로 확대하지 않는다.
참고: [Windows module pin](https://learn.microsoft.com/en-us/windows/win32/api/libloaderapi/nf-libloaderapi-getmodulehandleexw),
[DllMain 제약](https://learn.microsoft.com/en-us/windows/win32/dlls/dynamic-link-library-best-practices).

기존 사용자 Cargo/README/LICENSE11개 파일은 저장된 해시를 보존한다. 첫 Runtime은
`crates/ct-cudart/`에 독립 `[workspace]`와 lock을 두고 root workspace에 아직 편입하지
않는 방식으로 설계한다. root Cargo나 사용자 라이선스 변경을 함께 커밋하지 않는다.
새 crate는 외부 dependency와 publish 없이 시작한다. validation runner가 이 manifest의
fmt/clippy/test/build를 명시적으로 실행해야 하며, root cargo 검사만으로 통과를 선언하지
않는다. 소스 fingerprint는 기존 `crates/` 범위에 새 crate와 nested lock을 포함한다.

컴포넌트는 bridge(Win32 로딩·identity·함수 표), state(primary 캐시·초기화 상태),
errors(변환 표·TLS), device(장치 API), memory(전송·할당 정책), exports(ABI 진입과
panic containment)로 나눈다. coverage/tool lock은 기존v1 schema를 유지하며 별도
Runtime ABI manifest를 추가한다. 기존 Driver export manifest에 cuda 함수를 섞지 않는다.

## 3. 장치 선택과 단일 자원 상태

Runtime이 별도 allocation/context registry를 복제하지 않는다. 할당·모듈·primary 상태와
오류 격리는 Driver가 소유한다. Runtime은 Driver 함수 표, 장치별 Runtime retain,
초기화 동기화와 Runtime last-error만 소유한다.

* `cudaSetDevice(d)`: CUDA12 규칙대로 유효한 d의 primary를 즉시 확보하고
  `cuCtxSetCurrent`로 현재로 만든다. 실패 시 이전 current/선택 상태를 유지한다.
* context가 필요한 다른 호출: 현재 Driver 문맥이 유효하면 그대로 쓴다. 일반 문맥도
  덮어쓰지 않는다. current가 없을 때만 해당 스레드의 기본 장치0 primary를 확보한다.
* Runtime의 primary retain은 장치별 한 번이다. 호출/스레드별 반복 retain은 금지한다.
  캐시 생성은 mutex로 직렬화하고, publish 전 실패한 retain은 release로 rollback한다.
  rollback 실패는 그 자원을 보존하고 오류를 반환하며 정상 캐시로 재활용하지 않는다.
  rollback release가 실패하면 해당 장치의 primary 획득 캐시는 sticky Failed(999)가 된다.
  원 호출도999를 반환하고, 이후 SetDevice/자동 primary 획득은 재retain·재release 없이
  같은999를 반환한다. 새 primary나 격리한 핸들을 선택하지 않는다. 이미 유효한 일반
  Driver 문맥을 쓰는 호출까지 장치 전체 고장으로 표시하지 않는다. 회복은 프로세스 재시작
  또는 후속 수명 설계의 범위다. rollback 성공 시에만 원래 오류를 반환하고 미게시 상태를 유지한다.
* Driver가 current 문맥을 다른 장치로 변경하면 `cudaGetDevice`는 그 문맥의 장치를
  반영한다. current가 없을 때의 기본 선택은0이며 조회만으로 primary를 만들지 않는다.
* 초기 primary 참조는 프로세스 수명 동안 유지한다. DllMain/TLS destructor에서
  release/reset/free를 실행하지 않는다. 이 수명 정책과 pin은 명시적인 첫 profile 제한이다.
* Runtime의 `cudaDeviceReset`은 첫 export 집합에서 제외한다. Driver reset/final release로
  Runtime 캐시 또는 TLS가 stale이 되면709를 전달하고 자동 회복하지 않는다. reset 뒤
  자동 재초기화는 다음 수명 설계의 요구로 남기며, 이번에 성공으로 위장하지 않는다.

Driver 사용자가 destroy/reset/free와 다른 스레드의 사용을 안전하게 조정해야 한다.
Runtime 초기화 잠금과 Driver 잠금의 순서는 Runtime → Driver이며 Driver가 Runtime으로
재진입하지 않는다. 대기 중 callback/async 재진입은 첫 profile 밖이다.
공식 근거: [Runtime/Driver 상호작용](https://docs.nvidia.com/cuda/archive/12.0.1/cuda-runtime-api/group__CUDART__DRIVER.html).

## 4. 첫14개 공개 ABI와 동작

모든 함수는 Windows `CUDARTAPI` / Rust `extern "system"`이다. cudaError_t는
32-bit enum 표현, 포인터/size_t는64-bit다. CT 선언 TU와 공식 헤더 TU를 별도로
컴파일해 함수 표현·상수·출력 크기를 비교한 뒤 실제 공식 헤더 호출을 수행한다.

| 함수 / 인자 | 첫 profile |
| --- | --- |
| cudaGetDeviceCount(int*) | Driver 초기화와 실제 장치 수; primary 생성 없음 |
| cudaGetDevice(int*) | 유효 current 장치, current 없으면0; primary 생성 없음 |
| cudaSetDevice(int) | 유효 장치 primary 즉시 초기화·선택 |
| cudaDeviceSynchronize(void) | 현재 문맥 또는 기본 primary의 동기 완료 |
| cudaMalloc(void**,size_t) | 양수 크기, Driver allocation; 실패 출력은null |
| cudaFree(void*) | 유효 exact-base; NULL은 문맥 준비 후 free 명령 없는 성공 |
| cudaMemcpy(void*,const void*,size_t,cudaMemcpyKind) | 명시적 H2H/H2D/D2H/D2D만 |
| cudaMemset(void*,int,size_t) | 하위8-bit를 반복하는 byte fill |
| cudaGetLastError(void) | 스레드·Runtime instance의 오류 반환 후0으로 clear |
| cudaPeekAtLastError(void) | 같은 오류 반환, clear하지 않음 |
| cudaGetErrorName(cudaError_t) | static NUL 문자열; Driver/GPU 초기화 없음 |
| cudaGetErrorString(cudaError_t) | static NUL 설명; Driver/GPU 초기화 없음 |
| cudaDriverGetVersion(int*) | 출력0과801; 높은 버전을 만들어 반환하지 않음 |
| cudaRuntimeGetVersion(int*) | 출력0과801; DLL 이름은 ABI 대상이지 전체 지원 버전 아님 |

`cudaMalloc(size=0)`은 이번 profile 밖으로801과null을 반환한다. 공식 헤더의 설명만으로
정하지 못한 실제 NVIDIA zero 동작은 후속 대조 항목이다. NULL output은1이며 쓰지 않는다.
버전 출력의 NULL도1이다. count/device 출력은 유효한 storage를0으로 초기화한 뒤 처리한다.

cudaMemcpy kind0=H2H,1=H2D,2=D2H,3=D2D. kind4=Default는 UVA 미지원으로801,
그 밖의 enum은cudaErrorInvalidMemcpyDirection=21이다. 유효 kind의0-byte copy는
포인터 접근 없이 성공한다. 이 무작업은 primary를 만들지 않는다. 양수 H2H는 유효한
host extent·비중첩이 필요하며 CPU 복사를 명시한다. Device가 포함된 양수 copy는
현재 문맥의 Driver 범위 검사를 사용한다. 잘못된 kind를 추정·수정하지 않는다.
cudaMemset의0-byte 요청도 포인터 접근/primary 생성 없는 성공으로 정의한다.
이 zero 정책은 CT profile 규칙이며 NVIDIA 오류 순서·초기화 타이밍의 동등성은 미검증이다.

양수 D2D overlap, interior free, foreign/stale pointer, 범위·정렬·overflow는 기존
Driver의 제한을 유지한다. raw address의 재사용으로 새 allocation이 식별될 수 있다.
지원 함수도 미구현 CUDA 기능을 성공 처리하지 않는다. async export, stream/PTDS,
속성 구조체, peer/managed/pinned/2D/3D, launch와 등록 함수는 이 export 집합 밖이다.

## 5. 오류 변환과 last-error

Driver 코드를 Runtime 숫자로 그대로 cast하지 않는다. 명시적 표를 검증한다:

| Driver/adapter 결과 | Runtime 결과 |
| --- | --- |
| 0 / 1 / 2 | cudaSuccess0 / InvalidValue1 / MemoryAllocation2 |
| Driver3 | InitializationError3 |
| Driver100 / 101 | NoDevice100 / InvalidDevice101 |
| Driver201 | IncompatibleDriverContext49 |
| Driver709 / 801 | ContextIsDestroyed709 / NotSupported801 |
| Driver218 / 400 / 500 등 첫14개 경로에 맞지 않는 오류 | Unknown999 |
| Driver999 / 예상 밖 코드 / Rust panic·잠금 실패 | Unknown999 |
| Driver DLL 누락·다른 Driver 모듈·필수 export 누락 | InsufficientDriver35 |

1/2/3 등의 이름·값은 고정 driver_types.h와 확인한다. Native 원인의 더 세밀한 분류는
별도 검증 없이 약속하지 않는다. 작업 API의 nonzero 결과가 TLS last-error를 갱신하고,
성공은 이전 오류를 지우지 않는다. Peek/Get/문자열 함수는 새로운 오류를 기록하지 않으며,
Get만 clear한다. 서로 다른 스레드·Runtime instance 사이에서 오류를 공유하지 않는다.
ErrorName/String의 미등록 코드에는 `unrecognized error code`를 반환한다.
고정된 지원 enum 이름과 설명만 반환하고 raw native 로그/호스트 경로를 노출하지 않는다.
계획 구체화 시 초기화 오류의 모호함을 정리했다: 현재 Driver가 native 원인을999로
반환하면 Runtime도999를 유지한다. 원인 분류 없이 모든 초기화 실패를3으로 바꾸지 않는다.
Driver init의 첫 결과는 Runtime instance에서 고정하고 자동 재시도하지 않는다.
근거: [Runtime 오류](https://docs.nvidia.com/cuda/archive/12.0.1/cuda-runtime-api/group__CUDART__ERROR.html).

## 6. 로더·검증 경계

현재 `ct.py`는 모든 cudart import를 거부한다. 구현 시 명시적 Runtime 선택 옵션을 추가하고,
정확히 cudart64_12.dll과 허용14개 named import만 승인한다. 기본 Driver-only 동작은
유지한다. 등록 함수/다른 cudart 버전/ordinal/지연 로딩이 발견되면 미지원 사유로 거부한다.
Runtime 파일을 기존 PTX asset 인자에 섞지 않고 독립 인자로 받는다. 입력 EXE/DLL 바이트,
import 대상, hash와 번들 복사를 검사하며 시스템에 설치하지 않는다.

승격에 필요한 관찰:

1. 공식 헤더 ABI14개와 Runtime/Driver enum 차이, 상수·typed-output sentinels.
2. 공식 Runtime 헤더 C/C++ 앱의 실제 cudart64_12.dll import + CT import library;
   실행 파일 수정 없이 bundle에서 실행. 이 앱은 CT 소유 fixture라고 표시한다.
3. Runtime 할당 → Driver read/fill/free와 Driver 일반 문맥 할당 → Runtime copy/free.
   두 소비자의 Driver HMODULE 동일성 및 일반 문맥이 primary로 바뀌지 않는지 검사.
4. primary 상태를 전/후 조회해 Count/Get은 비활성, SetDevice는 즉시 활성임을 확인.
   반복/2-thread 호출 후 Runtime 자체 retain이 장치당 하나인지 확인한다. 참조가 남아
   있는지 단순히 active=true만 보는 것으로 retain 누수 검증을 대신하지 않는다.
   CPU provider의 정확한 retain 횟수와 별도 native child의 말미 probe를 함께 사용한다.
   외부 소비자의 retain 몫을 release한 뒤 Runtime 몫으로 예상한 한 번만 추가 release해
   inactive가 되는지 확인하고 child를 종료한다. 이 파괴적 관찰 뒤 Runtime 재사용 성공은
   요구하지 않으며, 일반 API가 참조를 임의 해제해도 된다는 의미로 확대하지 않는다.
5. 비정렬 길이·guard·입력 보존, H2H 경로 명시, zero/NULL/kind/overflow 오류,
   success 후 last-error 유지·Peek/Get·2-thread 격리·noGPU 순수 오류 함수.
6. missing/wrong-location Driver, missing-symbol fake provider, 실패한 retain/SetCurrent의
   rollback, cache publish 실패를 CPU fault injection으로 검증. rollback release 실패 뒤
   추가 호출에도 retain/release 횟수가 늘지 않는 sticky999를 검사한다. loader-lock 호출은
   미지원 호출자 전제이며, CT DllMain의 무작업은 source/fixture 검사로 확인한다.
7. 알려진 Driver/Runtime 혼용에서 stale/reset은709로 실패하고 자동 성공하지 않는지 검사.
8. 두 DLL hash·실제 import·Runtime test catalog/tool lock·original bundle audit,
   기존32개 required combined case와 실제 Arc 전체 회귀.

현재32/32 결과는 [기존 메타데이터 결과](../../P06a-QUERY-RESULTS.md)의 역사적 증거다.
이 설계에서 새로 실행한 Runtime 시험 수는0이다. CPU fake만으로 GPU 성공을 주장하지 않는다.
아직 runtime crate가 없으므로 새 필수 case 수는 구현 계획에서 정하고, 기존32개를 삭제하지 않는다.

## 7. producer와 등록·launch 후속 단계

현재 로컬에는 MSVC와 공식 Runtime 헤더가 있지만 nvcc 호스트 컴파일러의 실행 경로는 없다.
nvcc 이름의 보존된 wheel은 ptxas/NVVM 보조 구성요소이며 nvcc.exe를 포함하지 않는다.
기존 NVRTC PTX corpus는 host stub/실행 파일 생성 증거가 아니다.

P09a2는 실제 고정 nvcc로 `--cudart=shared` 호스트와 생성 stub/PE import를 관찰한 뒤
아래 요구를 구현해야 한다. tool 확보가 막히면 진단·설계는 진행할 수 있지만 그 경로를
완료로 표시하지 않는다. 수동 작성 host stub 성공도 nvcc 호환성으로 세지 않는다.

* raw fatbin과 구별되는 wrapper magic0x466243B1/version/layout·bounds.
* RegisterFatBinary/End/Unregister 토큰 수명과 constructor/atexit, 중복·실패·unload.
* RegisterFunction의 host 함수 identity ↔ module/device symbol 매핑과 다중 module.
* Push/Pop call configuration의 TLS·dim3 ABI, cudaLaunchKernel 인자·stream 검사.
* 등록은 native loader lock에서 GPU 작업을 하지 않도록 구분하고, 첫 실제 사용에서
  module translation을 수행. global/RDC/device-function 입력은 필요한 P03/P04와 연결.
* 실제 compiler가 생성한 PTX에서 처음 실패한 문법·타입을 원형대로 보존해 회귀 corpus에 추가.

원본 NVIDIA dynamic cudart 경로와 static cudart P09b의 Driver 요구 조사도 유지한다.
P09a1 메모리 앱 통과를 일반 커널/프레임워크/AI 라이브러리 지원으로 바꾸지 않는다.

## 8. provenance와 구현 진입 조건

공식 Runtime 선언의 package는 nvidia-cuda-runtime-cu12 12.0.107, compiler 보조 선언은
nvidia-cuda-nvcc-cu12 12.0.76이다. [로컬 의존성 감사](../../P09a-DEPENDENCY-AUDIT.md)에
선택 파일의 package 대응·hash를 기록했다. 이는 선택 파일 출처 검증이며 전체 전처리
의존성/Runtime ABI 시험 통과가 아니다. 구현 때 실제 전처리 include closure를 원본
패키지별로 pin하고 tool lock에 반영한다. raw vendor 파일과 절대 경로 로그는 공개하지 않는다.

설계 독립 검토 → 사용자 설계 검토 → 상세 실행 계획 → RED/구현/독립 검토 →
clean Arc required lane 순서로 진행한다. 이번 문서의 단계 목록은 승격 기준이며,
아직 존재하지 않는 Runtime 구현이나 상세 실행 계획의 승인으로 간주하지 않는다.
새 Runtime 하위 시스템의 설계가 확정되기 전 제품 코드·dependency를 추가하지 않는다.
