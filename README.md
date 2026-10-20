# CT (Cuda Translater)

CUDA 기반 프로그램을 Intel 및 AMD GPU에서도 실행할 수 있도록 하는 범용 변환·호환 계층을 목표로 하는 프로젝트입니다.

CT aims to develop a general-purpose translation and compatibility layer for running CUDA-based programs on Intel and AMD GPUs.

## Project status / 현재 상태

**M3i: deterministic native-failure containment probes passed. M3h / P03a 2D/3D CUDA execution remains verified on Intel Arc B390.**

현재는 초기 개발 단계입니다. Windows의 Intel Arc B390에서 제한된 PTX를 SPIR-V로 번역해 실제 GPU에서 실행합니다. 벡터 덧셈·SAXPY·ReLU·행렬 곱셈 4개 커널의 53개 조합에서 출력 606,660개와 가드 값 4,992개를 검증했습니다. API는 26개 심볼이며, M1 메모리·컨텍스트 검사 210개도 통과했습니다. 외부 CUDA 앱의 일반적인 호환성, CUDA 라이브러리 및 AMD 지원은 아직 확보하지 못했습니다.

[M0 실행 결과와 재현 방법](docs/M0-RESULTS.md) · [검증 환경](docs/environment-matrix.md) · [실행 경로 결정](docs/decisions/0001-intel-execution-path.md)

[M1 실행 결과와 재현 방법](docs/M1-RESULTS.md) · [Driver API 지원 범위](docs/compatibility/driver-api.md) · [공개 자료 보호 규칙](docs/PUBLICATION.md)

[M2 실행 결과와 재현 방법](docs/M2-RESULTS.md) · [지원하는 PTX 문법과 제한](docs/compatibility/ptx-profile.md)

M3a에서는 일반 `nvcuda.dll` import 및 동적 로딩을 쓰는 독립 합성 프로그램 두 개를, 실행 파일 수정 없이 CT에 연결해 GPU 계산을 검증했습니다. 아직 외부 앱·NVIDIA 원본 실행 비교를 통과한 것은 아닙니다. [M3a 실행 결과](docs/M3a-RESULTS.md) · [CUDA 프로그램 연결 목표](docs/CUDA-CONNECTION.md)

M3b에서는 NVIDIA 공식 헤더로 컴파일한 독립 프로그램이 구형·신형 `cuGetProcAddress`를 통해 함수 주소를 얻어 GPU 계산을 수행했습니다. 조회 80회, 출력 514개·가드 128개 검증을 통과했습니다. [M3b 실행 결과](docs/M3b-RESULTS.md) · [버전별 조회 지원 범위](docs/compatibility/driver-entrypoints.md)

M3c에서는 NVIDIA 공식 `vectorAddDrv`의 호스트·커널 소스를 수정하지 않고 빌드해 50,000개 원소 검사를 통과했습니다. 원본 커널을 NVRTC로 컴파일한 PTX를 예상 `.fatbin` 파일명에 제공한 조정 시험이며, 실제 바이너리 fatbin 지원은 아닙니다. 독립 GPU 검사 14개 조합에서 출력 50,970개·가드 896개도 검증했습니다. [공식 샘플 시험·조정 내역](docs/M3c-RESULTS.md)

M3d에서는 같은 공식 호스트에 NVIDIA `nvFatbin`이 만든 실제 바이너리 fatbin을 제공해 50,000개 검사를 통과했습니다. fatbin을 통한 독립 검사 6개 크기에서 결과 50,450개·가드 384개도 검증했습니다. 당시에는 압축하지 않은 PTX 모듈 하나를 지원하고 압축·복수 PTX·추가 JIT 옵션은 거부했습니다. [실제 fatbin 검증 결과](docs/M3d-RESULTS.md) · [지원 형식](docs/compatibility/fatbin-profile.md)

M3e에서는 CT 내부의 크기 제한을 둔 압축 해제기로 실제 압축 PTX fatbin도 처리합니다. 공식 샘플 50,000개 검사, 압축 입력의 독립 출력 50,450개·가드 384개와 이름·연산을 바꾼 커널 검사를 통과했습니다. M3d의 압축 거부 제한은 해제됐으며, 복수 PTX·JIT 옵션·CUDA Runtime·AMD 지원은 아직 확보하지 못했습니다. [압축 fatbin 검증 결과](docs/M3e-RESULTS.md)

