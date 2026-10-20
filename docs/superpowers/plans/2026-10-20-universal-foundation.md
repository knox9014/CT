# CT Universal Foundation Implementation Plan

> **For agentic workers:** When implementation is authorized in a subsequent turn, REQUIRED SUB-SKILL: use superpowers:executing-plans task-by-task and an independent subagent for whole-bundle review. This document does not authorize starting implementation in the planning turn.

**Goal:** 범용 CUDA 기능 개발과 병행해 기능 선언·의미 시험·실제 compiler 출력·공식 SPIR-V 검증·독립 소비자·통합 커밋을 연결하는 재현 가능한 기반을 만든다.
**Architecture:** 기존 Rust ABI/compiler/backend와 profile-v1을 보존한다. Python 검증·실행 도구와 별도 JSON registry를 추가하고 module 단위 exporter를 연결한다. CPU·vendor tool·Arc·전체 앱 결과를 분리한다.
**Tech Stack:** 기존 Rust workspace, Python 표준 라이브러리 unittest/subprocess/json, PowerShell, 공식 SPIRV-Tools, 기존 고정 CUDA header/NVRTC/nvFatbin 준비 경로.
**Spec:** [CT 범용 개발 명세](../../CT-UNIVERSAL-PLAN.md).

## Global Constraints

- 기준 소스는 d86d916이며 실행 시 작업 시작 commit을 따로 고정한다. 현재 숫자85/21은 이전 기록이고 새 결과는 실제 실행에서 계산한다.
- profile-v1.json의 닫힌 schema와 기존 checker를 변경 없이 유지한다. 새 정보는 별도 registry로 저장한다.
- 한 앱의 성공이 제품 범위를 정하지 않는다. 의미 coverage와 다양한 실행 경로를 함께 추적한다.
- CUDA ABI 기준은 기존 NVIDIA12.0.107 header 출처·실제 파일 hash다. generic 문서 버전으로 대체하지 않는다.
- exporter는 translate_module을 사용한다. 기존 single-entry translate example을 조용히 바꾸지 않는다.
- 생성 SPIR-V는 Kernel/OpenCL/Physical64 프로파일이다. Vulkan target으로 검증하지 않는다.
- raw log·header·DLL·EXE·SPV·미검토 producer output은 .cache/ 또는 results/local/ 안에 두고 공개하지 않는다.
- 기존 미커밋 LICENSE/Cargo/README와 review 문서는 보존한다. 통합 검증은 해당 수정이 섞이지 않은 별도 후보 checkout으로 수행한다.
- 실제 GPU 실행은 Windows x64 / Arc B390만 필수 현재 target이다. NVIDIA/AMD 부재는 해당 lane의 not_run이며 다른 lane을 막지 않는다.
- main 병합, PR ready 전환, 타 엔진 채택, 시스템 driver/PATH 변경은 이 계획의 자동 작업이 아니다.

### 병행과 최소 선행 조건

여섯 Task 전체의 완료를 P05/P03/P04/P10 설계 착수 조건으로 두지 않는다. 설계는 지금의
코드·고정 명세로 병행 가능하다. 실제 기능 구현은 source baseline과 관련 ABI/API 계약,
최소 재현·시험 기록을 고정하고 관련 차단 결함을 해결한 뒤 시작한다. registry 전부가 아직
없으면 기존 결과 문서에 commit/시험/환경을 정확히 남기고 registry 완성 시 연결한다.
공식 ABI·변경 관련 Arc 회귀는 기능 편입 gate, SPIR-V를 바꾸는 기능에는 실제 validator도 gate다.
전체 corpus 확대·무관한 누적 audit·CI 부트스트랩 미완료는 독립 기능 개발을 일괄 차단하지 않는다.
첫 기반 묶음 자체의 완료와 profile/릴리스 승격은 아래 필수 완료 기준을 그대로 따른다.

## Review Focus

