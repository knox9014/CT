# CT (Cuda Translater)

CUDA 기반 프로그램을 Intel 및 AMD GPU에서도 실행할 수 있도록 하는 범용 변환·호환 계층을 목표로 하는 프로젝트입니다.

CT aims to develop a general-purpose translation and compatibility layer for running CUDA-based programs on Intel and AMD GPUs.

## Project status / 현재 상태

**Concept stage. No translator or compatibility runtime has been implemented.**

현재는 프로젝트 목표를 정리하는 초기 단계입니다. 실행 가능한 변환기, 런타임, 검증된 GPU 지원은 아직 없습니다.

## Development plan / 개발 계획

[CT 개발 전략 및 단계별 계획](docs/CT-ROADMAP.md)은 검토용 설계 초안입니다. 기존 엔진 평가, Intel·AMD GPU 실행 검증, PTX 기반 최소 호환 계층, 라이브러리 및 AI 워크로드 확장 순서를 다룹니다. 제안된 기능은 아직 구현되지 않았습니다.

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
