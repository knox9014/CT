# CT 범용 CUDA 호환 계층 개발 명세와 전체 실행 계획

작성: 2026-10-20. 계획 작성 당시 구현 기준: M3o / d86d916.
상태: 사용자 목표 재확인에 따른 검토용 계획. 이번 문서 작성은 기능 구현·병합·릴리스가 아니다.
이 명세는 [전체 목표 G0~G14](CT-COMPLETION-GOALS.md)를 보존하며,
[P00~P25](CT-EXECUTION-ROADMAP.md)의 기능 목록을 삭제하지 않고 우선순위·증거·통과 조건을 구체화한다.
[중간 검토](CT-REVIEW-2026-10-20.md)의 앱 중심 제안은 아래의 **의미 coverage + 다양한 앱** 원칙으로 보완한다.

2026-10-21 진행 기록: [공통 검증 기반](CT-INTEGRATION-AUDIT.md)에 이어
[P05a primary context](P05a-RESULTS.md)를 구현·검증했다. Driver export는29개이며,
기본 플래그의 retain/GetState/release와 두 스레드의 자원 공유를 검증했다.
이어 [P05b reset](P05b-RESULTS.md)에서 참조를 보존하는 v2 reset과 두 스레드의
자원 무효화를 검증했다. 현재 export는30개다. 추가 플래그·독립 라이브러리 소비자는
P05c이며, 구형 ABI와 NVIDIA reset 후 핸들 재사용 대조도 남아 있다. 범용 CUDA 완성을 뜻하지 않는다.

## 1. 제품 목표와 성공의 정의

목표: 같은 OS·host ABI에서 기존 CUDA 프로그램의 실행 파일과 GPU 코드를 수정하지 않고,
가능한 넓은 CUDA API/ABI·코드·라이브러리 의미를 Intel·AMD GPU에서 보존하는 CT를 만든다.
특정 앱 실행은 중간 검증이며 제품 범위의 상한이 아니다.

우선순위는 정확성·호환 범위·안정성·성능을 함께 고려한다. 틀린 결과를 내는 빠른 경로는
지원으로 세지 않는다. 성능 목표는 동일 장치의 기준 측정 후 기능/앱별로 고정한다.
모든 CUDA 세대·모든 GPU의 무조건적 완전 호환이나 일정·완료율은 약속하지 않는다.

### 변경하지 않을 원칙

1. Rust 기반 CT 소유 CUDA ABI·상태 관리·컴파일러를 유지한다. 검증 도구·범용 compiler·vendor API를 활용한다.
2. 앱·커널 이름/해시·상수·shape를 보고 대체 커널이나 준비된 답을 선택하지 않는다.
3. CUDA API의 공개 의미를 대응 라이브러리로 구현할 수 있지만 자료형·배치·수치·순서·오류 계약을 검증한다.
4. 장치 속성·버전·기능 질의는 구현한 CUDA 의미와 실제 backend 제약을 반영한다. 초기화만 통과하려고 높은 버전을 꾸미지 않는다.
5. 하드웨어에 없는 기능은 정확성이 검증된 분해/에뮬레이션 또는 명시적 미지원으로 처리한다.
   CPU 실행·정확성 완화·소프트웨어 분해를 숨기지 않고 경로와 비용을 표시한다.
6. 시스템 GPU 드라이버를 덮어쓰지 않는 프로세스별 실행·설치·제거를 유지한다.
7. AMD/NVIDIA 실장비 부재는 Arc 개발을 막지 않는다. 해당 장비의 실행·대조 증거는 미검증으로 남긴다.
8. .gitignore와 공개 artifact/히스토리/신원 검사를 유지한다. 개인정보·키·개인 경로·raw log·vendor/generated binary를 공개하지 않는다.
9. 기존 미커밋 LICENSE/Cargo/README 수정은 이번 계획·기능 커밋과 섞거나 변경하지 않는다.

## 2. 계획 작성 당시 출발점

