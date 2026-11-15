# Intel 실제 사용 단계로 이어가는 실행 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or a scoped subagent workflow. Steps are checked only after their acceptance evidence exists. Independent review precedes integration.

**Goal:** 현재 CUDA 연결 증거를 재현 가능한 Intel 사용 경로로 만들고, 실제 앱의 첫 실패가 다음 기능 개발을 결정하게 한다.

**Architecture:** 기존 Rust Driver/Runtime/PTX/SPIR-V/Level Zero 구조를 유지한다. 지원 계약·정적 inventory·실제 실행 증거를 연결하되 구현 상태와 검증 상태를 분리한다. 소스 수정/다운로드 바이너리, strict/virtual/injected, nominal/관찰 수치 증거를 합치지 않는다.

**Tech Stack:** 현 Rust 구성, Python/Windows native ABI 시험, pinned nvcc/SPIRV-Tools, Intel Arc. 새로운 종속성·API·라이브러리 어댑터는 실제 호출 근거가 있을 때 별도 설계한다.

**Spec:** [전체 검토](../../CT-REVIEW-2026-10-27.md), [장치 정책](../../DEVICE-CAPABILITY-POLICY.md), 기존 G0~G14/P00~P25는 장기 요구사항으로 유지한다. 이 계획의 R 번호는 별도 완료 추적이며 CUDA 버전·전체 완료율이 아니다.

## 2026-11-06 검토 후 실행 순서

Arc B390에서 기본 테스트 16개와 CUDA 예제의 계산 결과 514개를 재확인했다. 공개 가이드는 GPU 자동 선택 커밋을 가리킨다. 로컬 CUDA 예제는 사용한 GPU 이름을 출력하지만, 기본 테스트에서 지정한 장치가 CUDA 예제로 전달되지는 않는다. 아래 순서를 지금부터의 착수 기준으로 사용한다.

| 순서 | 작업 | 통과 기준 |
| --- | --- | --- |
| 1 | NVIDIA 드라이버 공존을 고려해 CUDA 예제 실행 절차를 고친다. 대조군의 관찰 결과와 CT 예제의 성공 판정을 분리한다. | 시스템 드라이버가 없거나 발견되는 두 경우를 재현해, 대조군 결과 때문에 CT 실행이 중단되지 않는지 확인한다. CT 예제는 앱 폴더의 CT DLL이 로드됐다는 확인과 계산·가드 검사를 모두 통과해야 한다. 실제 NVIDIA 드라이버가 설치된 PC의 공존 검증 결과는 모의 시험과 구분한다. |
| 2 | 기본 GPU 테스트와 CUDA 예제에 같은 장치 선택을 전달한다. Level Zero 열거와 CT의 CUDA 장치 매핑을 검토해 선택을 한 번 확정한다. | 기본 자동 선택과 명시 선택을 각각 시험한다. 서로 다른 장치, 같은 모델명의 두 장치, 사라진 장치, 모호한 선택을 다룬다. 장치 이름 문자열만으로 물리 장치 일치를 판정하지 않는다. 필요한 식별자는 실행 내부에서 비교하고 공유 결과에는 모델, 드라이버 버전과 성공 여부를 남긴다. |
| 3 | 깨끗한 소스와 공개 가이드로 재현한다. 다른 Intel 모델이 있는 Windows PC에서 기본 GPU 테스트와 CUDA 예제를 이어서 실행한다. | 두 테스트가 의도한 Intel 장치를 사용하고 정확성 검사를 통과한다. 모델별 결과와 제한을 기록한다. 이 단계의 통과 범위는 검증용 예제다. |
| 4 | R2의 실사용 후보 중 버전과 최소 작업을 고정해, 기존 CUDA 경로의 첫 실패를 재현한다. | 원본 앱의 실행 방식, 입력, 독립 정답과 실제 차단점을 기록한다. [R2v 검증](../../R2V-RUNTIME-TOPOLOGY-RESULTS.md)에서 17번 속성은 현재 Windows·Intel 구성에서 근거를 확보하지 못했다. 선정한 앱 경로에서 이 속성이 필수이고 정확한 정책을 확인할 수 있을 때 구현 대상으로 다시 검토한다. |
| 5 | 앱의 실제 차단점을 해결하고 Intel 시험 배포 기준을 검증한다. | 미수정 배포본에서 작업을 끝내고, NVIDIA 기준과 결과를 비교하며, 다른 Intel PC에서 설치와 실행을 재현한다. 같은 Intel 장치의 기준과 비교해 CT의 비용을 측정하고, 사용자가 감당할 수 있는 실행 시간인지 확인한다. 이후 AMD 실장비 검증으로 넘어간다. |

