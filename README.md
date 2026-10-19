# CT (Cuda Translater)

CUDA 기반 프로그램을 Intel 및 AMD GPU에서도 실행할 수 있도록 하는 범용 변환·호환 계층을 목표로 하는 프로젝트입니다.

CT aims to develop a general-purpose translation and compatibility layer for running CUDA-based programs on Intel and AMD GPUs.

## Project status / 현재 상태

**M2: restricted PTX translation and GPU execution verified on Intel Arc B390.**

현재는 초기 개발 단계입니다. Windows의 Intel Arc B390에서 제한된 PTX를 SPIR-V로 번역해 실제 GPU에서 실행합니다. 벡터 덧셈·SAXPY·ReLU·행렬 곱셈 4개 커널의 53개 조합에서 출력 606,660개와 가드 값 4,992개를 검증했습니다. API는 24개 심볼이며, M1 메모리·컨텍스트 검사 210개도 통과했습니다. 일반 CUDA 프로그램 로딩, CUDA 라이브러리 및 AMD 지원은 아직 구현되지 않았습니다.

[M0 실행 결과와 재현 방법](docs/M0-RESULTS.md) · [검증 환경](docs/environment-matrix.md) · [실행 경로 결정](docs/decisions/0001-intel-execution-path.md)

[M1 실행 결과와 재현 방법](docs/M1-RESULTS.md) · [Driver API 지원 범위](docs/compatibility/driver-api.md) · [공개 자료 보호 규칙](docs/PUBLICATION.md)

[M2 실행 결과와 재현 방법](docs/M2-RESULTS.md) · [지원하는 PTX 문법과 제한](docs/compatibility/ptx-profile.md)

## Development plan / 개발 계획

[CT CUDA 호환 드라이버 설계 및 개발 계획](docs/CT-DRIVER-DESIGN.md)에 따라 CT 자체의 CUDA API/ABI, PTX 변환, 런타임과 백엔드를 개발하며 Arc B390에서 시작해 AMD와 실제 AI 프로그램으로 확장합니다. 제조사 드라이버 위에서 동작하는 사용자 공간 호환 계층을 목표로 합니다. 현재 M0 네이티브 실행, M1 메모리·컨텍스트 ABI와 M2의 제한된 PTX 번역·커널 실행을 검증했습니다.

## Goals / 목표

- Reduce the work needed to adapt CUDA-based software for Intel and AMD GPUs.
- Serve multiple CUDA applications, including AI workloads, rather than a single model.
- Publish supported operations, hardware, correctness results, and performance measurements as implementation progresses.

## Open design questions / 설계할 사항

- Source translation, runtime compatibility, or a combination of both.
- Initial CUDA API and kernel subset.
- Target backends, operating systems, and GPU models.
- Compatibility with libraries used by AI frameworks.
- Reproducible correctness tests and performance comparisons.

Full CUDA compatibility and performance parity are long-term research questions, not current capabilities or guarantees.

구현 범위와 기술 선택은 조사·설계·실험을 통해 결정합니다. 현재 모든 CUDA 프로그램의 실행이나 동등한 성능을 보장하지 않습니다.
