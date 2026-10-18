# CT CUDA 호환 드라이버 설계 및 개발 계획

작성: 2026-10-19. 상태: 검토용 설계안, 구현 전.

이 문서는 기존 CT-ROADMAP.md의 재사용 엔진 중심 전략을 대체한다. 사용자 목표는 CT 자체를 개발하는 것이다. 아래에서 목표와 제안 기술을 구분하며, 아직 GPU 실행 성공이나 호환성을 주장하지 않는다.

## 1. 제품과 범위

CT(Cuda Translater)는 우리가 개발하고 유지하는 범용 CUDA 호환 드라이버·실행 계층이다. 장기 목표는 같은 OS·호스트 아키텍처에서 기존 CUDA 프로그램을 수정하거나 다시 빌드하지 않고 Intel·AMD GPU에서 실행하는 것이다. 특정 앱의 패치나 기존 도구의 설치 관리자가 제품의 중심은 아니다.

CT는 사용자 공간에서 CUDA API/ABI와 GPU 코드 실행 의미를 구현한다. 제조사의 커널 드라이버·펌웨어는 하부 기반으로 사용한다. 디스플레이·PCIe·전원 관리까지 담당하는 새 커널 드라이버는 초기 범위에 넣지 않는다.

범용성은 프로그램마다 정답이나 커널을 하드코딩하지 않고 공통 API·명령 의미를 구현한다는 뜻이다. 첫 릴리스부터 모든 CUDA 기능을 지원한다는 의미는 아니다.

## 2. 환경과 초기 우선순위

- 2026-10-19 연결 장치 조회: Intel(R) Arc(TM) B390 GPU, Started. 해당 모델의 설치된 드라이버 항목: 32.0.101.8622.
- 현재 Windows에서 개발·검증을 시작한다. Level Zero 사용과 커널 실행은 아직 확인하지 않았다.
- AMD/NVIDIA 실장비, Linux/WSL 사용 가능 여부는 미확정이다.
- OS 전환을 전제로 작업하지 않는다. 현재 환경의 실행 경로가 성립하지 않으면 대안과 원인을 먼저 제시한다.

## 3. 구현 접근 선택

| 접근 | 장단점 | 선택 |
| --- | --- | --- |
| 새 커널 드라이버까지 개발 | 장치 제어·서명·안정성까지 범위가 커짐 | 초기 제외 |
| 자체 사용자 공간 CUDA 계층 + 자체 PTX 변환 + 제조사 백엔드 | 목표에 맞고 작은 API/명령부터 확장 가능 | 권장 |
| 기존 호환 엔진을 감싸 제품화 | 데모는 빨라질 수 있으나 CT 자체 개발 목표와 차이 | 제품 중심으로 삼지 않음 |

ZLUDA 등은 설계·검증 비교 대상으로 참고한다. LLVM, SPIR-V 도구, 벤더 SDK 같은 범용 기반은 사용할 수 있다. 외부 코드를 채택하면 파일·버전·라이선스·수정 범위를 기록한다. 기존 엔진 실행을 CT 자체 구현 성공으로 보고하지 않는다.

## 4. 구성과 소유 경계

```text
기존 CUDA 프로그램
        ↓
CT 프로그램별 로더
        ↓
CUDA Driver API / ABI 계층
        ↓
CT 런타임: 컨텍스트·메모리·모듈·스트림·이벤트
        ↓
PTX 파서 → 타입 있는 CT 내부 표현 → 대상 코드 생성
        ↓
Intel 백엔드                    AMD 백엔드
SPIR-V / Level Zero 후보        LLVM AMDGPU / HIP·ROCm 후보
        ↓                            ↓
Intel 제조사 드라이버           AMD 제조사 드라이버
        ↓                            ↓
Intel GPU                       AMD GPU

별도 확장: Runtime API / fatbin / cuBLAS 등 라이브러리 어댑터
```

| CT 구성 요소 | 직접 책임질 동작 |
| --- | --- |
| CUDA ABI | export 심볼, 인자/구조체 배치, 버전별 진입점, 오류 반환 |
| 런타임 코어 | 스레드별 컨텍스트, 자원 소유권·수명, 주소와 핸들 구분 |
| PTX 프런트엔드 | 구문·타입·주소 공간·명령 의미·지원 판정 |
| CT 내부 표현 | 타입·제어 흐름·메모리·커널 인자를 벤더 독립적으로 표현 |
| 코드 생성 | PTX 의미를 보존하는 Intel/AMD 실행 코드 생성 |
| 백엔드 | 장치 열거, 할당, 복사, 모듈 로딩, launch, 완료 확인 |
| 라이브러리 어댑터 | CUDA 수학 라이브러리의 타입·배치·정밀도·스트림 의미 연결 |
| 제품 도구 | 실행 로더, doctor/inspect/run, 로그·캐시·지원 표 |