첫 두 작업의 시작점은 `tests/m3_connection_check.py`, `tests/m3_cuda_app.c`, `scripts/run_m3_smoke.ps1`과 `tools/ct-intel-smoke`다. 1단계는 시스템 드라이버가 발견되는 경우의 회귀 시험부터 만들고, 2단계는 여러 장치에서 선택이 어긋나는 경우를 재현한 뒤 전달 방식과 결과 판정을 정한다. 다른 PC 접근과 실사용 후보의 의존성 조사는 이 작업과 병행할 수 있다.

1단계 로컬 검증. Arc B390에서 외부 CUDA DLL을 찾지 못한 경우(41)와 별도 검색 경로에서 CUDA 함수가 없는 모의 DLL을 발견한 경우(5)를 확인했다. 두 경우 모두 앱 폴더의 CT DLL로 이어져 계산 결과 514개와 가드 128개가 통과했다. 모의 DLL은 CUDA 함수 조회 전에 거부됐다. 실제 NVIDIA 드라이버 공존 검증과 2단계 장치 선택 연결은 남아 있다.

### 2단계 장치 전달 설계

- 기본 테스트는 Level Zero에서 선택한 장치의 UUID를 검증 스크립트에만 전달한다. 일반 실행 결과에는 GPU 모델명만 표시한다.
- 검증용 CT DLL은 초기화할 때 얻은 장치 목록에서 그 UUID에 해당하는 CUDA 장치 번호를 찾는다. 해당 번호를 CUDA 예제의 컨텍스트 생성에 사용하고, 현재 컨텍스트의 장치도 확인한다. 일반 CT DLL의 공개 ABI와 장치 순서는 유지한다.
- 서로 다른 장치의 열거 순서가 바뀌는 경우, 같은 모델명의 장치 두 개, UUID가 없거나 중복된 경우를 먼저 모의 시험한다. 사라졌거나 모호한 장치는 계산 전에 실패해야 한다. 실제 장치 식별자는 공개 로그와 공유 결과에서 제외한다.
- Arc B390에서 기본 테스트와 CUDA 예제의 결과를 확인한 후, 다른 Intel 모델과 여러 GPU가 달린 PC에서 재현한다. 단일 GPU 결과와 다중 GPU 결과는 각각 기록한다.

2단계 로컬 검증. `pwsh -NoProfile -File scripts/run_m3_smoke.ps1`은 자동 선택으로 두 테스트를 실행한다. 특정 모델을 시험하려면 `-Device B390`처럼 모델명 일부를 지정한다. Arc B390에서 자동 및 명시 선택 모두 CUDA 계산 결과 514개와 가드 128개를 통과했다. 존재하지 않는 모델은 CUDA 검증 전에 거부됐다. 장치 순서 변경, 중복·누락·제로 UUID는 합성 시험에서 확인했다. 다중 GPU 실기기 재현은 남아 있다.

3단계 소스 재현. 고정 베이스 `219e6e5`를 새 폴더에 풀고 자동 선택, 공존 진단, 동일 장치 검증과 라이선스에 필요한 파일 13개만 적용했다. Arc B390에서 이전 빌드 산출물 없이 자동 선택과 명시 선택이 각각 CUDA 계산 결과 514개와 가드 128개를 통과했다. 타 PC 검증에서 공유할 항목은 사용한 커밋, Windows 버전, GPU 모델, 드라이버 버전, 실행 명령, `same_device_verified`와 검사 결과다. 다른 Intel 모델에서 실행할 때는 `-Device`에 그 PC의 모델명 일부를 넣거나 자동 선택을 사용한다. 이 후보의 공개 가이드 반영과 타 PC 실기기 재현은 남아 있다.

## 전역 조건

- Desktop 작업 트리만 사용하고 사용자 변경과 보호11파일을 보존한다. README/LICENSE/Cargo를 이 계획 정리 작업으로 덮어쓰지 않는다.
- 개인정보/원시 로그/벤더 cache는 ignored local 영역에 둔다. publication은 자동 후속 동작이 아니다.
- 원본 코드를 커널명·해시·모델명에 따라 준비한 답/대체 커널로 바꾸지 않는다.
- 원본 앱 빌드 recipe·source/binary/PTX·tool/version/hash와 입력/실행 명령을 먼저 고정한다.
- 지원하지 않는 문법/ABI/함수는 명시적으로 거부하고, version/장치 속성을 실행 통과 목적으로 꾸며 내지 않는다.
- Intel의 비샘플 앱·타 PC 재현·수치·실용 성능 문턱 전 AMD 구현 확대는 보류한다. 장비 미확보 항목은 미검증으로 유지한다.
- 코드나 compatibility 계약 변경 후 새 소스 근거가 필요하다. 이전 fingerprint의 GPU 결과를 새 소스 결과로 재명명하지 않는다.