| 영역 | 현재 증거 | 아직 없는 핵심 |
| --- | --- | --- |
| 실행 | Windows x64 / Arc B390 / Level Zero 실제 실행 | 장치/OS 간 지원 검증 |
| 연결 | 제한된 Driver26 export, 프로세스별 DLL bundle, 함수 조회 | primary context, 일반 Runtime 시작·등록, 비동기 API |
| 컴파일 | 제한된 PTX7.0/sm_50·8.0/sm_52, 여러 entry, 타입/제어 흐름, 정수32/64 확장 | 범용 주소 공간·used global·device 함수·shared/warp·narrow/복합 ABI |
| 입력 | 실제 plain/compressed fatbin 및 대체 이미지 선택 | 일반 내장 wrapper/RDC/link/LTO/SASS |
| 시험 | M3o 기록 Rust85/Python21, Arc768사례·6,457,600출력·98,304guard | 공식 SPIR-V validator, 다양한 실제 compiler corpus·일반 앱 |
| 외부 코드 | 원본 공식 샘플 소스를 조정된 경로로 빌드·실행 | 원래 빌드/배포 artifact의 일반 호환 증거 |
| 통합 | 개발 브랜치에 누적, PR1~18 draft | 누적 통합 후보 검증·사용자 병합 결정 |

수치는 [M3o 결과](M3o-RESULTS.md)의 기록이며 이번 계획에서 재실행한 수치가 아니다.
원소 수·합성 사례 수를 독립 기능 수나 일반 호환성 비율로 환산하지 않는다.

## 3. 호환성의 여덟 축

| 축 | 추적할 세부 항목 | 완료 증거 |
| --- | --- | --- |
| 환경 | OS, host ABI, GPU/driver, CT/compiler/tool 버전 | 정확한 조합별 실행 보고서 |
| host 연결 | Driver, 동적/정적 cudart, import/동적 조회/entrypoint 버전 | 독립 공식 헤더 소비자·실제 로더 경로 |
| GPU 입력 | PTX, raw/compressed fatbin, 내장 wrapper, RDC/link, LTO IR, SASS-only | 입력별 정상/손상/충돌/재배치 검사 |
| compiler 의미 | 타입/modifier/인자 ABI/주소 공간/제어 흐름/함수/global/math | IR·출력 검증, 독립 정답, compiler corpus |
| 메모리 | 명시 할당/전송, pinned/mapped/pitched/array, pool/VMM/UM | 범위·소유권·수명·동기화·가시성 |
| 병렬 의미 | block/shared/barrier, atomic/order/scope/fence, 논리 warp, stream/event | 참여 규칙·허용 결과 집합·의존 그래프 |
| 생태계 | 수학/DNN 라이브러리, JIT/custom extension, framework, interop/도구 | ABI/수치/순서와 고정 외부 소비자 |
| 증거 단계 | 합성, 외부 소스 조정 빌드, 원래 recipe 빌드, 배포 artifact | 종류를 구분한 해시·정답·재현 |

API·명령 이름 하나의 존재는 타입/modifier/정렬/동시성/버전 전체의 지원이 아니다.
각 항목은 세부 형식·제약과 시험 ID를 가지며 구현과 실행 증거는 별도 파일에 둔다.
구현 상태는 missing/partial/implemented/research, 실행 상태는 pass/fail/skipped/not_run이다.
CPU 의미 검증·Arc 실행·NVIDIA 대조·AMD 실행을 각각 기록한다.

## 4. 공통 아키텍처와 소유 경계

```text
기존 CUDA EXE / DLL / Python extension
  → 로더·의존성/기능 진단
  → Driver ABI ← Runtime / 라이브러리 adapter
  → 단일 CT 실행 상태: device/context/resource/submission/completion
  → 모듈 입력·심볼·link 관리
  → PTX parser → 타입·주소 공간·제어 흐름 IR → 의미 검증/합법화
  → Intel SPIR-V / 향후 AMD 코드 생성
  → vendor runtime·driver → 실제 GPU
```

| 경계 | 책임 | 금지할 결합 |
| --- | --- | --- |
| ABI | 원래 호출 규약, 버전별 symbol, 크기/정렬/enum/구조체, 오류/출력 규칙 | 단순 이름 일치만으로 지원 선언 |
| 공통 실행 상태 | 자원 소유권, generation, TLS, 참조, 실패 상태 | Runtime DLL별 별도 Driver 상태 |
| IR | 명시적 타입·주소 공간·alignment·ABI layout·메모리 순서·scope | Intel subgroup 크기를 CUDA warp 의미로 고정 |
| 합법화 | target capability로 의미 보존 변환 또는 진단 | 조용한 정밀도/동기화 의미 완화 |
| backend | 장치 기능, 메모리, 제출/완료, native handle·오류 | 앱 이름에 따른 backend 분기 |
| adapter | library handle/descriptor/workspace·수치·stream 계약 | DLL 이름만 바꾸거나 인자 재해석 생략 |
| 진단/캐시 | 실패 위치/기능 ID, 버전·ABI·장치·옵션·내용 기반 키 | 원본 코드/개인 경로 유출, 다른 장치 binary 재사용 |

