# Numba Kernel Resources Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement task-by-task. 사용자 요청대로 이 세션에서 자율 실행한다.

**Goal:** Intel의 실제 커널 자원 조회를 검증하고 Numba 함수 속성 구현의 근거와 남은 경계를 기록한다.

**Architecture:** 기존 Level Zero ABI에 kernel properties layout을 추가한다. Backend는 module 소유 kernel을 조회하며, 진단 executable과 official-header native consumer가 같은 SPIR-V의 결과를 대조한다. CUDA export와 기존 실험 DLL은 변경하지 않는다.

**Tech Stack:** Rust, Level Zero v1.27.0 header, Windows x64 MSVC, Python validation.

**Spec:** `docs/superpowers/specs/2026-11-13-numba-kernel-resources-design.md`

## 장기 진행 순서

1. 현재 기준점·문서 정합성 확보와 actual kernel resources 검증: 이번 실행 범위.
2. native 결과를 바탕으로 CUDA 함수 속성별 표현 가능성 결정. NUM_REGS, occupancy, local/spill 범위가 불명확하면 명시적 미지원.
3. 메모리 조회의 OS/장치 출처와 Numba 최소 실행에서의 필수 소비를 검증. 프로세스 예산은 별도 정책으로 유지.
4. PTX link의 입력/출력/소유권 계약을 확정한 후 구현 여부 결정. 기존 시험 DLL은 계속 실험.
5. 원본 Numba의 실제 작업, 현재 소스 고정 native 회귀, 다른 Intel PC, 성능 순서로 확대.

후속 2~5는 조사 결과에 따라 별도 구현 계획으로 구체화한다. 이번 1의 완료가 전체 계획 완료는 아니다.

## Global Constraints

- 기존 modified/untracked 작업 보존, git stage/commit/push 없음.
- 원시 자원을 CUDA 호환 속성으로 단정하지 않음. UUID 외부 출력 금지.
- 기존 native closure 보존. 이번 분석의 전용 PDB 외 임의 cache 삭제 금지.
- 제품 코드는 실패 테스트 확인 후 구현. native 검증은 직렬 실행.

## Review Focus

- poison/LOST/RESET 후 추가 native work가 일어나지 않는가.
- 잘못된 entry와 zero/dead kernel이 native query 전에 거부되는가.
- raw private/spill/subgroup 값을 CUDA 단위로 오해하게 표시하지 않는가.
- ABI가 전체 UUID storage와 모든 필드 offset을 포함하는가.
- optional symbol 부재/실패에서 zero를 성공값으로 만들지 않는가.

### Task 1: 기준점과 저장공간

- [x] 변경 예정 기존 파일을 hash와 함께 scratch에 복사한다.
- [x] 앞선 분석의 두 전용 target 안에서 PDB inventory/hash를 기록하고 해당 PDB만 제거한다. DLL/EXE/로그는 유지한다.
- [x] cache guard와 disk free를 확인하고, 전용 Cargo 출력 경로 및 기준 지문을 ledger에 기록한다.

### Task 2: native resource query

**Files:** `crates/ct-level-zero/src/abi.rs`, `crates/ct-backend-intel/src/{lib.rs,fault_tests.rs,kernel_resources.rs}`.

- [x] backend fault tests에 성공 값 보존, invalid/dead/poison 선행 거부, optional symbol 부재, OOM/UNSUPPORTED/LOST/RESET를 추가하고 실패를 확인한다.
- [x] `KernelProperties` ABI storage와 spec의 `KernelResources`/`Backend::kernel_resources`를 구현한다.
- [x] focused tests와 backend 전체 테스트를 통과시킨다.

### Task 3: ABI와 실제 장치 대조

**Files:** `tests/abi_layout.c`, `tools/ct-intel-smoke/src/bin/ct-abi-layout.rs`, `crates/ct-backend-intel/examples/kernel_resources.rs`, `tests/kernel_resources_native.cpp`, `tests/fixtures/kernel_resources.ptx`.

- [x] 공식 header와 Rust의 struct layout을 전체 대조한다.
- [x] native example은 SPIR-V 경로와 entry를 받아 raw kernel fields만 출력하고 자원을 정리한다. CUDA 매핑이나 성능 주장을 넣지 않는다.
- [x] 같은 입력의 zero/nonzero shared entries를 B390에서 official-header consumer와 별도 프로세스로 대조한다. 모든 필드와 source/artifact hashes를 기록한다.

### Task 4: 회귀·검토·후속 결정

- [x] Rust workspace, 별도 Runtime, Python, 관련 Clippy/format 및 registry/publication 검사를 실행한다.
- [x] 새 소스로 Driver PTX 계산을 재실행해 메타데이터 변경이 기존 계산 경로를 깨뜨리지 않았는지 확인한다.
- [x] scoped fresh review를 받고 actionable finding을 수정·검증한다.
- [x] 결과 문서와 README/PTX 계약의 관련 오래된 설명을 정정하고 실제 값에 근거한 다음 구현 순서를 기록한다.

## 이번 실행 결과

첫 묶음 완료. [실제 결과와 한계](../../NUMBA-KERNEL-RESOURCES-RESULTS.md). 후속 장기 단계2~5는 미완료이며 이 체크 상태는 위 Task1~4에만 적용한다.
