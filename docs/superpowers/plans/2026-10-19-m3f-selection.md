# CT P00/P01 M3f Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking. Preserve the existing inline execution method; this document does not start execution.

**Goal:** 현재 기능을 추적 가능하게 고정하고, 제한된 복수 PTX fatbin을 결정적으로 선택해 Arc에서 실행한다.

**Architecture:** dependency-free fatbin decoder는 후보와 메타데이터만 반환한다.
PTX parser/codegen은 본문 프로파일을 보존한다. CUDA image 계층은 모든 후보의 구문·타입·ABI를
검증해 하나를 선택하고 기존 backend에 한 번만 전달한다.

**Tech Stack:** 기존 Rust workspace, Python 표준 라이브러리, PowerShell/MSVC, Level Zero;
NVIDIA nvFatbin12.4.99는 ignored 시험 producer로만 사용한다.

**Spec:** [M3f selection design](../specs/2026-10-19-m3f-selection-design.md).
**Parent roadmap:** [P00~P25](../../CT-EXECUTION-ROADMAP.md).

**Execution status:** 사용자 승인 후 P00/P01을 구현·Arc 검증했다. 실패/성공·공식 호스트의
복수 이미지 연결·독립 리뷰와 미검증 항목은 [M3f 결과](../../M3f-RESULTS.md)를 따른다.

## Global Constraints

- 시작 구현은 M3e `4b0c64f`의 의미를 보존한다. 계획 문서의 미커밋 변경도 보존한다.
- Windows x64/Arc B390, PTX7.0/sm_50 및8.0/sm_52만 지원 조합이다.
- image16MiB, 전체record256, PTX후보8, 본문256KiB, 누적 해제/padded 크기1,048,576 bytes.
- 각 압축 후보의 declared size를 기존 누적 크기에 더해 검사한 후 그 후보를 해제한다. overflow=Invalid, 자원 cap=Unsupported.
- 단일 모듈/entry 대체 이미지 선택이며 모듈 연결·여러 entry·알 수 없는 프로파일 skip은 하지 않는다.
- entry와 ParamKind 순서가 같고 프로파일이 서로 다른 후보만 허용한다. 이름/해시별 커널 치환 금지.
- 명시적 우선순위8.0/sm_52 > 7.0/sm_50, native load는 선택된 후보 한 번만 수행한다.
- native 실패 뒤 낮은 후보 fallback 금지; parser/selection 실패는 null handle과 사용 가능한 context.
- CUDA export26개 유지. Runtime/AMD/새 Driver 버전 지원을 광고하지 않는다.
- vendor/binary/raw log는 ignored; 공개 staged/history/identity 검사. main 자동 병합 금지.
- 이 계획의 검토는 구현/성능/새 하드웨어 실행의 성공 증거가 아니다.

## Review Focus

1. 선택되지 않는 압축 후보로 메모리 cap 우회: Task2의 누적 declared-size 시험.
2. metadata와 PTX 본문의 profile 불일치: Task3/4의 불일치218 시험.
3. 같은 이름이지만 다른 ABI/중복profile: Task4의 거부 시험; 의미 동등성은 주장하지 않음.
4. native 실패 후 조용한 다른 코드 실행: Task4의 단일 선택 구조, Task5의 선택 의미 GPU 시험.
5. 기능 manifest를 실행 pass로 오인/개인 경로 포함: Task1의 상태·참조 검증, Task5 공개 검사.

## File Structure and Interfaces