현재 작동하는 직접 SPIR-V emitter는 유지한다. 실제 함수·주소 공간·제어 흐름 확장에서
구조적 한계가 반복되면 고정 corpus로 LLVM/SPIR-V 대안을 비교하고 선택 기록을 남긴다.
AMD trait를 추측해 모든 계층을 먼저 재작성하지 않고 두 번째 backend 실험의 요구로 경계를 검증한다.

## 5. 필수 의미 계약

### 5.1. 컨텍스트와 메모리

primary/명시적 context, retain/release/reset, TLS current stack, 여러 host thread,
generation별 stale handle, 장치별 자원 소유권을 먼저 정의한다. reset과 마지막 release는
같은 동작으로 가정하지 않고 실제 export 버전의 공식 계약을 대조한다.
기존 헤더 기준은 CUDA12.0.107이며 문서12.0.1의 함수 이름과 _v2별 의미 차이도 확인한다.

할당·해제·복사는 범위/overflow/정렬/0크기/overlap/context/소유권 규칙을 명시한다.
현재 포인터 시작+최소 span 검사는 전체 kernel 접근 증명이 아니다. trusted kernel 조건을 유지한다.
나중에 비신뢰 입력 격리를 제공하려면 host process 격리와 GPU 메모리 보호의 한계까지 별도 검토한다.

### 5.2. 제출·완료·동기화

submission과 completion을 구분하고 allocation/module/kernel/host staging을 완료까지 보존한다.
free/unload/destroy가 대기·지연 파괴·오류 중 어떤 동작을 하는지 각 API 계약으로 고정한다.
stream/event의 default/PTDS/nonblocking, event 재기록 generation, callback 재진입,
지연 오류, query NOT_READY를 분리한다. 전역 mutex를 잡은 채 callback/외부 재진입을 기다리지 않는다.
오류 후 정상 복구와 completion 불명확에 따른 poisoned context를 구분한다.

### 5.3. compiler와 병렬 연산

- 인자는 size/alignment/offset/type/address-space를 보존한다. 구조체/vector/narrow 변환과
  load 확장 규칙은 별도 검증하며 현재 모든 wide-entry 포인터 align8 제한의 제거는 provenance 작업으로 다룬다.
- 사용되는 global/constant 저장소·초기화·symbol lookup과 device 함수 호출/반환/재배치 수명을 구현한다.
- FP의 rounding/FMA/contraction/NaN/Inf/signed zero/denormal을 형식별 계약으로 고정한다.
  유한 FP32 테스트의 성공을 모든 수치 예외로 확대하지 않는다.
- shared/barrier는 block 참여·분기·부분 block·자원 한계를 검증한다.
- atomic은 자료형·원자성·scope/order/fence와 주소 공간을 함께 구현한다.
- CUDA 논리 warp32와 Intel subgroup/AMD wave를 동일시하지 않는다. mask·분기·부분 warp와
  shuffle/vote/ballot의 참여자를 보존하는 분해를 먼저 증명한다.

## 6. 전체 작업과 세분화

아래 묶음은 장기 경계와 통과 조건이다. 즉시 코딩 가능한 계획은 다음 절과 별도 첫 실행 계획이다.
각 하위 PR은 착수 전에 정확한 API/명령 형식·파일·오류·수치·시험을 고정한다.