## 우선 검토할 실패 종류

- nominal PASS와 실제 계산을 혼동하는 경우: NaN/미복사/미실행이 외부 oracle에서 반드시 실패해야 한다.
- profile/registry의 범위가 섞이는 경우: 제한된 Runtime/stream을 전체 미구현 또는 전체 지원으로 표시하지 않는다.
- 수명·순서가 긴 실행에서 달라지는 경우: 리소스 예산/해제·재사용·동시 작업·오류 후 cleanup을 따로 시험한다.
- 로컬 cache/절대 경로를 재현성으로 착각하는 경우: 고정 소스 tree/툴 식별자/이동 가능한 실행 묶음을 구분한다.
- 다른 하드웨어의 속도를 CT 번역 비용으로 해석하는 경우: 같은 Intel의 기준과 NVIDIA 의미 대조를 분리한다.

## R0. 현재 상태·공개 검사·재현 기준 정리 — 완료 기록

**예상 변경 파일:** docs/compatibility/{profile-v1,coverage-v1,applications,virtual-target-v1}.json, docs/compatibility/fatbin-profile.md, scripts/{check_public_artifacts,check_coverage,check_compatibility_profile,compatibility_registry}.py 중 필요한 범위, tests/{test_public_artifacts,test_coverage_registry,test_compatibility_profile,test_runtime_profile}.py. 실제 schema 변경 전 입력/출력 명세를 고정한다.

- [x] 현 source fingerprint/HEAD/dirty·untracked 목록과 마지막 capture/replay 해시를 read-only 기록한다. 제품 소스·보호11파일·SDK를 섞지 않는다.
- [x] Runtime/stream broad ID와 세부 구현 상태의 모순을 재현하는 실패 시험을 작성한다. Driver 밖의 범위와 제품 미구현을 구분할 schema/용어를 결정한다.
- [x] 필요한 최소 지원표 정정을 한다. Runtime은 bounded partial, Driver stream은 별도 미지원처럼 실제 범위를 명시한다. 단순히 unsupported를 supported로 바꾸지 않는다.
- [x] vectorAdd/matrixMul의 exact upstream revision, adjusted-build recipe, 실제 EXE SHA, strict/virtual 모드, 입력 범위, 수치/nominal/capture/replay 근거를 schema에 맞춰 앱 목록에 등록한다. 필요 시 schema와 검증기를 함께 확장한다.
- [x] fatbin의 과거 M3g globals 제외 문구를 역사적 범위로 명시하고 현재 mutable U32/U64와 device-call 미지원 상태를 구분한다.
- [x] `--working-tree` 같은 명시적 공개 검사 모드를 설계한다. tracked+untracked nonignored 실제 바이트를 읽고, index/staged/history 모드는 유지한다. 수정 파일/새 파일의 합성 개인정보 패턴을 놓치는 실패 시험부터 만든다.
- [x] 작업 트리 외부 symlink/해결 경로는 거부하며 민감한 일치 문자열을 출력하지 않는다. force-added ignored 비공개 경로도 차단한다. clean CI의 index 검사와 로컬 전체 검사의 report 범위를 분명히 한다.
- [x] 사용자 파일을 reset/stage하지 않고, allowlist 기반 별도 ignored 로컬 소스 후보와 content hash manifest를 만든다. clean-tree 재현과 공개 commit/hosted CI 상태는 각각 기록한다.
- [x] 필요한 CPU/validator/native 및 앱 검사를 새 소스 기준으로 실행하고 독립 검토한다. 기존5a513... 결과는 과거 근거로 보존한다.

메타데이터 정정이 GPU 코드 변경을 뜻하지는 않는다. 다만 현재 전체 fingerprint 체계에서는 새 소스에 대한 지원/실행 주장을 새 검증과 연결해야 한다. 시험 재사용 최적화는 source/config/environment/artifact 의존성을 명세·검토하기 전 임의로 적용하지 않는다.

