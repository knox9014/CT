# Numba 진행을 위한 실제 커널 자원 조회

사용자는 현황 분석 후 새 계획과 자율 진행을 요청했다. 현재 제품 DLL의 Numba 경로는 `cuMemGetInfo`에서 막히며, 기존 JIT 실험은 메모리/링크 시험 DLL과 함수 속성 어댑터를 필요로 한다. 목적은 우회를 정식 호환성으로 편입하지 않고, 다음 구현 판단에 필요한 실제 Intel 커널 자원을 확보하는 것이다.

## 선택과 범위

- 메모리 예산을 CUDA 전체 가용량으로 반환하는 방법은 의미가 검증되지 않아 선택하지 않는다.
- 시험용 PTX 전달을 CUDA cubin linker로 편입하는 방법도 출력 계약의 차이 때문에 선택하지 않는다.
- **선택:** Level Zero `zeKernelGetProperties`의 실제 결과를 조회하는 backend 기능과 독립 native 검증을 먼저 만든다. 현재 실행 환경에서 확보되는 값과 CUDA로 매핑할 수 없는 값을 분리한다.

첫 실행 묶음은 native kernel resource query, 실패/수명 테스트, official-header ABI 대조, 서로 다른 정적 shared 요구를 가진 커널의 실제 조회까지다. CUDA 함수 속성 export는 이 묶음에서 추가하지 않는다. raw Intel 자원 조회를 Numba 지원 완료로 표시하지 않는다.

## 계약

- Windows x64, 현재 Intel backend 구조와 기존 오류 격리 정책을 유지한다.
- `Backend::kernel_resources(&self, context: &mut Context, module: &Module, entry: usize) -> NativeResult<KernelResources>`.
- 결과는 `num_kernel_args`, `required_group_size: [u32; 3]`, `required_num_subgroups`, `required_subgroup_size`, `max_subgroup_size`, `max_num_subgroups`, `local_mem_bytes`, `private_mem_bytes`, `spill_mem_bytes`를 원시 u32 값으로 보존한다.
- UUID는 ABI storage에만 포함하고 외부 결과에서 제외한다. raw values를 CUDA register count/max threads/local-memory로 이름만 바꾸지 않는다.
- poisoned context는 UNKNOWN, 잘못된 entry/비활성 module/kernel은 BAD_ARGUMENT이며 native 호출 전에 거부한다.
- optional query symbol 부재는 UNSUPPORTED. 조회 실패는 출력 값을 반환하지 않는다. LOST/RESET은 기존 `Context::observe`를 통해 poison/loader-retention 처리한다. 일반 unsupported/OOM은 자동 poison하지 않는다.
- 조회는 커널 인자나 group size를 설정하지 않고 launch를 제출하지 않는다.
- native handles의 context/module 소유권은 기존 backend와 동일하게 상위 계층 책임이다. 이번 API는 native kernel handle을 공개하지 않는다.

## 검증

fake foreign-call boundary에서 성공 필드 전달, entry 범위/zero handle/poison, symbol 부재, recoverable/fatal 실패와 호출 횟수를 검사한다. 공식 pinned `ze_api.h`로 C와 Rust의 크기/정렬/모든 필드 offset을 비교한다. 실제 B390에서 같은 SPIR-V 입력에 대해 backend와 official-header consumer 결과를 비교하고, zero/nonzero shared workload를 구분한다. 이 검증은 메타데이터 조회이며 계산/성능 검증과 구분한다.

## 작업 보존과 실행 선택

기존 dirty checkout에는 최신 미커밋 구현이 있으므로 이 실행은 현재 feature branch에서 기존 파일을 보존하면서 진행한다. 과거 HEAD로 새 worktree를 만들면 최신 구현이 빠지므로 선택하지 않는다. 이 작업의 변경 전 파일 해시/복사본과 실행 ledger를 무시되는 로컬 scratch에 둔다. git index/HEAD/기존 worktree와 과거 native closure는 수정하지 않는다. 사용자에게 중간 선택/승인을 반복 요청하지 않는다.

현재 cache ceiling 초과는 앞선 분석에서 생성한 두 전용 CPU target의 PDB만 inventory/hash 후 제거해 완화한다. DLL/EXE/로그와 과거 작업의 파일은 보존한다. 새 CPU 출력은 일반 `target/` 아래 전용 nonincremental 위치를 사용하고, 실제 disk-free floor와 cache guard를 함께 확인한다. 이 선택은 cache guard가 모든 Cargo 출력을 관리한다는 주장이 아니다.

## 참조

- [현황 분석](../../CT-STATUS-ANALYSIS-2026-11-13.md)
- [Level Zero kernel properties](https://oneapi-src.github.io/level-zero-spec/level-zero/1.20.41/core/api/apis/kernel.html)
- [CUDA function attributes](https://docs.nvidia.com/cuda/cuda-driver-api/cuda_driver_api/group__CUDA__EXEC.html)
- 로컬 `.cache/reference/ze_api.h`: 기존 v1.27.0 pinned header. 외부 문서와 설치된 드라이버 기능을 동일시하지 않는다.