| 기존 ID | 하위 묶음 | 선행/병행 관계 | 통과 증거 |
| --- | --- | --- | --- |
| P00 | coverage/behavior map, tool lock, 결과 schema | 즉시; 모든 작업과 병행 | 선언·실행 분리, 공식 헤더 ABI, 잘못된 pass 거부 |
| P01/P02 | 입력·여러 entry 기반 유지; wrapper/link·global은 별도 확장 | 현재 기반 있음; P09/P04와 연결 | 손상/대체 충돌/소유권·unload 검사 |
| P03 | narrow8/16·load 확장, scalar/vector/struct ABI, 연산/수치 modifier, producer 문법 | P04/P05와 병행; 전체 완료를 P09 앞에 두지 않음 | 독립 의미·변형·compiler corpus·조합 |
| P04 | 04a 주소 공간/포인터 provenance;04b global/constant;04c 함수/호출;04d libdevice | P02 및 필요한 P03 형식 | 같은 symbol을 공유한 여러 kernel, 호출/반환·미해결 참조 |
| P05 | 05a primary 상태/TLS;05b reset/수명;05c 다중 소비자/flags | P00 뒤 우선; P03 전체 불필요 | retain/release/reset 차이, 두 thread/소비자, stale/실패 |
| P06 | 06a D2D/memset/속성;06b pinned/mapped;06c pitched2D/3D | P05;06a만 첫 동기 Runtime의 후보 선행 | byte 정답·범위·0/overflow/정렬·해제 |
| P07 | 제출/완료 모델, in-flight 참조, 지연 파괴·오류 | P05/06a; 비동기 API보다 먼저 | 완료 전 free/unload/destroy, 실패 후 보존 |
| P08 | 08a stream/default/PTDS;08b event;08c async copy/callback | P07; pinned 관련 API는06b | 두 stream 그래프, NOT_READY, 재기록·재진입 |
| P09 | 09a 동적 Runtime/등록;09b 정적 Runtime Driver 요구;09c 비동기 Runtime | P02/P05/06a;09c는P08 | 내장 모듈·init/teardown·오류TLS·Driver 혼용 |
| P10 | static shared, dynamic shared, barrier, 자원/참여 규칙 | 필요한 P03/P04;P09와 일부 병행 | reduction/타일계산·부분 block·분기 참여 |
| P11 | atomic 자료형·연산, order/scope/fence, reduction | P10 및 주소 공간 | 경쟁 counter/histogram, 허용 결과 집합 litmus |
| P12 | logical warp/mask, shuffle/vote/ballot, divergent 실행 | P10/11 결과와 target 실험 | 부분 warp·mask·32와native크기 차이 |
| P13 | NVRTC 경로, cuLink/nvJitLink/RDC, device link, LTO 조사 | P04;Runtime 전체 없이 조사 가능 | 실행 중 생성/두 object 참조/미해결·오류 |
| P14/P15 | AMD 네이티브 feasibility→공통 IR 코드 생성→공통 실행 | 현재 장비 미확보; 인터페이스 연구 가능 | 같은 OS/ABI artifact 실제 Intel/AMD 교차 |
| P16 | SGEMM→pointer mode/stride/batch/handle/stream | P05/06a, async는P08 | 독립 수치·layout·transpose·오류·소비자 |
| P17 | BLASLt/FFT/RAND/SPARSE/SOLVER/DNN, FP64/저정밀 | library별P03/04/08/10~13 | library별 동작·수치·workspace·실제 소비자 |
| P18 | 여러 계층/분야 consumer cohort·artifact registry | 즉시; 모든 주 작업의 진단 도구 | 증거 단계·버전·hash·정답·최초 실패 |
| P19 | CI/validator/fuzz/fault/cache/doctor/package/perf/공존 | P00부터 상시 | 아래 검증/릴리스 gate 전체 |
| P20 | array/texture/surface, VMM/pool, Unified Memory | 관련P05~08·backend별 실험 | 일관성·수명·주소·명시적 미지원 |
| P21 | MMA/저정밀, Graph/capture, cooperative/cluster, device async/동적 병렬 | 기능별P03/08/10~13 | 의미 보존·수치·성능 feasibility 후 편입 |
| P22 | 22a IPC/external memory·semaphore 계약과 단일장치 경로;22b peer/multi-GPU;22c NCCL/분산 | 22a는P05/06 및필요한P07/08·OS/backend기능;22b/22c만실제여러장치;AMD는해당backend대상일때만P15필요 | 카드별장치수·프로세스/장치간수명·전송·순서·통신·장애 |
| P23 | graphics/video interop, CUPTI/debug/profile/NVML | 대상API·장비·OS별 | 실제 소비자/도구 지원 또는 진단 |
| P24 | SASS/cubin 전용 명령·재배치·ABI의 별도 엔진 연구 | 별도 feasibility;PTX경로와 구분 | 좁은 아키텍처 go/no-go와 한계 |
| P25 | Linux loader/ABI, 추가Intel/host 아키텍처 | 공통 의미 기반·각환경 장비 | 환경별 같은 artifact 및 회귀 |