**완료 문턱:** 정적 지원표·앱 목록·실제 실행 근거에 모순이 없고, 로컬 전체 검사에서 발견0건, 보호 파일 일치, 동일 고정 소스 후보의 재검증이 존재한다. 이때도 공개 push/릴리스가 된 것으로 세지 않는다.

완료2026-10-28: [R0 결과](../../R0-INVENTORY-SOURCE-RESULTS.md). clean 로컬 소스 후보 CPU11/11과 새98e40 Intel capture/replay를 확인했다. 공개/타 PC/성능 문턱은 별도다.

## R1. 지금 되는 계산 경로를 더 넓게 검증

**주요 기존 파일:** scripts/{matrix_kernel_check,run_matrix_kernels,matrix_runtime_check,run_virtual_target,fma_check}.py, 해당 tests와 새로 고정한 입력/오차 명세.

- [ ] 현재 원본 EXE는 block32/full-tile 전제와 상수 입력을 유지한다. 예를 들어(M,K,N)=(32,96,64),(96,32,64),(64,128,32) 등 추가 유효 full-tile 사례를 먼저 자원/시간 한도로 심사한다.
- [x] 원본 PTX Driver 소비자에는 비균일·비대칭·상쇄·다중 K-loop 입력을 추가한다. EXE를 수정한 입력을 원본 앱 증거로 기록하지 않는다.
- [x] 정확 dyadic 정답과 비-dyadic FMA/누적 정답을 구분한다. 오차 예산은 실행 전에 정하고, 결과가0일 때도 유한성/절대 오차 검사를 유지한다. FMA bit oracle·고정밀 기준을 독립 대조한다.
- [ ] 모든 입력/출력/guard, no-launch/no-copy/오염 대조군, 두 seed 이상과 별도 프로세스 replay를 요구한다. 같은 입력 재실행 횟수를 새로운 입력 다양성으로 세지 않는다.
- [ ] 긴 host/stream/event/module 반복 사용과 기존 lifetime 예산 경계, 오류 후 cleanup/동시 스레드 사용을 시험한다. 범위 밖 reset/Driver 혼용은 계속 명시적으로 분리한다.

**완료 문턱:** 새로 선언한 입력 집합·오차·수명 범위에서 수치/guard/대조군/replay가 모두 통과한다. 잘못된 partial-tile 원본 커널을 고의로 GPU에 보내지 않는다. 경계 처리는 R3/R4의 sound control-flow 기능으로 다룬다.

R1a 완료2026-10-28: [정확 입력 확대 결과](../../R1A-EXACT-MATRIX-BREADTH-RESULTS.md). 새7크기/6입력의42조합과28누락 대조군, 별도 replay를 검증했다. 비-dyadic 오차·장기 수명·원본 EXE 크기 확대는 미완료로 유지한다.

R1b 완료2026-10-28: [소수 입력 반올림 결과](../../R1B-MATRIX-ROUNDING-RESULTS.md). 제한된 normal/zero 입력의 FMA0ULP와 사전 gamma_K 실수 내적 한도,8조합/5120출력·8누락 작업·별도 replay를 확인했다. 임의 floating-point 입력/장기 수명/원본 EXE 크기 확대를 완료한 것은 아니다.

R1c 완료2026-10-28: [제한된 자원 수명 결과](../../R1C-RESOURCE-LIFETIME-RESULTS.md). Runtime512회·별도 Driver 모듈320회, live128 스트림/이벤트 한도 회복·stale 핸들·복구 가능한 오류·5대조군·별도 replay를 확인했다. 단일 호스트 호출자 범위이며, 동시 호출/실제 장치 고장/독립 fence 타이밍/모든 숨은 누수 부재는 미검증이다. 따라서 위 장기 수명·동시성 묶음 전체는 체크하지 않는다.

## R2. 실제 사용 앱 선정과 의존성 gate

**첫 후보:** tinygrad CUDA 경로의 작은 FP32 텐서/ML 작업과 CuPy의 작은 elementwise/RawKernel 작업. llama.cpp/PyTorch 전체는 초기에 성공을 약속하지 않는다. SDK transpose/reduction은 보조 의미론 목표다.