초기 언어는 Rust와 외부 C ABI를 제안한다. SDK 연결에는 필요한 C/C++를 허용한다. 첫 Intel 경로는 제한된 PTX → CT 표현 → SPIR-V → Level Zero다. SPIR-V 프로파일·포인터 표현·커널 인자 ABI는 실험으로 확정한다. Level Zero의 SPIR-V 지원만으로 PTX 번역 가능성이 입증되는 것은 아니다.

AMD 경로는 CT 표현에서 AMD 코드를 생성하고 HIP/ROCm 등으로 로딩하는 방향을 평가한다. HIP가 PTX를 직접 실행한다고 가정하지 않는다. 공통 인터페이스는 실제 두 백엔드의 요구를 확인하면서 정리한다.

CUDA Runtime API는 Driver API 위의 별도 호환 과제다. Driver API 몇 개의 구현이 기존 cudart 전체 지원을 뜻하지 않는다. PTX와 NVIDIA 기계어(SASS/cubin)도 구분한다.

## 5. 마일스톤

### M0. Arc B390 하부 실행 기반

작업: Windows x64 툴체인·Level Zero 로더/장치 확인 → 네이티브 메모리 할당·복사 → 사전 준비한 SPIR-V 벡터 덧셈 → 회수·정답 비교. 인자 ABI, GPU 주소, 모듈 빌드 로그, 그룹 크기 제한을 기록한다.

산출물: `docs/environment-matrix.md`, `docs/decisions/0001-intel-execution-path.md`, 재현 가능한 backend smoke test.

통과: 실제 B390 GPU 실행과 CPU 기준값 비교 성공. CPU 대체 실행 금지. 이 단계는 Intel 실행 기반 검증이며 CUDA 호환 성공이 아니다.

### M1. CT CUDA ABI와 메모리 관리

작업: 초기화·장치 열거·이름·컨텍스트·메모리 할당/해제·동기 복사·동기화·오류 조회. 구현 전 API 목록과 정확한 버전별 C 서명을 `docs/compatibility/driver-api.md`에 고정한다. `cuMemAlloc_v2` 등 접미사 심볼을 구분한다.

통과: CT DLL을 명시적으로 여는 독립 테스트 호스트에서 메모리 왕복 성공. 컨텍스트 없음, 잘못된 핸들, 해제 후 접근, 범위 초과, 할당 실패를 시험한다. 명시적 CT DLL 로딩을 일반 앱 자동 호환이라고 부르지 않는다. 미구현 속성·CUDA 버전을 NVIDIA 장치처럼 과장해서 광고하지 않는다.

### M2. 자체 PTX 변환기

작업: 고정 PTX 버전의 구문·타입 분석 → CT 표현 → SPIR-V 생성·검증 → 모듈 로딩·함수 조회·커널 실행. 정수/FP32, kernel 인자, 주소 산술, 전역 메모리, 스레드/블록 인덱스, 비교·분기부터 시작한다.

명령 후보: `ld.param`, `ld.global`, `st.global`, `mov`, `add`, `mul`/`mad`, `cvt`, `setp`, 조건부 `bra`, `ret`. 실제 fixture가 사용하는 타입·modifier 조합을 명시하며 opcode 하나로 모든 변형을 지원한다고 선언하지 않는다.

통과: 벡터 덧셈·SAXPY·ReLU·shared memory 없는 단순 FP32 행렬곱을 CT 경로에서 실행한다. 커널명·상수·입력 크기·블록 크기를 바꾸어도 의미가 유지되어야 한다. 커널명/해시별 사전 구현으로 치환하는 우회 금지. 미지원 명령은 위치와 이유를 보고한다.

### M3. 기존 CUDA 실행 파일 연결 — v0.1 Intel alpha

작업: 프로세스별 로더, 정적 import·동적 라이브러리/심볼 조회·버전별 Driver 진입점 접근을 조사하고 지원 범위를 고정한다. `ct doctor`, `ct inspect`, `ct run`으로 환경·지원 범위·실행 오류를 제공한다.

