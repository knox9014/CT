# CT (Cuda Translater)

CUDA 기반 프로그램을 Intel 및 AMD GPU에서도 실행할 수 있도록 하는 범용 변환·호환 계층을 목표로 하는 프로젝트입니다.

CT aims to develop a general-purpose translation and compatibility layer for running CUDA-based programs on Intel and AMD GPUs.

## Project status / 현재 상태

**Concept stage. No translator or compatibility runtime has been implemented.**

현재는 프로젝트 목표를 정리하는 초기 단계입니다. 실행 가능한 변환기, 런타임, 검증된 GPU 지원은 아직 없습니다.

## Development plan / 개발 계획

[CT CUDA 호환 드라이버 설계 및 개발 계획](docs/CT-DRIVER-DESIGN.md)은 검토용 초안입니다. CT 자체의 CUDA API/ABI, PTX 변환, 런타임과 백엔드를 개발하며 Arc B390에서 시작해 AMD와 실제 AI 프로그램으로 확장합니다. 제조사 드라이버 위에서 동작하는 사용자 공간 호환 계층이며, 제안된 기능은 아직 구현되지 않았습니다.

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
