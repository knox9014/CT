# Numba 후속 1단계: 실제 Intel 커널 자원 조회

2026-11-13. [새 실행 계획](superpowers/plans/2026-11-13-numba-kernel-resources.md)의 첫 묶음을 구현·검증했다. Backend의 raw metadata query와 현재 소스 기준점 확보가 범위다. CUDA 함수 속성 export, 정식 메모리 조회, linker 또는 원본 Numba 호환성을 완료한 것은 아니다.

## 구현

- `ct-level-zero::abi::KernelProperties`: 공식 `ze_kernel_properties_t`의 전체 layout. 32바이트 kernel/module UUID storage까지 포함하되 UUID는 진단 결과에 내보내지 않는다.
- `Backend::kernel_resources(context, module, entry)`: 살아 있는 module entry의 원시 자원을 조회한다. kernel argument/group size 설정, launch, CUDA 속성 변환은 수행하지 않는다.
- poison/dead/invalid entry 선행 거부, optional API 부재의 UNSUPPORTED, 실패 결과 차단, LOST/RESET의 기존 context poison/loader retention을 유지한다.
- 별도 Rust example과 공식 헤더 C++ consumer를 추가했다. 후자는 출력 구조체를 0xa5로 초기화해 성공 응답이 필드를 쓰지 않는 경우도 비교에서 드러나게 했다.
- README의 로컬 상태 설명과 PTX 문서의 식별자 길이·제한된 u64 분류·standalone common 선언을 현재 구현과 맞췄다. 기존 현황 분석은 당시 기록으로 보존했다.

## 실제 B390 조회

현재 소스가 생성한 같은 SPIR-V를 각각 Rust backend와 독립 official-header consumer에서 로드했다. 각 entry마다 별도 두 프로세스로 조회했으며, 세 entry의 모든 공개 필드가 일치했다. 이 6개 프로세스는 **metadata 조회**이며 kernel 계산이나 성능 시험으로 세지 않는다.

| 입력 | 인자 수 | native local bytes / group | private bytes / thread | native spill bytes | max subgroup size | max subgroup count |
| --- | --- | --- | --- | --- | --- | --- |
| synthetic `no_shared` | 1 | 0 | 0 | 0 | 32 | 32 |
| synthetic `with_shared` | 1 | 4096 | 0 | 0 | 32 | 32 |
| 저장된 원본 Numba `add_one` 생성 PTX | 7 | 0 | 0 | 0 | 32 | 32 |

세 entry 모두 required group dimensions `[0,0,0]`, required subgroup size/count `0`이었다. native local은 workgroup 메모리이며 CUDA의 thread-local memory와 혼동하면 안 된다. private/spill이 0이라는 관측으로 사용 register 수가 0이라고 결론 내릴 수 없다. 위 subgroup 값을 NVIDIA warp/occupancy 또는 함수별 CUDA 최대 thread 수로 자동 변환하지 않는다.

Numba 입력은 기존 `.cache/numba-0651/dxgi/numba-add-one.ptx`를 수정 없이 사용했다. SHA256은 `5334acfa9dc8e38daf95ba324d9fc842171b38936e65fb5ddcd2a1496cdb71f2`다. 이번 단계에서 Numba JIT 호스트 경로를 실행한 것이 아니다.

공식 Level Zero 헤더와 Rust의 **14개 구조체** 크기/정렬/필드 offset을 대조했다. 새 kernel properties는 size96/align8이며 모든 필드 offset이 일치한다. pinned v1.27.0 `ze_api.h` SHA256은 `3e7967d37ce79a472205c9cc230da837173ba390686bc4017e980e1290e40feb`이다.

별도로 이번 CT Driver DLL로 원본 Numba PTX의 실제 계산도 재실행했다. 길이1/16/37에서 정답54개와 guard96개가 일치했다. 이것은 custom Driver consumer의 계산 회귀이며 원본 Numba의 컨텍스트/메모리/link/함수 속성 경로를 대신하지 않는다.

새 fixture와 원본 Numba 입력에서 생성한 두 SPIR-V 모두 기존 pinned `spirv-val`의 OpenCL1.2 검증을 통과했다. 이 형식 검증도 CUDA 전체 의미론이나 계산 정답을 대신하지 않는다.

## 고정 소스와 회귀

제품/검증 입력 지문:

`fcc304dae665e49ce0cf7eb68f349ad9d8f45d61fcd9a861fd82618d07798be0`

743개 소스 파일의 private checkpoint를 생성해 원래 작업 트리의 index/HEAD를 바꾸지 않고 바이트·Git 객체·지문을 검증했다. private commit `8e74bd47139c2fb838d7532ab13cbc22a11956dd`, tree `500eb0325ac3cf5fa0066aa05f825d6286c940fe`다. 이는 로컬 별도 snapshot의 식별자이며 원래 저장소에 commit/push했다는 뜻이 아니다.

그 깨끗한 checkpoint에서 CPU lane **11/11**이 `clean=true`, `release_claim=false`로 통과했다. 기존 캐시/SDK를 snapshot 안에 복사하지 않았으며 이 PC에 설치된 컴파일러와 의존성 캐시는 사용했다. 다른 PC나 네트워크 없는 초기 설치 증거는 아니다.