M3f에서는 알려진 두 프로파일의 대체 PTX를 검증하고 순서에 관계없이 선택합니다. 실제 Arc의48개 조합에서 출력403,600개·가드3,072개, 오류6종 거부·복구와 모듈 생성/해제1,000회를 통과했습니다. 같은 entry와 인자 종류를 가진 서로 다른 프로파일만 허용하며, 알 수 없는 프로파일·복수 entry·링킹은 아직 지원하지 않습니다. 기능 추적표 검증과 실제 실행 결과도 분리했습니다. [M3f 결과](docs/M3f-RESULTS.md)

M3g에서는 하나의 모듈에 최대32개 kernel entry를 담고 각각 조회·실행합니다. 덧셈·뺄셈·다른 인자 ABI의 채우기 커널을 실제 Arc144개 조합에서 실행해 출력1,210,800개·가드9,216개를 검증했습니다. 모듈·컨텍스트별 핸들 수명, 부분 생성/해제 실패 시험, 독립 CUDA C 소비자와 공개 CLI도 통과했습니다. 아직 제한된 문법·동기1D 실행이며 저장된 전역 변수·device 함수·Runtime·AMD는 지원하지 않습니다. [M3g 결과](docs/M3g-RESULTS.md)

## Development plan / 개발 계획

M3i에서는 실제 GPU를 중단시키지 않고 native 오류를 주입해 실패 보고·후속 연산 차단·자원 보존을 검사했습니다. 설정/할당 단계의 치명적 오류와 해제·빌드 로그 정리 실패 처리를 보완했고 Rust64개·Python19개 및 실제 Arc 정상 경로가 통과했습니다. 오류 주입은 테스트 빌드에만 포함되며 실제 드라이버 재시작·자동 복구는 검증하지 않았습니다. [M3i 결과](docs/M3i-RESULTS.md)

M3h에서는 CUDA grid/block의 세 축과12개 좌표 레지스터를 연결했습니다. 실제 Arc26개 사례에서 출력37,394개·가드4,856개, 잘못된 크기 거부·복구, 별도 C 소비자의2D/3D 실행과 CLI 연결을 통과했습니다. P03의 첫 하위 작업이며 정수 연산·인자 형식 확장은 남아 있습니다. [M3h 결과](docs/M3h-RESULTS.md)

[범용 CUDA 번역기의 전체 구현 목표와 완료 기준](docs/CT-COMPLETION-GOALS.md)에 현재 위치, 남은 기능, 개발 순서와 출시 조건을 정리했습니다.

[작업별 의존성과 검증 문턱](docs/CT-EXECUTION-ROADMAP.md) · [첫 구현 상세 계획](docs/superpowers/plans/2026-10-19-m3f-selection.md) · [계획 검토](docs/CT-PLAN-REVIEW.md)

[CT CUDA 호환 드라이버 설계 및 개발 계획](docs/CT-DRIVER-DESIGN.md)에 따라 CT 자체의 CUDA API/ABI, PTX 변환, 런타임과 백엔드를 개발하며 Arc B390에서 시작해 AMD와 실제 AI 프로그램으로 확장합니다. 제조사 드라이버 위에서 동작하는 사용자 공간 호환 계층을 목표로 합니다. 현재 M0 네이티브 실행, M1 메모리·컨텍스트 ABI와 M2의 제한된 PTX 번역·커널 실행을 검증했습니다.

## Goals / 목표

- Reduce the work needed to adapt CUDA-based software for Intel and AMD GPUs.
- Serve multiple CUDA applications, including AI workloads, rather than a single model.
- Publish supported operations, hardware, correctness results, and performance measurements as implementation progresses.

## Next priorities / 다음 과제

- Expand process-local CUDA application loading and versioned Driver entry points.
- Validate an external unchanged application and compare against NVIDIA execution.
- Extend PTX, CUDA Runtime and library coverage with reproducible checks.
- Implement and verify an AMD backend on physical hardware.

Full CUDA compatibility and performance parity are long-term research questions, not current capabilities or guarantees.

구현 범위와 기술 선택은 조사·설계·실험을 통해 결정합니다. 현재 모든 CUDA 프로그램의 실행이나 동등한 성능을 보장하지 않습니다.