통과: Driver API와 외부 PTX를 사용하는 기존 Windows x64 프로그램을 패치·재빌드하지 않고 B390에서 실행한다. NVIDIA 원본 환경과 CT 환경에서 실행 파일·PTX 해시가 동일해야 한다. 미지원 로딩 방식은 명시한다. 시스템 nvcuda.dll이나 제조사 드라이버를 덮어쓰지 않고 실행 단위로 격리하며, CT 제거와 NVIDIA 공존을 시험한다.

M0~M3 통과 시 v0.1 Intel alpha. 이것은 임의의 fatbin/cudart/AI 앱 지원을 뜻하지 않는다. 이전 로드맵의 양쪽 GPU 필수 v0.1 조건은 보유 장비에 맞춰 v0.2로 옮긴다.

### M4. AMD 백엔드 — v0.2 dual-vendor alpha

작업: AMD 실장비·OS·드라이버 고정 → 네이티브 실행 → CT 표현의 AMD 코드 생성·모듈 실행 → 공통 시험 전부 수행. Intel 구현을 특정 프로그램에 맞춘 분기 없이 재사용한다.

통과: 같은 OS·호스트 아키텍처의 동일한 CUDA 실행 파일·PTX를 양쪽 GPU에서 실행한다. 서로 다른 OS에서 각각 재빌드한 성공과 구분한다. AMD Windows 경로가 불가능하면 대체 OS 시험은 별도 결과로 남긴다. AMD 장비 미확보 시 미검증 상태로 유지한다.

### M5. 일반 프로그램 호환 확대

별도 하위 과제로 순서대로 진행: PTX 포함 fatbin 선택 → static/dynamic cudart·커널 등록 → primary context 공유·진입점 버전 협상 → 스트림·이벤트·비동기 복사 → shared memory·barrier·atomic·warp/subgroup 의미 → 외부 오픈소스 CUDA 앱 미수정 실행.

각 기능별 정확성·오류·실행 순서 시험 후 지원 표를 갱신한다. NVIDIA warp와 Intel/AMD subgroup 크기·메모리 모델을 동일하다고 가정하지 않는다.

### M6. 수학 라이브러리와 실제 AI

cuBLAS FP32 GEMM의 좁은 API 집합부터 대응 계산 라이브러리에 연결한다. 전치·leading dimension·배치·포인터 모드·정밀도·스트림·오류 의미를 시험한다. 작은 고정 MLP 추론 후 실제 AI 앱 한 개의 의존성을 조사한다.

PyTorch CUDA 패키지·cuDNN·TensorRT·NCCL은 각각 별도 호환 프로젝트로 계획한다. GEMM 성공을 전체 프레임워크 지원으로 확대 해석하지 않는다.

## 6. 첫 릴리스 제외 범위

PTX 없는 SASS/cubin 전용 프로그램, 모든 CUDA 버전, 32비트 앱, 전체 Unified Memory, 멀티 GPU, 동적 병렬 실행, CUDA Graphs, Tensor Core/MMA, 전체 AI 프레임워크는 v0.1 범위 밖이다. SASS 변환은 PTX 지원과 다른 장기 연구다. 장기 목표는 유지하되 기능별로 검증하며 확장한다.

## 7. 제안 코드 경계

```text
crates/ct-cuda-abi/       CUDA 타입·export·버전별 심볼
crates/ct-core/           컨텍스트·자원·공통 실행 계약
crates/ct-ptx/            PTX 파서·타입·지원 판정
crates/ct-ir/             타입·주소 공간·제어 흐름·인자 정보
crates/ct-codegen-spirv/  Intel 대상 코드 생성
crates/ct-backend-intel/  Level Zero 연동
crates/ct-backend-amd/    M4에서 구체화할 AMD 실행 경로
crates/ct-loader/         프로그램별 로딩 연결
crates/ct-cli/            doctor·inspect·run
tests/fixtures/          합성 PTX·호스트·정답
tests/conformance/       API·의미·오류·실장비 검증
benchmarks/              네이티브·CT 비교
docs/compatibility/      GPU·OS·API·PTX·라이브러리 지원 표
docs/decisions/          실험과 선택 근거
```

모든 빈 모듈을 미리 만들지 않는다. 해당 마일스톤에서 필요한 경계만 구현하며 AMD 코드 생성 방식은 M4 실행 경로 확정 후 추가한다.

## 8. 검증 계약