기존의 이름 있는 요구도 다음 카드로 명시적으로 추적한다.

| 요구 | 담당 카드 | 검증 경계 |
| --- | --- | --- |
| Thrust/CUB 생성 kernel | P03/P04/P10~12/P18 | source-levellibrary이름만매핑하지않고실제생성코드의메모리·병렬의미검사 |
| Triton/JIT/custom extension | P13/P18 및필요한P03/P10~12 | 실제입력PTX/연결/런타임경로와고정버전별검사 |
| TensorRT | P17/P18의독립feasibility카드 | engine/전용runtime/plugin과GPU입력의의존성조사후별도계약 |
| external memory/semaphore | P22a/P23 | 단일장치/다중프로세스와multi-GPU를분리해OS별실제기능검증 |

## 7. 우선순위와 병행 실행선

우선순위는 한 앱의 최초 실패만으로 정하지 않는다.

| 등급 | 선택 기준 | 예 |
| --- | --- | --- |
| A 필수 기반 | 의미/ABI/수명/진단의 모순을 막으며 여러 기능의 선행 | primary context, 실제 SPIR-V 검증, 단일 상태 |
| B 범용 확장 | 여러 기능군·독립 소비자를 함께 열거나 조합 공백을 줄임 | Runtime 등록, 주소 공간, shared/barrier, async 수명 |
| C 분야 확장 | 특정 분야이지만 공통 표준 API로 여러 소비자에 재사용 | FFT/DNN/특정 수치형 |
| D 연구 | 하드웨어·배포·의미 실현성이 아직 확인되지 않음 | SASS/MMA분해/cluster/새backend |

모든 작업 카드에는 의미 coverage 공백, 의존 기능 수, 영향을 받는 서로 다른 소비자,
정확성 위험, 현재 장비 검증 가능성, 예상 변경 경계를 기록한다. 근거 없는 점수/기간은 만들지 않는다.
공통 표준의 필수 기능은 당장 사용하는 앱이 없어도 A/B로 구현할 수 있다.
새 스칼라 명령은 기준 시험·producer corpus·다른 기능 조합에 연결해 독립 추가 가치도 평가한다.

실행선:

- T0 증거/통합/진단: 첫 실행 묶음 → 모든 기능 PR의 검증 기반 유지.
- T1 host 실행: P05 → P06a → P09a/09b, P07 → P08 → P09c 병행 확대.
- T2 compiler: P03/P04의 타입·주소·함수·수치·문법을 corpus와 의미 matrix로 확대.
- T3 병렬: 필요한T2 기반 → P10 → P11 → P12;Runtime 전체 완료까지 기다리지 않는다.
- T4 생태계: P13과 P16 → library별P17 → MLP/CNN/Transformer 추론·학습·framework.
- T5 장기/장치: P14/15/20~25를 기능별 실현성 연구와 실장비 확보에 따라 편입.

한 묶음 구현은 책임 파일을 분리하고 독립 검토를 하위 에이전트에 맡긴다. 공유 상태나
의존성 있는 Rust 코드를 여러 구현자가 동시에 바꾸지 않는다. 병행은 작업 독립성이 확인된 경우에만 한다.

## 8. 기능 편입과 범용성 검증

| 층 | 필수 검증 | 성공 해석 |
| --- | --- | --- |
| L0 계약/최소 재현 | 명세·정확한 형식·RED·예상 오류/출력 | 무엇을 구현하는지 고정 |
| L1 단위/ABI | 타입·range·size/alignment/offset·calling convention·version | 내부/host 경계의 정합성 |
| L2 의미/조합 | 경계·예외·수명·독립oracle·다른 기능과 조합 | 단일 이름 이상의 의미 검증 |
| L3 일반화 | 이름/상수/shape변형, mutation/property, 실제 producer출력 | fixture 과적합 억제 |
| L4 실제 장치 | Arc정답/guard·반복·오류·자원 | 현재 target 실제 실행 |
| L5 소비자 | 개발에 사용하지 않은 holdout·다른분야·Driver/Runtime/JIT/library | 지원 profile의 외부 일반화 |
| L6 교차/출시 | NVIDIA대조/AMD동일artifact·공존·설치·성능·내구 | 해당환경/제품에 한정한 주장 |