| 파일 | 역할/변경 |
| --- | --- |
| docs/compatibility/profile-v1.json (신규) | schema1, baseline, 환경, exports/features/제한/시험 참조 |
| scripts/check_compatibility_profile.py (신규) | pure validator와 고정 registry CLI, 성공은 manifest 유효성만 의미 |
| tests/test_compatibility_profile.py (신규) | P00 schema/export/참조/상태 오류 시험 |
| crates/ct-fatbin/src/lib.rs | 후보 API와 cap; 기존 단일 추출 wrapper 유지 |
| crates/ct-fatbin/tests/decoding.rs | 다중 후보·자원·기존 wrapper 회귀 |
| crates/ct-ptx/src/lib.rs, src/parser.rs | Profile과 Kernel.profile 보존 |
| crates/ct-ptx/tests/compiler_profile.rs | 본문 profile 반환과 기존 거부 규칙 |
| crates/ct-codegen-spirv/src/lib.rs, tests/translation.rs | Compiled.profile 전달 |
| crates/ct-cuda/src/images.rs (신규) | C input 판별/후보 변환/순수 선택 및 단위 시험 |
| crates/ct-cuda/src/lib.rs, src/modules.rs | images 모듈과 기존 module API 연결 |
| tests/m3f_selection_check.py (신규) | 실제 producer·선택 의미·실패/복구/byte 보존 검사 |
| tests/m3d_fatbin_check.py | Producer.make_many만 추가; 기존make/검사 유지 |
| tests/m3c_gpu_validation.py | Device에 선택적dll_path를 추가해 baseline/현재 DLL을 각각 명시적으로 검사 |
| scripts/run_m3f_smoke.ps1 (신규) | build, m3f 검사, 기존 공식 샘플 경로 호출 |
| docs/M3f-RESULTS.md (신규) 및 기존지원표/README | 실제 결과와 제한 갱신; 계획 수치를 통과 결과로 전사하지 않음 |

### Task 1: P00 기능 추적표와 validator

**Consumes:** include/ct_cuda.h, 기존 Driver/PTX/fatbin/entrypoint 지원표 및 시험 소스.
**Produces:** `validate_profile(data: dict, root: pathlib.Path) -> list[str]` in
scripts/check_compatibility_profile.py. 빈 목록=유효한 manifest, GPU 통과를 뜻하지 않는다.
CLI는 고정 repo profile-v1.json을 읽고 errors이면 exit1, 성공이면 exit0.

- [x] **Step 1: 실패 시험 작성.** test_compatibility_profile.py에
  `test_rejects_export_signature_drift`, `test_rejects_missing_or_escaping_test_reference`,
  `test_manifest_cannot_claim_execution_pass`, `test_current_profile_is_explicitly_bounded` 추가.
  schema1/export26·중복 없음, signature_id가 헤더 인자 목록의 whitespace 정규화와 일치함,
  `cuDriverGetVersion`의 behavior=NOT_SUPPORTED, schema의 features.state가
  experimental/unsupported만 허용됨을 assert한다. supported/pass를 넣으면 errors가 있어야 한다.
- [x] **Step 2: RED 확인.** `python -m unittest discover -s tests -p test_compatibility_profile.py`.
  신규 validator/manifest 부재로 실패함을 확인.
  첫 Rust 변경 전에 `git diff 4b0c64f -- crates include`가 비어 있음을 확인하고,
  `cargo build -p ct-cuda`로 기준 DLL을 만든다. `.cache/m3f-baseline/ct_cuda.dll`에 복사해
  SHA-256과 기준commit을 ignored 기록에 남긴다. Rust 차이가 있으면 기존 작업을 지우지 말고
  별도 baseline checkout에서 빌드한다. 이후 native RED는 이 보존 DLL로 실행한다.
- [x] **Step 3: 구현.** JSON 필수 필드 schema_version/baseline/platform/exports/features.
  export는 symbol/signature_id/lookup_ranges/behavior/test_ids를 갖는다. signature_id는
  `symbol + ':' + normalized_header_args`; lookup_ranges는 실제 entrypoints.rs의 지원 구간을 전사.
  feature는 id/state/limits/test_ids, unsupported면 reason도 필수다. test_ids는
  `repo-relative-path#source-marker`; path가 repo 내부의 실제 파일이고 marker가 그 파일에
  존재해야 한다. 비어 있는 experimental 근거는 거부한다. 이것은 정적 참조 검증이며 실행 증명이 아니다.
  profile-v1의 실제 의미는 기존 지원표에서 옮긴다. vendor 파일/개인 절대 경로를 참조하지 않는다.