- [ ] 후보마다 exact commit/package hash, Windows/host ABI, toolchain, 라이선스/의존 DLL, 입력/기준 출력과 본래 CUDA 실행 경로를 고정한다.
- [ ] 실행 전 import/dynamic lookup/Driver·Runtime/library/API/PTX/fatbin/cubin/JIT 의존성을 목록화한다. 앱별 전체 필요 기능과 해당 최소 작업에서 실제 사용한 기능을 나눈다.
- [ ] source/CPU 분석으로 안전한 준비를 끝내고 통제된 실제 launch에서 처음 실패한 지점을 보존한다. 원인을 모르는 code를 GPU에 반복 제출하지 않는다.
- [ ] 현재 tinygrad 소스의 Driver stream/async copy/packed launch/host map 의존과 CuPy의 version/property/JIT/library 의존은 정적 단서다. 실제 고정 버전의 첫 실패를 확인하기 전 구현 요구사항으로 확정하지 않는다.
- [ ] 사용 가치, CT 고유의 CUDA 연결 필요성, 최초 공통 실패 범위, 수치 checker, 재현 비용으로 후보를 비교하고 하나를 선택한다. 실패를 피해 원본 연산을 바꾸거나 갑자기 과거 버전으로 낮추지 않는다.
- [ ] 선택된 앱을 applications registry에 정확한 evidence tier와 상태로 등록한다. source-adjusted와 downloaded-binary unchanged 경로는 별도다.

**완료 문턱:** 버전이 고정된 앱1개와 최소 실제 작업1개, 첫 차단점, 필요한 공통 기능 묶음, 독립 정답·대조군이 명확하다. 이 gate 전에는 앱을 지원한다고 선언하지 않는다.

## R3. 선정 앱의 첫 막힘 구현

R2 결과에 따라 **한 묶음만** 상세 설계한다. API 숫자를 채우는 순서가 아니다.

- [ ] Driver 경로가 먼저 막히면 stream 생성/파괴·소유권, 실제 전송 API, packed launch extra ABI 중 필요한 계약을 고정한다. Runtime stream 지원과 Driver stream 지원을 혼동하지 않는다.
- [ ] 장치/버전 조회가 먼저 막히면 공식 ABI와 의미를 대조하고 truthful bounded contract를 만든다. 미지원 속성을0으로 성공시키거나 임의 CUDA 버전을 반환하지 않는다.
- [ ] PTX 분기가 먼저 막히면 barrier 없는 제한 분기 영역의 재합류를 별도 명세로 다룬다. varying 분기를 전부 허용하지 않고 barrier 참여·early return·loop·shared taint 증명을 유지한다.
- [ ] 각 변경은 실패 시험, 최소 구현, 실제 API/producer ABI 대조, 무효/미지원/오류/수명 시험, 독립 검토, 기존 회귀, 앱의 다음 실패 지점으로 이어지는 것을 요구한다.

**완료 문턱:** 원본 앱/연산을 그대로 두고 실제 첫 실패가 해소되며, 새 차단점 또는 올바른 출력이 증거로 남는다. fabricated success나 커널별 특례가 없어야 한다.

## R4. 병렬·JIT·라이브러리를 앱 요구에 맞춰 확장

- [ ] transpose/경계형 커널이 요구하면 통제된 분기 재합류와 partial block의 모든 thread barrier 참여를 먼저 검증한다.
- [ ] reduction이 실제 요구하면 bounded dynamic shared, atomic ordering/scope, warp mask/shuffle 중 필요한 부분을 하나씩 설계한다. 부분 warp·분기 mask·race/litmus·메모리 한도를 포함한다.
- [ ] device 함수/libdevice, 작은 정수/벡터/구조체 ABI, FP16/BF16/FP64는 실제 producer 요구와 수치 기준별로 별도 확장한다.
- [ ] JIT는 고정된 NVRTC 실제 호출·생성 PTX·오류/캐시/옵션의 계약으로 연결한다. 이미 준비한 NVRTC producer가 제품 NVRTC ABI 지원이라는 뜻은 아니다.
- [ ] library가 먼저 필요하면 FP32 GEMM의 handle/pointer mode/layout/stride/error부터 검증 가능한 어댑터를 만든다. cuBLAS/cuDNN 이름만 다른 DLL로 바꾸지 않는다.

**완료 문턱:** 각 확장 기능이 해당 앱의 의미 있는 작업을 전진시키고 독립 수치/원래 CUDA 의미 대조를 통과한다. NVIDIA가 필요한 모호한 의미는 장비 접근 전까지 미검증으로 둔다.

## R5. 두 번째 Intel PC와 사용성

도구 준비는 R1/R2와 병행 가능하며 실제 타 PC 실행은 장비 접근이 필요하다.