- Rust workspace:231 통과, 실패0, 기존 ignored7.
- 별도 CT Runtime:129 통과, 실패0.
- Python:394 통과.
- 양 workspace의 format/Clippy, registry/Driver·Runtime profiles, 실제 working-tree publication 검사 통과.
- 새 focused tests4개는 API/타입 부재의 실패를 먼저 확인한 뒤 구현 후 통과했다. backend 전체47개도 통과했다.

native capture와 clean CPU report는 같은 `fcc304da...` 소스를 가리킨다. checkpoint 이후 이 결과 문서와 계획 체크 상태를 추가하는 reporting-only 변경은 제품 지문을 바꾸지 않는다. 과거 matrix/공식 Runtime 전체 native parent chain을 이 새 소스로 다시 통과시킨 것은 아니다.

저장 위치:

- `.cache/numba-kernel-resources-2026-11-13/native-capture.json`: native 결과, source fingerprint, PTX/SPIR-V/실행 파일/header SHA256.
- `.cache/numba-kernel-resources-2026-11-13/`: RED/GREEN, backend/workspace/Runtime/Python, ABI/native/계산 회귀, build logs와 ledger.
- `.cache/source-candidates/005f12c7d83e46e09538d6557a6e0388/manifest.json`: private checkpoint manifest.
- 위 candidate의 `source/results/local/numba-kernel-resources-2026-11-13/`: clean CPU report/configuration/environment/logs.

독립 read-only 검토에서 구현상 actionable finding은 보고되지 않았다. reviewer는 테스트/native를 재실행하지 않았고 소스와 기존 증거를 검토했다. PTX 문서의 남은 pointer-only 문장 한 곳을 지적해 현재 classifier와 대조한 뒤 정정했다. 전 경로 무결함 증명이나 CUDA 적합성 심사는 아니다.

## 저장공간과 작업 보존

앞선 분석의 두 전용 CPU target 안에서 PDB45개만 목록·SHA256을 기록하고 제거해393457664바이트를 회수했다. 그 분석의 DLL/EXE/로그와 과거 native closure는 보존했다. 삭제 경로는 workspace 내부의 해당 두 target으로 검증했고 reparse ancestor와 변경된 bytes를 거부했다. cache guard는 다시 통과했다.

이번 CPU build는 일반 `target/` 아래 전용 nonincremental 경로를 사용한다. 이는 기존 cache guard가 모든 Cargo 출력을 제한한다는 뜻이 아니다. 디스크 free floor도 확인했으며, 기존 GPU evidence를 임의로 옮겨 한도 검사를 우회하지 않았다. 외부 업로드, root stage/commit/push 또는 기존 worktree 변경은 하지 않았다.

## 재현 진입점

프로젝트 root에서 다음 명령으로 fixture를 번역하고 raw resource query를 실행할 수 있다. Windows x64의 Rust/MSVC와 Intel Level Zero가 필요하며 이 example은 B390 하나가 정확히 선택되는 환경을 요구한다.

```powershell
cargo run -p ct-codegen-spirv --example translate_module -- tests/fixtures/kernel_resources.ptx .cache/kernel_resources.spv
cargo run -p ct-backend-intel --example kernel_resources -- .cache/kernel_resources.spv no_shared
cargo run -p ct-backend-intel --example kernel_resources -- .cache/kernel_resources.spv with_shared
```

독립 소비자는 `tests/kernel_resources_native.cpp`를 pinned `ze_api.h`와 MSVC C++17로 빌드한다. 인자는 `INPUT.spv ENTRY`이며 로더는 Windows System32에서만 연다. 새 ABI는 기존 `scripts/check_level_zero_abi.ps1`의 C/Rust 대조에도 포함된다. 위 recipe 실행은 과거 고정 capture를 자동으로 갱신하거나 공식 앱 지원으로 등록하지 않는다.

## 다음 구현 판단

이번에 Numba 함수 메타데이터의 근거 일부를 확보했다. 다만 설치된 Numba0.65.1은 함수 생성 시 NUM_REGS를 먼저 요청하고, 이어 constant/local/shared/maxthreads를 요구한다. 기본 `zeKernelGetProperties`에는 CUDA식 register count가 없다. 따라서 이 raw query만 추가해 `cuFuncGetAttribute`를 임의의 값으로 성공시키지 않았다.

다음 단계는 native compiler/module metadata에 검증 가능한 register 자원이 있는지, 그 단위를 CUDA per-thread32-bit register로 변환할 근거가 있는지 확인하는 것이다. 없으면 해당 CUDA 속성은 계속 미지원으로 두고, Numba의 공식 확장 경로나 명시적 어댑터를 별도로 검토한다. 이것은 이번 단계에서 구현하지 않은 후속 결정이다.

`cuMemGetInfo`, 정식 JIT linking, 다른 Intel PC/장치, 일반 워크로드와 실용 성능은 여전히 별도 미완료 항목이다. 함수 속성 한 항목이 해결돼도 원본 Numba 전체 실행이 자동으로 성공한다고 예측하지 않는다.

공식 의미 참조: [Level Zero kernel properties](https://oneapi-src.github.io/level-zero-spec/level-zero/1.20.41/core/api/apis/kernel.html), [CUDA function attributes](https://docs.nvidia.com/cuda/cuda-driver-api/cuda_driver_api/group__CUDA__EXEC.html). 문서상의 기능과 현재 장치에서 실제 조회한 결과를 구분한다.