- [x] **Step 4: GREEN 확인.** 위 unittest와 `python scripts/check_compatibility_profile.py` exit0.
  기존 Python suite도 통과. 검증 결과 메시지는 정적 manifest 검증이라고 명시한다.
- [x] **Step 5: commit.** 세 신규 파일만 staged 공개 검사 후
  `test(compat): track bounded CT profile and evidence references`.

### Task 2: 안전한 다중 fatbin 후보 추출

**Consumes:** 기존 Error, Cow, ptx_record와 metadata/LZ4 검증.
**Produces:** ct-fatbin의 공개 타입과 함수:

```rust
pub struct PtxProfile { pub major: u16, pub minor: u16, pub target: u32 }
pub struct PtxCandidate<'a> { pub profile: PtxProfile, pub text: std::borrow::Cow<'a, [u8]> }
pub fn extract_candidates(image: &[u8]) -> Result<Vec<PtxCandidate<'_>>, Error>;
```

PtxProfile은 Clone/Copy/Debug/PartialEq/Eq; 이름·identifier는 선택 키가 아니다.
`extract_ptx`의 기존 서명은 유지하고 candidates가 하나가 아니면 Unsupported를 반환한다.

- [x] **Step 1: 실패 시험.** decoding.rs에
  `extracts_mixed_plain_compressed_candidates_with_profiles`,
  `rejects_ninth_candidate_and_aggregate_expansion_before_decode`,
  `legacy_extract_still_rejects_multiple_candidates` 추가.
  순서와 관계없이 두 text/profile을 정확히 반환하며,8개 후보/누적1,048,576의 정확한 경계와
  +1, count9를 검사한다. 누적 초과+잘못된 압축 스트림은 해제 진입 전에 cap의 Unsupported여야 한다.
- [x] **Step 2: RED.** `cargo test -p ct-fatbin`에서 새 API/동작 부재 실패 확인.
- [x] **Step 3: 구현.** record 순회에서 후보 수와 누적 크기를 checked_add로 검사한다.
  plain은 padded payload bytes, compressed는 header의 decoded bytes를 해제 전에 합산한다.
  기존 검증과 개별 cap을 유지하며, 모든 후보에 known profile 검사를 적용한다.
  CUBIN은 기존처럼 bounded opaque skip. 서로 다른 후보의 ABI/중복 정책은 Task4에 둔다.
- [x] **Step 4: GREEN.** `cargo test -p ct-fatbin`; 로컬 producer fixture 준비 후
  `cargo test -p ct-fatbin -- --include-ignored`. 모든 기존 decoding 사례도 통과.
- [x] **Step 5: commit.** `feat(fatbin): expose bounded PTX candidates without changing legacy extraction`.

### Task 3: 본문 프로파일을 IR와 번역 결과에 보존

**Consumes:** 기존 parse(&str)->Result<Kernel,Error>, translate(&str)->Result<Compiled,Error>.
**Produces:** ct-ptx::Profile { major:u16, minor:u16, target:u32 }, Clone/Copy/Debug/PartialEq/Eq;
Kernel.profile:Profile 및 Compiled.profile:ct_ptx::Profile. 기존 함수 서명은 유지한다.

- [x] **Step 1: 실패 시험.** compiler_profile.rs의
  `preserves_supported_source_profile`에서 기존 유효 fixture의7/0/50과
  헤더만8.0/sm_52인 대응 입력의8/0/52를 검사한다. 알 수 없는 조합은 여전히unsupported.
  translation.rs의 `compiled_profile_matches_parsed_source`에서 profile 전달과
  기존 entry/인자/연산 보존을 assert한다.
- [x] **Step 2: RED.** `cargo test -p ct-ptx -p ct-codegen-spirv`에서 필드 부재 실패 확인.
- [x] **Step 3: 구현.** parser가 이미 검증한 version/target을 Profile로 기록하고 Compiled에 전달.
  SPIR-V 명령 생성이나 새로운 PTX 기능 수용은 추가하지 않는다.
- [x] **Step 4: GREEN.** 같은 명령으로 기존/신규 모든 parser/codegen 시험 통과.
- [x] **Step 5: commit.** `refactor(ptx): preserve validated source profile through compilation`.