1. resolver 이름 존재를 behavior 실행 성공으로 오인: Task1의 잘못된 category 연결과 거짓 report 시험.
2. 조정한 PTX를 원래 compiler output으로 오인: Task4의 hash mismatch·capture state 시험.
3. single-entry 검증이 multi-entry emitter를 놓침: Task3의 two-entry export/validator 시험.
4. 도구 없음·timeout·stale head가 pass로 바뀜: Task2/3/5의 required lane 실패·후보 불일치 시험.
5. 통합검증에 사용자 미커밋 변경이 섞이거나 개인정보가 공개됨: Task5/6의 source/tree 연계와 공개 검사.

## 파일 구조와 공통 데이터 계약

| 파일 | 책임 |
| --- | --- |
| docs/compatibility/coverage-v1.json | 기능별 구현 상태·제약·시험 종류 참조 |
| docs/compatibility/applications.json | 다양한 소비자·artifact 증거 단계·요구 기능 |
| docs/compatibility/toolchain-lock-v1.json | 도구/header/producer 버전·출처·내용 hash |
| docs/compatibility/producer-corpus-v1.json | source/recipe/output hash·expected지원분류 |
| docs/compatibility/stack-audit-v1.json | PR 의존 그래프·검토 baseline; 실행 후보는 외부 보고서에 기록 |
| scripts/compatibility_registry.py | JSON 구조·참조·lane 결과 순수 검증 함수 |
| scripts/check_coverage.py | registry 정적 검사 CLI |
| scripts/validate_spirv.py | 고정 validator 실행과 결과 분류 |
| scripts/run_compiler_corpus.py | producer capture/immutable replay/지원분류 |
| scripts/run_validation.ps1 | CPU/validator/producer/Arc lane orchestration |
| scripts/check_integration_audit.py | 후보/result/PR graph 일치 검사 |
| crates/ct-codegen-spirv/examples/translate_module.rs | 개발용 multi-entry module exporter |
| tests/test_coverage_registry.py, tests/test_spirv_validation.py | 구조·상태·환경/옵션 identity·오류 경계 |
| tests/test_compiler_corpus.py, tests/test_integration_audit.py | provenance·지원분류·통합후보 |
| tests/corpus/sources/*.cu | CT 소유 실제 compiler 입력 source |
| .github/workflows/cpu.yml | CPU와 필수 validator lane의 자동 실행 |
| docs/CT-INTEGRATION-AUDIT.md | 전체 결과·누적 검토·남은 위험 |

### 공통 schema 규칙

- schema_version은 모두1. 알 수 없는 필드·중복 ID·깨진 참조·경로 이탈은 오류.
- feature ID는기존symbol대소문자를보존할수있는 `[A-Za-z][A-Za-z0-9_.-]*`로고정한다.
  기존profile-v1 ID검사규칙을변경하지않는다.
- 공개 artifact 참조는 role과 sha256으로 표현한다. 개인 경로나 로컬 tool executable 경로를 쓰지 않는다.
- 시험 ID는 public repo 상대경로#marker이며 kind는 resolver/abi/behavior/semantic/validator/native/application/performance 중 하나다.
- coverage root는 schema_version/source_baseline/features/test_catalog다. test_catalog 항목은 id/kind이며
  feature 항목은 id/category/implementation/limits/test_ids다. test_ids는 kind→ID목록 map으로
  선언하며 catalog의kind와일치해야한다. 빈목록은검증공백으로허용하고지원증거로세지않는다.
  implementation은 missing/partial/implemented/research.
  정적 registry에는 pass 필드를 두지 않는다. 결과는 실행 보고서에만 기록한다.
- 보고서는 schema_version/source_commit/target_profile/lane/environment_id/toolchain_lock_sha256/
  test_catalog_sha256/configuration_sha256/cases를 갖는다. environment_id가가리키는local manifest는
  OS/hostABI/GPU모델과driver/runtime/compiler버전을고정하며hostname·serial·개인경로를제거한다.
  seed·실행옵션·입력hash는configuration에연결하고개인인자는공개하지않는다.
  case는 case_id/test_id/execution_kind/application_id/status/reason/artifact_hashes/tool_ids다.
  application_id는해당없는시험에null, artifact_hashes는role→sha256 map이며
  execution_kind는catalog kind와일치해야한다. status는 pass/fail/skipped/not_run.
  reason은 고정 category이며 raw stderr·원본 코드·개인 경로를 public summary에 쓰지 않는다.
- pass는 실제 해당 실행으로 생성된 결과에만 허용한다. declaration이나 mock test 결과를 native/application 결과로 승격하지 않는다.

### 초기 고정 ID와 분류

coverage 기능 범주는 abi/loader/compiler/memory/context/parallel/runtime/library/backend/product.
기존26 export는 `driver.<export_name>` ID로 전부 기록하고 resolver·abi·behavior 참조를 분리한다.
기존 profile-v1의 각feature도 id와 제약을 대응시킨다. behavior 시험이 아직 없는 항목은
그 사실을 missing으로 남긴다. 새 API 구현을 이 registry 작업에 섞지 않는다.

소비자 실행 경로 ID는 driver_external/runtime_dynamic/runtime_static/block_parallel/library/jit.
evidence_tier는 synthetic/upstream_adjusted_build/upstream_original_build/distributed_binary.
candidate는 artifact hash가 없어도 되지만 pinned는 필수 artifact의 sha256이 모두 있어야 한다.
candidate·missing artifact가 application pass 결과를 만들 수 없다.
applications root는schema_version/source_baseline/applications이며 각항목은
id/execution_path/evidence_tier/inventory_state/source/artifacts/required_features/test_ids다.
source는repository/revision/recipe_ref, artifact는role/sha256/availability를갖는다.
inventory_state는candidate/pinned, availability는missing/local_only/public_reference다.
missing의sha256은null이고pinned의필수artifact는missing일수없다. 결과상태는이파일에넣지않는다.
toolchain root는schema_version/source_baseline/tools다. tool항목은
id/pin_state/version/source_url/source_revision/artifact_sha256/platform/recipe_ref/files/validation_target이다.
artifact_sha256은원본package/archive, files는실제사용executable/header/DLL의role→sha256이다.
pinned는필수files hash가모두있어야한다. validation_target은validator에만사용하고나머지는null이다.
source_revision은git기반이면40자리commit, package기반이면null이며version과원본hash로고정한다.
unresolved의미정값은null로기록하고실행가능한도구로세지않는다.

다음검증context는Task1에서정의하며뒤Task가채울registry도같은형식으로소비한다.

```python
@dataclass(frozen=True)
class RegistryContext:
    expected_commit: str
    expected_profile: str
    expected_environment_id: str
    expected_toolchain_lock_sha256: str
    expected_test_catalog_sha256: str
    expected_configuration_sha256: str
    test_catalog: dict[str, dict]
    case_catalog: dict[str, dict]
    applications: dict[str, dict]
    toolchain: dict[str, dict]
    required_cases: frozenset[str]
```

expected_commit은실제실행한40자리commit이다. 정적검사는report의교차참조·일관성을검사하며
실제실행사실의진실성을증명하지는않는다. runner가실제subprocess·입력·observed hash를기록하는책임은별도다.

### 환경·실행 설정의 교차 대조

environment manifest는schema_version/os/host_abi/gpu_model/driver_version/runtime_versions/
compiler_versions를갖는다. configuration은schema_version/lane/cases를갖고각case는
case_id/test_id/execution_kind/application_id/parameters/artifact_requirements/tool_ids를갖는다.
parameters에는크기·seed·옵션·반복수를명시한다. case_id는각실행인스턴스의고유ID이며
같은test_id의여러입력·형식·크기를분리한다. required_cases는test_id가아닌case_id의집합이다.
manifest/configuration은검증후정렬key·UTF-8·공백없는canonical JSON으로hash를계산한다.
environment_id는검증된environment의canonical hash이고다른기대hash도같은규칙을쓴다.
case_catalog는검증된configuration cases에서만구성한다. runner가관측한환경과고정기대환경을
대조하며다르면새run identity로기록하고기존결과로재사용하지않는다.
개인파일/인자는configuration에원문으로넣지않고공개가능한역할·내용hash만참조한다.
report검증은context의환경/lock/catalog/config hash·case구성·artifact역할을실제대조한다.

## Task 1: coverage·소비자·결과 registry

**Files:** Create compatibility_registry.py, check_coverage.py, test_coverage_registry.py, coverage-v1.json, applications.json.
**Consumes:** 기존 profile-v1.json/include/ct_cuda.h/test marker와 spec.
**Produces:** 아래 public Python 순수 함수. 모든 함수는 입력을 변경하지 않고 category 오류 list를 반환한다.

```python
validate_coverage(data: dict, root: Path) -> list[str]
validate_applications(data: dict, root: Path, feature_ids: set[str]) -> list[str]
validate_environment(data: dict) -> list[str]
validate_configuration(data: dict, *, test_catalog: dict) -> list[str]
validate_report(data: dict, *, context: RegistryContext) -> list[str]
```

- [ ] RED: `python -m unittest discover -s tests -p test_coverage_registry.py`.
  시험은 duplicate ID, path escape, resolver-only의behavior분류, 알 수 없는feature/test 참조,
  static pass 필드, candidate artifact의실행pass, 다른commit report를 거부한다.
  같은commit/profile이더라도driver/환경ID·seed/옵션config·lock/catalog hash가다른결과,
  duplicate/missing case_id와구성에없는case도거부한다.
  정상 missing/partial declaration은 허용한다. Expected: 필요한검증함수부재 또는 실제잘못된입력수락으로 FAIL.
- [ ] GREEN: 닫힌schema와 기존checker의안전한경로검사방식을 재사용하여 함수/CLI를 구현한다.
  kind를 임의로 behavior로 바꾼 참조를 막기 위해 test_catalog에 ID당kind를한번정의하고
  기능이 요구하는 evidence kind와 실제catalog kind를 대조한다. report는context의application상태/
  role별artifact hash/tool pin/required case/expectedprofile/실행종류를대조한다.
  이름만있다고실행성공으로세지않는다.
- [ ] 기존26 export와 모든feature를 기록하고 아직없는 핵심기능도 명시적으로 missing/research로 등록한다.
  기존resolver시험은resolver에만 연결하고 nativeharness의실제API호출지점을 behavior 참조로구분한다.
- [ ] applications에는 여섯경로의 조사카드를 만든다. 기존 vectorAddDrv만 출처·기존증거에맞게
  upstream_adjusted_build로 등록한다. 새Runtime/독립앱은 candidate이며성공·hash를만들어내지않는다.
- [ ] verify: 위unittest PASS, `python scripts/check_coverage.py`와 기존
  `python scripts/check_compatibility_profile.py` 모두 exit0. 출력은 정적검사임을명시.
- [ ] commit: registry/code/tests만선택stage, publication검사후커밋.

## Task 2: tool lock과 공식 header ABI provenance

**Files:** Create toolchain-lock-v1.json; extend compatibility_registry.py/test_coverage_registry.py.
Create tests/cuda_reference_abi.cpp, tests/cuda_declared_abi.cpp, tests/cuda_abi_probe.hpp,
scripts/check_cuda_abi.ps1; reuse current tests/abi_layout.c only for Level Zero.
**Consumes:** 기존 tests/m3c_external_check.py의 wheel pin/hash, entrypoints.rs의12.0.107출처.
**Produces:** 정적 `validate_toolchain(data: dict) -> list[str]`와 별도실행대조함수:

```python
validate_tool_execution(entry: dict, *, observed_platform: str,
                        observed_hashes: dict[str, str], required: bool) -> list[str]
```

정적함수는unresolved를합법인미준비선언으로허용한다. 실행함수/runner가실제platform/hash와
required 여부를검사해필수미준비를실패시키고선택미준비를skipped로기록한다.

- [ ] RED: 정적시험은pinned의없는version/source/hash·잘못된sha256을거부하고unresolved는허용한다.
  별도실행시험은다른platform, required unresolvedtool과headerhash mismatch를실패시킨다.
- [ ] GREEN: 위고정toolchain schema로lock을만들고원본archive와실제사용files의hash를구분한다.
  pin_state는 unresolved/pinned이고 pinned만실행한다. unresolved에는가짜hash를채우지않고null을허용한다.
- [ ] 기존12.0.107의실제cuda.h/cudaTypedefs.h와준비package를 대조해 각hash와출처를기록한다.
  원본헤더를공개커밋하지않는다. 공식헤더만포함한reference TU와CT헤더만포함한declared TU를
  독립컴파일하고공유CT소유probe로정규화한ABI표현을비교한다. enum과int,서로다른opaque struct이름의
  명목타입일치를ABI일치조건으로삼지않는다. return/인자순서·개수·폭·정렬·pointer형태·calling convention,
  enum표현과관련값,사용구조체offset을검사한다. 두헤더를한TU에그대로함께포함하지않는다.
  cuGetProcAddress는공식PFN_v11030의4인자,CT_v2는PFN_v12000의5인자로명시매핑한다.
  최신header alias macro를따라구형export까지5인자로비교하지않는다. 정규화표비교와별도로
  공식PFN으로컴파일한독립소비자의실제호출/출력·resolver경계도검증한다.
- [ ] SPIRV-Tools는공식source/release의고정revision을선정해아티팩트hash와빌드recipe를기록한다.
  이선정단계에서필요한host버전만선택하며 rolling latest를lock에쓰지않는다. 사용할수없으면unresolved로남기고필수lane은실패한다.
- [ ] verify: schema unittest PASS, `./scripts/check_cuda_abi.ps1` 실제고정헤더probe PASS.
  헤더/툴미확보는검사하지않은상태로기록하며 이Task의실행완료로세지않는다.
- [ ] commit: publiclock/probe/검사코드만stage. tool/header/binary는ignoredcache에남긴다.

## Task 3: module exporter와 실제 SPIR-V validator

**Files:** Create crates/ct-codegen-spirv/examples/translate_module.rs,
crates/ct-codegen-spirv/tests/module_export.rs, scripts/validate_spirv.py, tests/test_spirv_validation.py.
**Consumes:** ct_codegen_spirv::translate_module, Task2 pinned validator, Task1 result 계약.
**Produces:**

```python
run_validator(module: Path, tool_path: Path, lock: dict,
              *, required: bool, timeout_s: int = 30) -> dict
```

- [ ] RED: module_export의two-entry입력은두entry와서로다른인자ABI를보존해야한다.
  Python시험은hash mismatch/도구없음/nonzero/timeout/exit0을분리하고, missing필수도구가pass되는것을거부한다.
- [ ] GREEN: 개발용 CLI `cargo run -p ct-codegen-spirv --example translate_module -- INPUT OUTPUT`를만든다.
  기존singleentryexample은유지한다. 입력실패시정상output으로오인할stale파일이남지않도록실패계약을고정한다.
  exporter는exit0=성공,3=명시적unsupported,1=invalid translation,2=usage/I/O로분리하고
  line/category만출력한다. 원본PTX·개인경로는출력하지않는다. corpus의unsupported기대는exit3만만족하며
  IO오류·손상입력·validator거부로대체될수없다.
- [ ] run_validator는subprocess argv list와timeout을사용하고 shell=True를쓰지않는다.
  reason은 passed/tool_unavailable/tool_hash_mismatch/tool_timeout/validation_rejected로제한한다.
  required=True의도구부재는status fail, 선택lane부재는skipped이며원인을남긴다.
- [ ] target_env는 emitter의SPIR-V1.0 Kernel/OpenCL/Physical64에맞는 `opencl1.2` 후보로고정검증한다.
  known-goodmodule과공식규칙을대조해환경이맞는지증명한다. 현재출력이위반하면원인을수정하거나
  명세근거로환경선택을변경하는기록을남긴다. 오류를피하려고Vulkan/느슨한flag로바꾸지않는다.
- [ ] 실제고정spirv-val로singleentry, multi-entry, signed64, branchloop, typedmemory 출력의정상검증과
  잘린binary/잘못된type-ID 출력의실패를확인한다. mock runner unittest만으로이단계를통과시키지않는다.
- [ ] verify: `cargo test -p ct-codegen-spirv`와 `python -m unittest discover -s tests -p test_spirv_validation.py` PASS;
  실제validator정상5종pass/손상2종reject, 도구hash·환경·커밋을localreport에기록.
- [ ] commit: Rust/Python/tests/공개요약만. 생성SPV와rawdiagnostic은ignored.

## Task 4: immutable compiler corpus와 일반화 probe

**Files:** Create docs/compatibility/producer-corpus-v1.json, scripts/run_compiler_corpus.py,
tests/test_compiler_corpus.py, tests/corpus/sources/{scalar_boundary,multi_entry,address_control,block_candidate}.cu,
tests/corpus/recipes/{scalar_boundary,multi_entry,address_control,block_candidate}.json.
**Consumes:** 기존고정NVRTC12.0.76경로, Task2lock, Task3exporter/validator, Task1feature IDs.
**Produces:**

```python
validate_corpus(data: dict, root: Path, tool_ids: set[str]) -> list[str]
verify_fixture(data: bytes, expected_sha256: str) -> bool
@dataclass(frozen=True)
class CorpusContext:
    root: Path
    cache_root: Path
    toolchain: dict[str, dict]
    tool_bindings: dict[str, Path]
    translator_path: Path
    validator_path: Path
    registry_context: RegistryContext

run_case(case: dict, *, mode: str, required: bool, context: CorpusContext) -> dict
```

- [ ] RED: source/producer/options/output hash누락·PTX한byte변경·지원분류불일치·candidate pass를거부한다.
  capture/replay mode외입력도거부한다. expected분류unsupported인실제거부는특정negativecase성공이지만
  feature지원pass로합산되지않는것을검사한다.
  source/recipe 경로이탈·미존재·recipe hash변경·replay cache부재도검사한다.
- [ ] GREEN: root는schema_version/source_baseline/cases이며각case에
  id/source_ref/source_sha256/recipe_ref/recipe_sha256/tool_id/options/output_sha256/capture_state/
  expected_class/expected_rejection/required_features/evidence_tier를기록한다. source_ref/recipe_ref는public repo상대파일이며
  resolve 후root내부와hash를확인한다. capture_state는pending/captured, expected_class는supported/unsupported다.
  pending의output_sha256/expected_class는null이다. capture와초기진단은관측만기록하며호환성pass로세지않는다.
  원본출력·최초거부의명시적검토후expected_class를고정하고그다음normative replay를실행한다.
  captured라도expected_class가null이면required replay는실패한다. expected_rejection은supported면null,
  unsupported면stage=translation/category=unsupported다. 기대를통과시키려고관측후자동재분류하지않는다.
  recipe는schema_version/source_ref/tool_id/options를갖는다. case와tool/options/source가일치해야한다.
- [ ] 생성물은cache_root/sha256/<output_sha256>.ptx에내용주소로저장한다. capture는바로관측한bytes/hash를
  기록하고replay는정확한hash경로만읽는다. cache miss는명시적실패/선택skip이며자동재생성하지않는다.
  capture만compiler실행을허용하며그경로도tool_bindings를통해명시적으로받고lock의실제files hash를검사한다.
  clean checkout은public source/recipe로capture한뒤hash를확정하고별도replay한다.
  기존output hash와다르면재현불일치로남기고baseline을자동갱신하지않는다.
- [ ] 위네 source family를실제고정compiler로생성해 localPTX bytes와hash를보존한다.
  scalar는폭·부호경계, multi_entry는entry별ABI, address_control은주소/loop/인자,
  block_candidate는shared/barrier를사용한다. 마지막은미지원이어도진단coverage로남긴다.
- [ ] PTX를수정해지원문법으로맞추지않는다. 원래출력이미지원이면원래hash와최초실패feature를기록한다.
  기존compiler_profile.rs의문자열수정시험은 synthetic/변형시험으로유지하고immutableproducer로재분류하지않는다.
- [ ] 원본출력이모두unsupported여도진단조사는성립하지만compiler호환성증가/positive coverage로세지않는다.
  기존고정NVRTC의vectorAdd원본출력을별도positive기준으로재현해지원·validator통과를확인한다.
- [ ] 재배포검토없는generatedPTX/header/binary는local에둔다. 공개에는CT소유source·recipe·hash·분류만둔다.
- [ ] verify: corpus unittest PASS, 네familycapture+replay결과가실제상태와일치, outputtamper검사fail,
  별도기존producer positive기준통과, 지원output은Task3validator실행.
  unsupportedcase성공은호환기능증가로세지않는다.
- [ ] commit: source/manifests/harness/공개요약만. 새producer지원기능은이Task에추가하지않는다.

## Task 5: 실행 lane·통합 후보·CPU CI

**Files:** Create run_validation.ps1, check_integration_audit.py, test_integration_audit.py,
stack-audit-v1.json, .github/workflows/cpu.yml.
**Consumes:** Tasks1~4, 현재smoke/ABI/privacy명령, GitPRbase/headgraph.
**Produces:**

```python
validate_stack(data: dict) -> list[str]
validate_integration_report(report: dict, stack: dict) -> list[str]
```

- [ ] RED: stale head, unknownbase, cycle, 다른commit결과, native not_run을pass로합산,
  requiredvalidator미실행, dirtycandidate를release검증으로표기하는사례를거부한다.
- [ ] GREEN: lane값cpu/validator/producer/arc/combined를허용하는인터페이스를구현한다.
  실행예: `./scripts/run_validation.ps1 -Lane cpu -Required -OutputDirectory results/local/cpu`.
  파일경로/원시로그는local, 공개요약은커밋·toolID·caseID·status·hash만쓴다.
- [ ] cpu lane: Windows x64cargo fmt/check, Clippy, Rust의pure/ABIresolver시험, Pythonregistry/publication시험.
  ignorednative/producer시험을실행한것으로세지않는다. timeout설정으로실행상태를보고한다.
- [ ] validator lane: Task3의실제공식도구probe가필수. producer lane은Task4capture/replay.
  arc lane은GPU필요package/test의명시적whitelist, LevelZero/CUDAreferenceABI,
  관련기존smoke와최근M3k~M3o검사를순차실행한다. 각case의vendor fixture/producer 의존성도고정한다.
  `cargo test --workspace -- --include-ignored`는producer용nvFatbin fixture까지요구하므로
  모든준비가끝난combined lane에서만실행하고개별결과의native/producer분류는유지한다.
  Arc부재와producer fixture부재를같은이유로처리하지않는다.
- [ ] CI는공식pinnedtool을준비하고cpu+validator를실행한다. vendor/Arc미설정시producer/native는
  명시적not_run이며requiredArc완료가아니다. 신뢰하지않는PR코드를개인GPUrunner에서자동실행하지않는다.
- [ ] tracked stack에는PR번호/base/head기준/검토baseline과의존graph를기록한다.
  이파일을포함하는자기commit의HEAD를내용에기록하지않는다. 실제candidate commit·clean상태·
  실행입력범위의tree hash·관측원격snapshot은외부local실행보고서에고정한다.
  API권한부재면not_run, 하드코딩된head를원격확인한것으로쓰지않는다.
  후속문서commit은원래검증commit을그대로표기한다. 실행source/tests/scripts/Cargo/설정/manifests의
  범위와hash가동일한경우에만source-equivalent를기록할수있고새HEAD직접검증으로바꾸지않는다.
- [ ] verify: integration unittest PASS, CPU/validator실제exit0, 명시적누락lane식별,
  단일후보의결과와모든requiredlane일치. 명령래퍼성공을각하위case성공으로대체하지않는다.
- [ ] commit: workflow/scripts/tests/manifest만. 어떤PR도merge/ready변경하지않는다.

## Task 6: 누적 검토·실행·다음 설계 handoff

**Files:** Create docs/CT-INTEGRATION-AUDIT.md; update첫묶음체크박스와coverage누락표.
**Consumes:** 앞선모든산출물과정확한통합후보.
**Produces:** 검토가능한후보commit/결과/미검증/의사결정목록, P05및P03/P04다음상세설계의입력.

- [ ] 기존변경을보존한별도관리checkout에서작업후보를고정한다. 필요한localfixture는준비recipe로재현하며
  사용자미커밋수정을임의복사·커밋하지않는다. clean source commit과보고서의대상을일치시킨다.
- [ ] Task5requiredlane을실제실행해읽고, CPU/validator/producer/Arc/APIbehavior/앱을분리집계한다.
  NVIDIA/AMD not_run은별도유지하며이번Arc기반완료를막지않는다.
- [ ] 하위에이전트에main~후보누적변경의공통계약검토를맡긴다. 보안·ABI·수명·의미에영향있는
  Critical/Important는재현RED→공통수정→관련suite검증으로처리한다. 발견·판단·보류를전부기록한다.
- [ ] 공식도구의제약과미확보artifact를정직하게남긴다. pipeline구축성공을범용CUDA/외부앱성공으로세지않는다.
- [ ] 병행중인P05의retain/release/reset/_v2/TLS/공유상태설계와P03/P04/P10의타입·주소·함수·참여규칙설계에
  수집한결과를연결한다. 이Task완료때까지설계착수를미루지않는다. 소비자없는필수공통기능도누락하지않는다.
- [ ] 공개artifact/identity/history검사, 문서링크/차이검사. 기존정책의검토가능초안PR에결과를첨부한다.
  main병합은구체적후보를사용자에게제시한뒤별도결정한다.

## 완료 판정

첫 묶음은 호환성 자체를완료하는작업이아니다. 다음이모두있어야완료다.

1. 모든기존export/feature와핵심미구현영역이coverage에추적되며resolver/behavior가구분된다.
2. 실제pinnedvalidator가multi-entry포함정상출력을검증하고손상출력을거부한다.
3. 네producer source family의원본출력hash·분류·실행상태가재현된다.
4. 공식headerABI와현재Arc회귀결과가고정후보에연결된다.
5. 미실행·도구부재·하드웨어부재·unsupported가pass로바뀌지않는다.
6. 독립검토와공개검사결과가있고원래사용자변경이보존된다.

실제toolpin/producer출력/외부앱조사에서새의존성이드러나면해당Task의작은결정을기록하고진행한다.
범용성/의미/상태경계를바꾸는결정은추측구현하지않고수정명세로제시한다.
P05/실제compiler공백/P10설계는첫묶음과병행가능한범위로분리하며,
한앱완주나P03전체완료를모든후속개발의일괄선행조건으로두지않는다.