- 상태: pass / fail / skip / unsupported. GPU 부재는 skip이다.
- 정수 정확 일치. 초기 유한 FP32 원소 연산: `abs(actual-expected) <= 1e-5 + 1e-4*abs(expected)`를 제안. 행렬곱/reduction은 크기·누적 오차를 근거로 허용오차를 사전에 별도 정의한다. 실패 후 임의 완화 금지.
- NaN/Inf/부호 있는 0·FMA·반올림은 별도 의미 시험. 크기 0/1/블록 경계 전후/큰 비정렬 입력을 시험한다.
- 컨텍스트의 스레드 규칙, 포인터 정렬·인자 배치, 자원 해제, 비동기 완료 전에 해제하는 상황을 검증한다.
- 독립 CPU 정답, 가능한 경우 원본 NVIDIA, 실제 Intel·AMD 결과를 비교한다. 장치 실행 증거를 남긴다.
- 일반 CI는 파서·변환·오류 시험. 실제 GPU는 전용 장비에서 검토한 커밋으로 시험한다. 공개 PR 코드를 개인 runner에서 자동 실행하는 구성은 피한다.
- 성능은 첫 변환·캐시 재사용·전송·커널·전체 시간을 분리한다. 워밍업 5회·측정 30회로 시작해 중앙값과 변동을 보고한다. 같은 GPU의 네이티브 코드 대비 오버헤드를 주 비교값으로 쓴다.
- 캐시 키는 입력 코드·CT 버전·옵션·장치·드라이버/컴파일러를 포함한다. 잘못된 캐시 재사용 시험을 둔다.
- 결과에 CT 커밋·OS·GPU·드라이버·툴체인·입력 해시·실행 명령을 포함한다.

## 9. 위험과 설계 변경 기준

| 위험 | 대응 |
| --- | --- |
| Windows B390에서 Level Zero 불가 | M0에서 먼저 확인. OpenCL 등 대안이나 별도 OS 실험을 비교하고 실행 경로 결정을 수정 |
| PTX 포인터/주소 공간과 SPIR-V 의미 불일치 | 하부 ABI 실험 후 실제 포인터 산술·정렬·인자 시험. 의미 보존이 안 되면 코드 생성 설계 수정 |
| DLL export만으로 광범위 호환이라고 오인 | export 존재와 의미 검증 분리. Driver/Runtime/라이브러리/로더별 지원 표 |
| 병렬 의미 차이로 조용한 오답 | 기능별 의미 시험과 명시적 미지원. 임의 warp 크기 가정 금지 |
| 큰 목표로 개발 분산 | M3까지 Intel Driver API+PTX 집중. AMD·fatbin·AI 라이브러리는 후속 |
| 외부 코드·SDK 재배포 조건 | 채택 파일·버전·라이선스·NOTICE 기록. 제품 라이선스는 구현 공개 전 별도 확정 |

## 10. 다음 작업과 일정

첫 작업 묶음: 환경의 Level Zero·툴체인 읽기 전용 조사 → M0 상세 실행 계획 → B390 SPIR-V 실행·ABI 검증 → M1~M3 API/PTX/의존성 버전과 작업량 확정.

현시점에서 전체 CUDA 지원 완료 날짜나 동등한 성능을 약속하지 않는다. M0 결과로 Intel alpha의 작업량을 추정하고, M3 후 AMD·앱 확장 일정을 산정한다. 하부 실행이 실패하면 원인을 기록하고 설계를 수정한다.

현재 완료한 것은 목표 확인과 설계 문서 작성이다. 의존성 설치, CT 기능 코드, GPU 커널 실행은 아직 수행하지 않았다. 이 문서가 전체 설계 검토 대상이며, 승인 후 첫 하위 과제인 M0의 상세 구현 계획을 작성한다.

## 11. 공식 근거

2026-10-19 확인. 문서상의 기능과 CT 실장비 실행 증거는 다르다.

- NVIDIA Driver API·컨텍스트·모듈: https://docs.nvidia.com/cuda/cuda-programming-guide/03-advanced/driver-api.html
- NVIDIA 버전별 Driver 진입점: https://docs.nvidia.com/cuda/cuda-driver-api/cuda_driver_api/group__CUDA__DRIVER__ENTRY__POINT.html
- NVIDIA PTX ISA: https://docs.nvidia.com/cuda/parallel-thread-execution/
- Level Zero 모듈·SPIR-V: https://oneapi-src.github.io/level-zero-spec/level-zero/1.19.12/core/api/apis/module.html
- Level Zero 프로그래밍 가이드: https://oneapi-src.github.io/level-zero-spec/level-zero/latest/core/PROG.html
- Intel Linux 지원 표(B390 기재; Windows 실행 보장과 구분): https://dgpu-docs.intel.com/overview/supported-hardware/xe-driver-gpus.html