### Task 4: CUDA image 계층에서 검증·선택 후 native load

**Consumes:** Task2 후보/metadata, Task3 Compiled.profile/params/entry.
**Produces:** ct-cuda/src/images.rs의 아래 crate-private 인터페이스:

```rust
pub(crate) struct SourceCandidate {
    pub(crate) profile: Option<ct_ptx::Profile>,
    pub(crate) text: String,
}
pub(crate) unsafe fn read_candidates(image: *const std::ffi::c_void)
    -> Result<Vec<SourceCandidate>, i32>;
pub(crate) fn compile_candidates(candidates: Vec<SourceCandidate>)
    -> Result<ct_codegen_spirv::Compiled, i32>;
```

read_candidates의 C 포인터 전제는 기존 source와 같다. tests는 images.rs의 cfg(test) 모듈에 둔다.

- [x] **Step 1: 실패 시험.** `selects_profile_independent_of_record_order_and_parameter_names`는
  같은entry/ParamKind와 다른 인자 이름의 후보 순서를 뒤집어8/0/52를 얻는다.
  `rejects_profile_mismatch_duplicate_and_abi_conflict`는 metadata 불일치218,
  동일profile중복/entry차이/ParamKind 또는 인자수차이801을 검사한다.
  `does_not_hide_unsupported_unselected_candidate`는 하위 후보의 미지원 명령도801로 거부한다.
  `raw_ptx_and_short_c_strings_keep_contract`는 단일None 경로 및 empty/짧은 C string 회귀를 검사.
  빈 배열과 None/Some 혼합 배열은 INVALID_VALUE=1; 유효한 단일None은 기존 번역 결과다.
- [x] **Step 2: RED.** `cargo test -p ct-cuda`에서 새 선택 동작 부재 실패 확인.
- [x] **Step 3: 구현.** 기존 source의 pointer 검사/바이너리 판별을 read_candidates로 옮긴다.
  fatbin Profile 필드를 ct_ptx::Profile에 명시적으로 복사한다. compile_candidates는 모든 후보를
  translate하고 본문/metadata 및 전체 ABI를 비교한다. 파라미터 이름은 ABI 비교에서 제외.
  명시적 두 profile 순위를 사용해 Compiled 하나만 반환한다. 함수별 알려진 커널명은 사용하지 않는다.
  modules.rs는 이 결과로 기존 native load를 정확히 한 번 호출한다. 선택/컴파일 과정에는
  native backend 호출이 없어야 하므로 낮은 후보 fallback 분기를 만들지 않는다.
  기존 short source 시험을 이동/갱신하고 export26·오류 매핑218/801을 보존한다.
- [x] **Step 4: GREEN.** `cargo test -p ct-cuda`와 `cargo test --workspace`.
  raw PTX 및 wrapper/ELF 거부가 이전과 같고 새 API export가 없음을 확인.
- [x] **Step 5: commit.** `feat(cuda): select validated PTX alternatives before native module creation`.

### Task 5: 실제 producer·Arc·회귀 검증과 공개 문서

**Consumes:** Task1~4, 기존 Producer/Device/prepare_bundle, 공식 unchanged sample 경로.
**Produces:** `Producer.make_many(self, entries: list[tuple[bytes, bytes]], compressed: bool) -> bytes`.
entries는(PTX source bytes, target arch ASCII bytes)이며 기존 make 동작은 바꾸지 않는다.
`Device.__init__(self, dll_path: Path | None = None)`는 기본 현재 DLL 동작을 유지한다.
신규 m3f script와 검증 harness는 결과 집계만 공개하고 실제 입력/로그는 ignored에 둔다.

- [x] **Step 1: GPU 실패 시험 준비.** tests/m3f_selection_check.py에서 합성 vector_add를
  하위7.0/sm_50 add, 상위8.0/sm_52 sub로 만든다. 두 entry 이름을 동일한 임의 식별자로
  바꾸되 producer/코드 선택에 특별한 이름 분기를 추가하지 않는다. 다른 식별자로도 반복한다.
  두record순서×압축여부×entry이름2종×크기(1,63,64,65,257,50000)의48 GPU사례를 정의한다.
  CPU sub 정답과64 guard를 검사한다. 예상 합계403,600 outputs/3,072 guards이며 실제 집계와 대조한다.