각 PR에 모든 앱/장치를 요구하지 않는다. 해당 기능의 L0~L4를 먼저 완료하고 관련L5를
누적하여 profile을 승격한다. 새 preview 이름이 기존 M3/v0.1의 미검증 gate를 우회하지 않는다.
NVIDIA 의미 대조가 필요한 항목은 미검증 표식을 유지하며 Arc 기능 개발과 별도로 추적한다.

소비자 집합은 최소 다음 여섯 유형을 조사한다: Driver외부모듈, 동적Runtime내장모듈,
정적Runtime, shared/reduction/scan, library사용 수치·영상, JIT/custom extension.
합성소비자/외부소스조정빌드/원래recipe빌드/기존배포artifact를 각각 구분한다.
각 주요 기능군은 서로 다른 두 kernel family의 조합 검증과 별도 holdout 소비자를 목표로 하며,
정확한 cohort와 수치 허용오차는 실행 전에 고정한다. 알려진 성공 앱만 시험 집합에 남기지 않는다.

### 오류·수치·성능 기준

- 정수는 모든 비트를 정확 비교한다. float는 rounding/ULP/절대·상대오차/NaN/zero 규칙을 사전에 정한다.
- 초기 payload가 기대값과 다르게 설정됐는지, guard·읽기전용 입력이 보존됐는지 확인한다.
- API 출력은 성공/실패 시 변경 규칙을 검사한다. unsupported를 성공이나 빈 결과로 바꾸지 않는다.
- 새 parser/container는 손상/한계/fuzz, backend는 fault injection과 uncertain completion을 검사한다.
- 커널100회·자원cycle1000회는 초기 회귀 기준이다. 장기 안정성 보장은 별도 시간/메모리 관찰로 검증한다.
- cold compile/cache hit/transfer/kernel/app 전체 시간을 분리한다. CPU나 다른 GPU 속도를 같은 장치의 기준으로 쓰지 않는다.

## 9. 릴리스와 완료 주장

| 단계 | 최소 주장 범위 | 통과 조건 |
| --- | --- | --- |
| 현재 prototype | 제한 Driver/PTX의 Arc 실행 | 현재 결과/제약 그대로 |
| Arc 기능 profile | 고정API/명령 조합의 Arc지원 | 계약·L0~L4·traceability·범위 공개 |
| Arc 앱 개발 preview | 명시한다양한소비자의 실험 실행 | L5·artifact고정·진단·반복;미검증명시 |
| 기존 Intel alpha | 기존M3/v0.1기준의실행 | 원래gate의미수정앱·NVIDIA대조·공존 포함 |
| dual-vendor alpha | 같은OS/ABI artifact Intel/AMD | 실제양장비공통profile검사 |
| library/framework beta | 고정버전의생태계범위 | 연산·수치·수명·실제소비자·회귀 |
| 실사용 release | 지원표에고정한제품계약 | 설치/제거/배포/장기안정/진단/성능 |

범용성은 완료 퍼센트가 아니라 (a) 의미 matrix의 빈칸 감소,
(b) 독립 소비자/경로의 증가, (c) 조합·장치 검증 깊이로 평가한다.
P24 등 연구가 실패하면 한계를 남기고 해당입력을 미지원으로 유지한다. 전체 목표에서 조용히 삭제하지 않는다.

## 10. 바로 다음 묶음과 재계획 규칙

기반 작업은 [검증·coverage 실행 계획](superpowers/plans/2026-10-20-universal-foundation.md)을 따른다.
산출물: 별도coverage registry, typed시험/실행보고서, 실제compiler corpus registry,
SPIR-V validator/module exporter, export behavior map, CPU/native lane, 누적PR통합보고서.
앱·producer 조사와 도구/검증 기반은 독립 범위에서 병행한다.