- [ ] 현재 절대 경로 결합 frozen-evidence와 이동 가능한 사용자 묶음을 분리한다. provider/EXE hashes와 로컬 tool path/env provenance의 목적을 나눈다.
- [ ] 개인 cache를 복사하지 않고 공식 도구의 고정 식별자/라이선스 조건으로 준비한다. 진단은 GPU/드라이버·SDK·지원 profile·missing DLL/함수/PTX 실패를 구분한다.
- [ ] strict/실험 모드가 보이는 한 명령 실행 recipe, 재시작/설정 해제, 로컬 로그/비밀 정보 보호 규칙을 제공한다.
- [ ] 다른 Intel PC에서 설치부터 앱·수치·대조군·반복 실행까지 재현하고 모델/드라이버/버전/수동 단계를 기록한다.

**완료 문턱:** 기존 PC의 경로·숨은 파일 없이 동일 artifact/계약으로 실행된다. 다른 Intel 지원은 실제 통과 모델·드라이버 범위로만 표시한다.

## R6. 정확성 이후 성능과 병목 개선

- [ ] cold compile, module creation, first run, warm run, host/device copy, host overhead, 전체 wall time을 나눈다. correctness/guard 검사 비용은 측정 구간에서 구분한다.
- [ ] 동일 Intel에서 같은 SPIR-V/알고리즘의 직접 native 경로를 비교하면 API/런타임 비용, 실용 SYCL/라이브러리 구현과 비교하면 사용자 가치의 차이를 측정한다. 둘을 같은 지표로 섞지 않는다.
- [ ] 최초 native 기준 측정 후 CT 최적화 전에 선정 작업의 허용 기준을 수치로 고정한다: warm p95 지연 상한, 최소 처리량, cold-start 상한, peak memory 상한과 필요한 native 대비 허용 비율. 입력·정밀도·반복 조건과 사용자 가치 근거를 함께 기록하고 결과에 맞춰 기준을 사후 완화하지 않는다.
- [ ] NVIDIA 원본 실행은 결과/의미 대조에 사용하고 다른 GPU의 시간 차이를 CT 번역 손실로 주장하지 않는다.
- [ ] 반복/warmup/입력/전력 조건과 raw local timing을 고정한다. 현 global-counter event 값을 kernel-only 실행 시간으로 간주하지 않는다.
- [ ] 먼저 측정한 병목에 따라 compile cache, 불필요한 sync/메모리 복사, 단일 worker/native queue/global lock 구조 중 하나를 개선한다. 실제 overlap은 새 순서·수명 계약과 시험을 요구한다.

**완료 문턱:** 입력별 수치가 맞고 cold/warm 분포와 native 대비 근거가 있으며 사전 고정한 지연/처리량/cold-start/메모리 기준을 충족한다. 미달이면 성능 단계 미통과 또는 앱/범위 재선정으로 기록하고 R7의 실용 성능 충족으로 세지 않는다. 비교 없이 성능 백분율/near-native를 약속하지 않는다.

## R7/R8. Intel 시험 배포와 AMD

- [ ] Intel: 비샘플 실제 작업1개, 다른 PC 재현, 수치/대조군, 실용 성능, 오류 진단/수명/설치·제거, 개인정보/라이선스/원본 도구 재배포 조건을 함께 검토한다.
- [ ] 공개 지원표에 성공/부분 지원/미지원/미검증과 정확한 OS/GPU/드라이버/앱 버전을 표시한다. hosted CI 결과는 로컬 통과와 구분한다.
- [ ] AMD: Intel 문턱 후 실제 장치와 실행 backend를 고정하고, 같은 OS/host ABI의 동일 의미론/앱 묶음으로 메모리→kernel→수명→앱 순서로 검증한다.

**Intel 문턱 전 보류:** 무조건적인 모든 CUDA 함수 구현, AMD native backend 확대, SASS/cubin 범용 해독, 완전 PyTorch/TensorRT 호환, 최적화되지 않은 경로의 성능 약속. 장기 목표를 폐기하는 것이 아니라 현재 다음 작업의 범위를 정하는 것이다.

## 실행 순서와 인계

다음 착수 순서는 머리말의 2026-11-06 검토를 따른다. R2가 선정한 앱의 첫 차단점에 맞춰 R3 세부 계획을 확정한다. 실제 GPU 검증은 직렬로 진행한다. 각 단계 결과에는 입력, 파일, 환경, 도구, 반환값, 수치, 실패 대조군, 재실행 결과와 남은 한계를 기록한다.

이 문서는 계획이다. 체크되지 않은 작업은 구현 완료나 지원 약속으로 세지 않는다.