- [x] **Step 2: RED 증거 확보.** Task1의 baseline DLL과 기록 해시를 확인하고 Device에
  명시적경로로 전달해 동일한2후보 컨테이너 로드가801/null임을 확인한다.
  raw 실행 로그는 공개하지 않는다. baseline 부재/해시 불일치는 실패 증거 없이 통과시키지 않는다.
- [x] **Step 3: harness/script 구현.** run_m3f_smoke.ps1은 현재 CT를 build하고 m3f 검사 후
  기존 run_m3e_smoke.ps1로 공식 unchanged host/CLI 회귀를 실행한다.
  native negative는 duplicate profile, entry 차이, 유효한 추가u32 인자에 의한 ABI 차이,
  metadata/본문 불일치, unknown profile, 하위 미지원 연산을 포함한다.
  malformed metadata negative는 producer 결과를 수정한 입력임을 구분해 기록한다.
  rejection 뒤 같은 context에서 sub를 재실행한다. 앱/asset byte 보존은 기존 prepare_bundle 사용.
  선택된 커널의65개 원소를100회 반복하고, 별도의 module 생성/해제1000회를 검사한다.
  이 내구성 기초 검사 수와 출력/guard는 위48사례와 분리해 집계한다.
- [x] **Step 4: GREEN과 공식 검증.** 다음 명령을 순차 실행하고 실패 시 후속 공개를 중단한다.

```powershell
$env:CARGO_INCREMENTAL = '0'
python scripts/check_compatibility_profile.py
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
./scripts/run_m3f_smoke.ps1
cargo test --workspace -- --include-ignored
python -m unittest discover -s tests -p 'test_*.py'
./scripts/check_level_zero_abi.ps1
./scripts/run_m1_smoke.ps1
./scripts/run_m2_smoke.ps1
./scripts/run_m3_smoke.ps1
./scripts/run_m3b_smoke.ps1
./scripts/run_m3c_smoke.ps1
./scripts/run_m3d_smoke.ps1
```

  SPIR-V tools 사용 가능 시 각 후보의 generated bytes를 ignored 파일에 저장하고
  `spirv-val --target-env opencl2.0 <generated.spv>`를 실행한다. 도구 버전/target 검증 여부를 기록한다.
  도구가 없으면 skip; 설치가 완료됐다고 가정하거나 native compiler 결과로 대체하지 않는다.
  native 선택 load 실패 경로를 검토해 backend 호출이 단일이고 fallback이 없음을 확인한다.
- [x] **Step 5: 결과와 manifest 갱신.** M3f-RESULTS.md에 실제 case/guard수·프로파일·CT커밋·
  producer버전·input hash·미검증 범위를 쓴다. profile-v1에 새 제한과 시험참조를 추가한다.
  지원표/README는 unknown profile skip/일반 fatbin/링킹을 지원한다고 쓰지 않는다.
- [x] **Step 6: 최종 검토·commit·초안 PR.** git diff/check와 전역 리뷰 후
  staged 및 outgoing-history/identity 검사를 통과한 파일만 commit/push한다.
  별도 기능브랜치의 초안 PR을 생성·첨부하고 main은 병합하지 않는다.

## Plan Self-Review

- Task2의 PtxProfile과 Task3의 Profile을 Task4에서 명시적 필드 변환하므로 crate 의존 cycle 없음.
- Task4가 모든 pure 검증을 끝낸 뒤 기존 native load에 하나만 전달하므로 rollback 복잡도 증가 없음.
- 기존 single extract wrapper 및 raw C string을 보존하고, unknown profile 혼재 제한을 명시했다.
- 48사례의 출력/guard 집계와 separate official/raw regressions를 섞지 않는다.
- 위 자체 검토는 착수 전 기록이며, 후속 실행 증거는 M3f 결과에 분리해 기록했다.