이 여섯 Task 전체를 기능 설계의 공통 선행 조건으로 두지 않는다. P05 ABI/참조/reset/TLS와
P03/P04 주소·타입·함수, P10 참여 규칙의 설계는 현재 코드·고정 명세를 근거로 즉시 병행할 수 있다.
구현 착수에는 정확한 source 기준·해당 ABI/API 계약·최소 재현/시험 기록과 관련 차단 결함의
해결이 필요하다. 전체 corpus 수집이나 모든 PR 누적 audit의 완료까지 기다리지 않는다.
기능 편입 때 해당 변경의 공식 ABI·실제 Arc 회귀를 필수로 하고, SPIR-V 출력/의미를 바꾸면
공식 validator를 추가 필수 gate로 둔다. 독립 기반 작업의 미완료는 해당 기능과 무관하면 차단하지 않는다.
공통 profile/릴리스 승격과 첫 기반 묶음 자체의 완료에는 그 단계의 필수 검증을 모두 요구한다.
P05 및 P06a가 준비되면 첫 동기 Runtime 구현 경로를 확정한다.

재계획 조건:

1. 실행 결과가 실제보다 높게 표시되거나 잘못된 답을 내면 기능 확대보다 정합성 수정을 우선한다.
2. 기능 두 묶음이 의미 coverage·조합·외부 소비자 어디에도 새 증거를 만들지 못하면 우선순위를 검토한다.
3. backend/IR가 명세 의미를 보존하지 못하면 API 추가를 멈추고 고정 reproducer로 실현성을 비교한다.
4. 정적cudart·전용library·SASS가 넓은선행을 요구하면 표기된별도경로로 분리한다. 쉬운입력으로 바꾼 성공은 원래경로로 세지 않는다.
5. 누적draft stack을 계속 늘리기 전에 실제통합후보를검증한다. 병합은 사용자결정으로 남긴다.

## 11. 참고와 도구 채택 기준

- [CUDA12.0.1 Driver/primary context](https://docs.nvidia.com/cuda/archive/12.0.1/cuda-driver-api/group__CUDA__PRIMARY__CTX.html): 단일device의Runtime공유context계약. 실제export버전은고정12.0.107헤더와대조.
- [CUDA stream 규칙](https://docs.nvidia.com/cuda/archive/12.0.1/cuda-runtime-api/stream-sync-behavior.html): legacy/PTDS의의미를분리.
- [PTX ISA](https://docs.nvidia.com/cuda/archive/12.1.1/parallel-thread-execution/index.html): 타입·modifier·병렬·메모리계약. 이버전전체지원선언아님.
- [SPIRV-Tools](https://github.com/KhronosGroup/SPIRV-Tools): 공식validation도입. 통과도CUDA동등성의대체는아님.
- [ZLUDA](https://github.com/vosen/ZLUDA), [chipStar](https://github.com/CHIP-SPV/chipStar), [PCUDA](https://github.com/AdaptiveCpp/AdaptiveCpp/blob/develop/doc/pcuda.md), [SCALE](https://docs.scale-lang.com/stable/), [HIPIFY](https://github.com/ROCm/HIPIFY), [SYCLomatic](https://github.com/oneapi-src/SYCLomatic): 중간검토의구분대로설계/시험참고.

외부구성요소는원본·버전·hash·변경·라이선스/NOTICE를기록하고, CT장비의실행가능성을시험한다.
소스이식·vendor도구실행·타엔진실행을기존CUDAartifact의CT호환성으로세지않는다.

## 12. 계획 검토 기록

두 읽기전용 하위 검토가 제안한 (1) 앱최초실패독점 대신 의미coverage 병행,
(2) 구현/검증상태분리, (3) v1schema보존, (4) module exporter, (5) ABI원본헤더고정,
(6) CPU/native실행분리와통합검증을 반영했다. 두문서의독립최종검토에서지적된
report검증context·환경/입력provenance, tool정적/실행검사분리, trackedHEAD자기참조,
Arc/producer 의존성분리, Rust시험의정확한경로, 계획턴구현금지를수정했다.
추가 독립 재검토에서 기반 전체의 직렬 gate, 환경/설정 검증 context, corpus 재현 경로,
P22의 과도한 AMD/다중장치 의존성을 발견해 수정했고 external memory 등 세부 추적을 보완했다.
공식 ABI probe의 명목 타입·버전 macro 충돌도 별도 translation unit과 표현 비교로 예방하도록 했다.
중대한목표삭제나앱전용축소는보고되지않았다. 이는계획검토이며구현의성공보증이아니다.
기능 구현은 이 문서에서 시작하지 않았다.

추가 결과: [계획 독립 재검토 기록](CT-UNIVERSAL-PLAN-REVIEW.md).
