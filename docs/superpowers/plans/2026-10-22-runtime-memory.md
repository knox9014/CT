# P09a1 Shared Runtime Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 공식 Runtime 헤더 앱의14개 메모리·장치·오류 API를 하나의 CT Driver에 연결한다.

**Architecture:** 별도 `ct-cudart` Rust DLL이 app-local CT Driver의 C ABI를 동적으로 호출한다.
Runtime은 초기화·primary 참조·오류 TLS만 소유하며 Driver 자원 목록을 복제하지 않는다.
root workspace를 수정하지 않고 nested workspace를 명시적으로 검사한다.

**Tech Stack:** Rust/std, Win32, Python unittest, MSVC, 고정 CUDA12 헤더, 기존 Intel Level Zero Driver.

**Spec:** [2026-10-21-runtime-memory-design.md](../specs/2026-10-21-runtime-memory-design.md).
설계 기준 `f262a52e95c8b193734d41a7298c7664c6743571`, 기존 실행 코드 기준
`39f97521e9e6c35990754e904555655d09a5c6b2`.
사용자의2026-10-22 `이어해봐`는 앞서 제출한 서면 설계를 따라 상세 계획을 작성하는 승인이다.
이 계획의 제품 구현은 아직 실행하지 않았다. 기존 실행 방식은 주 에이전트 구현 + 하위 에이전트 독립 검토다.

## Global Constraints

- Windows x64, app-local `cudart64_12.dll`과 `nvcuda.dll`, eager/serialized completion.
- 별도 DLL 안에 `ct-cuda` rlib를 정적으로 링크하지 않는다. 외부 Cargo dependency/publish 없음.
- `crates/ct-cudart/`의 독립 `[workspace]`와 nested Cargo.lock을 사용한다. root Cargo/기존 사용자11개 파일 해시 보존.
- Runtime/Driver 모듈은 소유 reference를 확보하고, 함수 표 게시/사용 전에 process lifetime pin한다.
- 호출자는 loader-lock 밖에서 stateful 함수를 호출한다. DllMain/TLS destructor에 GPU·정리 작업 없음.
- CUDA12 SetDevice는 primary를 즉시 선택한다. 다른 호출은 유효한 일반 current 문맥을 그대로 사용한다.
- primary retain은 Runtime instance/장치당 하나. rollback release 실패는 sticky999, 재retain/release 금지.
- Driver reset 후 자동 회복, cudaDeviceReset, launch/등록, UVA/Default-copy, stream/PTDS/async는 범위 밖.
- `cudaMalloc(0)`은801/null, 버전 함수는801/출력0. 지원하지 않는 버전을 위장하지 않는다.
- Driver38개 manifest/v1 report schema를 보존하고 별도 Runtime14 ABI manifest를 만든다.
- .gitignore/공개·신원 검사를 유지한다. vendor 파일·생성 binary·raw log·개인 경로를 커밋하지 않는다.

## Review Focus

1. 동일 basename의 다른 Driver/경로 별칭/동시 unload: 소유한 동일 모듈만 사용하고 다른 상태는35로 실패한다(Task2/6).
2. SetCurrent 실패 뒤 release도 실패: 첫 호출999, 이후에도 추가 retain/release 없음(Task3).
3. 일반 Driver 문맥을 Runtime이 덮어씀: 원래 문맥과 할당이 그대로 유지된다(Task3/6).
4. Default/알 수 없는 memcpy kind와0-byte 경로:801/21을 구분하고 무작업 성공으로 미지원 kind를 숨기지 않는다(Task4).
5. root 검사만 통과한 standalone crate/위조 child 보고서: nested 명령과 실제 artifact·관찰을 required gate로 검사한다(Task1/6).

## 파일과 공통 인터페이스

새 crate: `crates/ct-cudart/{Cargo.toml,Cargo.lock,src/lib.rs,src/errors.rs,src/driver.rs,src/platform.rs,src/state.rs,src/device.rs,src/memory.rs,src/tests.rs}`.
`lib.rs`는14개 ABI 진입과 panic containment, `driver.rs`는 함수 표/호출만,
`platform.rs`는 Win32 모듈 identity/참조/pin, `state.rs`는 primary 획득만 담당한다.

공통 type은 `driver.rs`의 `type Context=usize; type DriverResult<T>=Result<T,i32>`.
`DriverCalls: Send+Sync`의 메서드는 다음으로 고정한다. 숫자 오류는 아직 Driver 코드이며
Runtime 변환은 export 경계에서 한 번만 한다.

```text
init()->i32; count()->DriverResult<i32>; device(ordinal:i32)->DriverResult<i32>;
current()->DriverResult<Option<Context>>; context_device()->DriverResult<i32>;
retain(device:i32)->DriverResult<Context>; release(device:i32)->i32;
set_current(context:Context)->i32; synchronize()->i32;
allocate(bytes:usize)->DriverResult<u64>; free(pointer:u64)->i32;
unsafe copy_htod(dst:u64,src:*const u8,bytes:usize)->i32;
unsafe copy_dtoh(dst:*mut u8,src:u64,bytes:usize)->i32;
copy_dtod(dst:u64,src:u64,bytes:usize)->i32; fill8(dst:u64,value:u8,bytes:usize)->i32.
```

`state.rs`: `Runtime<D:DriverCalls>::new(driver:D)`, `set_device(&self,i32)->i32`,
`ensure_current(&self)->DriverResult<Context>`, `get_device(&self)->DriverResult<i32>`.
추가로 `initialize(&self)->i32`는 Driver init의 첫 결과를 OnceLock에 저장하며,
`get_count(&self)->DriverResult<i32>`를 제공한다. 모든 state/device 진입은 initialize를
먼저 확인하고 raw Driver 오류를 유지한다. get_count/get_device는 primary를 만들지 않는다.
공개 ABI는 `cudaError_t` 대체 i32, 문자열 함수는 `*const c_char`이며 정확한14개 이름과
인자는 spec4절 표와 일치해야 한다. `errors::from_driver(i32)->i32`와
`errors::record(i32)->i32`를 혼동하지 않는다. record에는 이미 변환된 Runtime 코드만 전달한다.

## Task 1: Runtime ABI·오류와 standalone 검사 기반

**Files:** Create crate manifest/lock, `src/{lib,errors,driver,tests}.rs`, `include/ct_cudart.h`,
`docs/compatibility/runtime-profile-v1.json`, `scripts/check_runtime_profile.py`, `tests/test_runtime_profile.py`.

**Interfaces:** Produces14개 선언, DriverCalls, 오류 TLS·`from_driver/record`, Runtime profile 검증기.
아직 실제 Driver 함수 표나 장치 작업을 연결하지 않는다. 중간 함수는 명시적801이며 지원 완료로 표시하지 않는다.

- [ ] 실패 시험 `runtime_error_mapping_is_explicit`에 다음 값을 고정한다:
  `assert_eq!(from_driver(201),49); assert_eq!(from_driver(709),709);`
  `assert_eq!(from_driver(218),999); assert_eq!(from_driver(400),999);`
  나머지 spec5절의0/1/2/3/100/101/801/999도 별도 입력 표로 확인한다.
- [ ] `last_error_is_thread_local_and_success_does_not_clear`를 먼저 작성한다.
  `record(21); record(0); assert_eq!(peek(),21); assert_eq!(take(),21); assert_eq!(take(),0);`
  두 번째 스레드는 초기0을 보고, 두 스레드 오류가 교차하지 않아야 한다.
- [ ] `cargo test --manifest-path crates/ct-cudart/Cargo.toml --locked`의 RED를 기록한다.
  `[workspace]`, dependency 없는 publish=false package와 lock을 만들고 panic=unwind로 고정한다.
- [ ]14개 CT-owned C ABI 선언과 정확히 같은 Rust export만 만든다. errors는 순수 static/TLS이다.
  version(NULL)=1, version(valid)=801/0, 문자열 미등록 코드=`unrecognized error code`.
  문자열/Peek/Get은 새 오류를 기록하지 않고 Driver 초기화를 호출하지 않는다.
  Rust test의 typed function-pointer assignment14개로 실제 export의 extern/system,
  인자·반환 타입도 고정한다. C 선언끼리 일치하는 것만으로 Rust ABI 일치를 대신하지 않는다.
- [ ] Runtime manifest 필드는 `schema_version,dll_name,exports,limits`로 닫는다.
  `dll_name=cudart64_12.dll`; export는 `symbol,signature_id,behavior,test_ids`만 가진다.
  상태는 검증 전 profile 제약이며 실행 결과를 담지 않는다.14개와 signature drift/누락/중복,
  escaped test reference를 Python RED→GREEN으로 검사한다. Driver manifest는 변경하지 않는다.
- [ ] fmt/clippy/test를 각각 이 manifest로 실행하고 성공·원래 사용자 파일 해시를 확인한다.
  stage는 Task1 파일만 선택하고 공개 검사 후 commit `feat(runtime): define bounded ABI and error state`.

## Task 2: 소유한 단일 Driver 모듈과 함수 표

**Files:** Create `src/platform.rs`; implement `src/driver.rs`, bootstrap section `src/lib.rs`; extend `src/tests.rs`.

**Interfaces:** Produces `DriverBridge:DriverCalls`,
`DriverBridge::open()->Result<Self,i32>`(실패는 Runtime35),
`bridge()->Result<&'static Runtime<DriverBridge>,i32>`.
bridge 오류는 이미 Runtime 코드이므로 from_driver에 다시 넣지 않는다.

- [ ] CPU `bootstrap_rejects_wrong_module_and_missing_symbols`의 fake Platform을 작성한다.
  다른 위치의 nvcuda 또는 필수 함수 누락은35, Driver init 호출 수0, 함수 표 publish0이다.
  `pin_failure_is_sticky`는 첫35 뒤 DLL이 제공돼도 load/resolve/pin이 반복되지 않음을 확인한다.
- [ ] `table_is_not_called_before_modules_are_pinned`의 trace에
  owned-load → identity-check → resolve-all → pin-runtime/driver → publish → first-driver-call을 요구한다.
  소유 module reference가 없는 borrowed handle을 호출하거나 pin 실패 후 호출하면 RED다.
- [ ] 실패를 관찰한 후 Win32 모듈 탐색·소유·identity 계층을 구현한다.
  Runtime 자기 모듈에서 adjacent absolute path를 얻고 현재 process의 모든 nvcuda 모듈을 점검한다.
  basename만 주는 GetModuleHandle 결과 하나로 중복 여부를 판단하지 않는다.
  열거 핸들은 주소 기반 GetModuleHandleEx로 reference를 확보한 뒤 실제 module 경로/파일 identity를 검증한다.
  열거 중 사라진 모듈·동일성을 입증하지 못한 별칭은35로 실패한다. CWD/PATH fallback 없음.
- [ ] 소유한 LoadLibraryEx reference와 검증된 identity를 유지한 채15개 Driver 함수를 모두 resolve한다:
  Init/DeviceGetCount/DeviceGet/CtxGetCurrent/CtxGetDevice/CtxSetCurrent/PrimaryRetain/PrimaryRelease_v2/
  CtxSynchronize/MemAlloc_v2/MemFree_v2/MemcpyHtoD_v2/MemcpyDtoH_v2/MemcpyDtoD_v2/MemsetD8_v2.
  official Driver ABI 형식을 사용하고 Driver module 및 Runtime module pin 후에만 publish한다.
- [ ] `OnceLock<Result<Runtime<DriverBridge>,i32>>`로 bootstrap 실패를 고정한다.
  pin 전에 실패하면 소유 module reference를 정리하되 GPU cleanup은 호출하지 않는다.
  pin은 process lifetime이므로 부분 성공도 unpin/재시도를 약속하지 않는다.
- [ ] nested cargo test/clippy 성공, dependency metadata에 ct-cuda/ct-backend-intel 없음,
  DllMain/TLS destructor에 Driver/cleanup 진입 없음과 공개 검사 후 commit.

## Task 3: primary 참조와 장치/문맥 상호작용

**Files:** Create `src/state.rs`, `src/device.rs`; wire exports and extend `src/tests.rs`.

**Interfaces:** Consumes DriverCalls/bridge; produces Runtime methods defined above and
`cudaGetDeviceCount/GetDevice/SetDevice/DeviceSynchronize`의 실제 경로.
primary slot은 `Vacant | Ready(Context) | Failed(i32)`이며 device별 Mutex 안에서 관리한다.
state 메서드는 raw Driver 코드를 반환하고 device API가 from_driver로 한 번 변환한다.
memory API는 자체 Runtime 정책 오류와 변환한 Driver 결과를 반환하며 export는 record만 한다.
`bridge()`의35와 memory 정책21/801을 from_driver에 다시 넣지 않는다.

- [ ] `set_device_is_eager_and_retains_once` RED:
  `set_device(0)` 100회/두 스레드 뒤 `retain_calls(0)==1`; 각 성공은 해당 스레드 current를 선택한다.
  Count/Get만 호출한 시나리오는 `retain_calls(0)==0`이다.
- [ ] `ordinary_current_is_preserved` RED:
  fake current=77/device=1이면 ensure_current=77, get_device=1, primary retain/set 호출 수0.
  current가 없을 때만 장치0을 선택한다. stale current의709를 None으로 바꾸지 않는다.
- [ ] `failed_selection_rolls_back_or_faults_slot` RED:
  최초 retain 성공→SetCurrent 실패→release 성공이면 원래 오류와 Vacant;
  release도 실패하면 첫999와 Failed999, 이후 두 호출의 retain/release count가 늘지 않는다.
  이미 Ready를 사용하는 SetCurrent 실패에는 Runtime-owned ref를 release하지 않는다.
- [ ] 현재 문맥을 먼저 확인하는 ensure_current, device 검증 후 primary를 준비하는 set_device를 구현한다.
  Ready handle이 stale로709를 반환하면 Failed709로 고정하고 재retain하지 않는다.
  새 primary를 선택/게시하기 전 실패는 이전 current를 유지하며, 유효한 ordinary current 호출을
  다른 primary slot의 Failed 때문에 거부하지 않는다. Driver reset 자동 회복은 구현하지 않는다.
- [ ] 각 export의 NULL scalar output=1, count/device valid output0 초기화,
  성공 후 last-error 보존과 nonzero 갱신을 검증한다. panic/poisoned Mutex는999이며 unwind가 C로 나가지 않는다.
- [ ] nested cargo tests/clippy, fake trace의 정확한 호출 수, 공개 검사 후 commit.
  initialize의 최초3/100/999가 다음 호출에서 재시도·성공으로 바뀌지 않는 시험도 포함한다.

## Task 4: 명시적 메모리 API와 경계 동작

**Files:** Create `src/memory.rs`; wire `cudaMalloc/Free/Memcpy/Memset` in `src/lib.rs`; extend `src/tests.rs`.

**Interfaces:** `unsafe copy_host(dst:*mut u8,src:*const u8,size:usize)->i32`,
`unsafe copy_device<D:DriverCalls>(rt:&Runtime<D>,dst:*mut c_void,src:*const c_void,size:usize,kind:i32)->i32`,
`unsafe allocate<D:DriverCalls>(rt:&Runtime<D>,out:*mut *mut c_void,size:usize)->i32`,
`free<D:DriverCalls>(rt:&Runtime<D>,ptr:*mut c_void)->i32`,
`fill<D:DriverCalls>(rt:&Runtime<D>,ptr:*mut c_void,value:i32,size:usize)->i32`.
후자의 내부 결과도 Runtime 코드다. 순수/zero fast path는 export에서 bridge를 부르기 전에 선택한다.

- [ ] `unsupported_kind_is_not_hidden_by_zero_size` RED:
  kind4/size0=801, kind-1·5/size0=21, kind0..3/size0=0이고 pointer/native/primary 접근 수0.
  `malloc_zero_is_outside_profile`은801/null, NULL output=1, Driver allocate 호출 수0을 확인한다.
- [ ] `memory_dispatch_preserves_direction_and_byte_value` RED:
  양수 kind1/2/3은 각각 htod/dtoh/dtod 한 경로만 호출한다. memset(-1)=0xff,
  memset(256)=0x00, memset(0x1234)=0x34를 Driver fill8 인자로 확인한다.
- [ ] 양수 H2H는 유효한 non-null host extents·checked pointer addition·비중첩을 검사하고
  CPU copy만 실행한다. positive NULL/overflow/overlap=1. H2H는 Driver/primary 초기화 없이 동작한다.
  host pointer가 실제 읽기/쓰기 가능한지는 호출자 전제이며 임의 포인터 안전성을 주장하지 않는다.
- [ ] 양수 device 작업은 ensure_current 뒤 Driver의 소유·범위·overlap·exact-base 규칙에 위임한다.
  positive NULL 인자는 bridge 전에1로 거부한다. cudaFree(NULL)은 context 준비 후 free 명령 없이0,
  cudaMemset(size0)은 context 준비 없이0이다. malloc의 유효 output은 호출 전null로 설정한다.
- [ ] 두 스레드 last-error와 성공 후 오류 유지, fake Driver의1/2/201/709/801/999 반환,
  손상 뒤 추가 native 작업 차단을 기존 Driver contract와 대조해 검사한다.
- [ ] nested test/clippy, CPU host 복사의 독립 byte 기준·guard 보존과 공개 검사 후 commit.

## Task 5: 명시적 Runtime 앱 로더

**Files:** Modify `scripts/ct.py`, `tests/test_ct_loader.py`; update Runtime profile limits.

**Interfaces:** 기존 호출은 유지하며
`inspect_pe(data,*,dll=False,runtime=False)`와
`prepare_bundle(application,ct_dll,assets,root,*,runtime_dll=None)`로 확장한다.
CLI `run --ct-dll ... --runtime-dll ... application`만 Runtime 허용을 켠다.

- [ ] Python RED `test_runtime_imports_require_exact_opt_in_profile`:
  기본은 모든 cudart 거부; opt-in은 cudart64_12.dll과14개 named import만 허용한다.
  다른 버전/추가 symbol/등록·launch/ordinal/delay import는 거부한다.
- [ ] `test_runtime_bundle_preserves_all_payload_bytes_and_rejects_collisions` RED:
  EXE + nvcuda.dll + cudart64_12.dll 바이트를 원본과 각각 비교한다.
  app 이름이 Runtime/Driver 이름과 충돌하거나 대소문자만 다른 asset도 거부한다.
- [ ] Runtime 파일은 독립 인자로만 받는다. PE DLL 검사와 Runtime profile 검증 뒤 고정 이름으로 복사한다.
  report에 Runtime SHA-256을 추가하되 Driver-only report/기존 호출 동작은 보존한다.
  malformedPE/기존unknownDriverimport/개인 경로를 포함한 CLI 오류가 기존 규칙을 우회하지 않게 한다.
- [ ] `python -m unittest discover -s tests -p 'test_*.py'`와 기존 synthetic PE fixture 전체를 실행한다.
  로더 성공만으로 native API 성공을 선언하지 않는다. 공개 검사 후 commit.

## Task 6: 공식 ABI·실제 앱·전체 evidence gate

**Files:** Create `tests/{runtime_reference_abi.cpp,runtime_declared_abi.cpp,p09a_runtime_app.c,p09a_runtime_check.py}`,
`tests/{p09a_runtime.def,p09a_fake_driver.c,p09a_noop_driver.c}`,
`scripts/{check_runtime_abi.ps1,run_p09a_smoke.ps1}`; modify
`docs/compatibility/{toolchain-lock-v1.json,coverage-v1.json,runtime-profile-v1.json}`,
`scripts/{run_validation.py,check_toolchain_files.py}`, `tests/test_validation_runner.py`, `.github/workflows/cpu.yml`.

**Interfaces:** Runtime/Driver 선언 비교는 독립 TU로 수행한다. native harness는 실제 import의
official-header EXE, 명시한 두 DLL, 실행 전/후 payload identity와 수치·수명 관찰을 소비한다.
tool lock은 기존 schema를 확장하지 않고 `cuda-runtime-headers`/`cuda-nvcc-support-headers` 두 tool을 추가한다.

- [ ] 고정 Runtime12.0.107/compiler-support12.0.76 원본 wheel에서 MSVC가 실제 include한 vendor
  closure를 수집한다. 절대 경로 로그는 ignored에 두고 각 파일의 원본 archive member/hash를 확인한다.
  선택5개 hash만으로 전체 closure를 통과시키지 않는다. missing/변조된 필수 header가 실패하는 RED부터 작성한다.
- [ ]14개 ABI·cudaMemcpyKind0..4·오류0/1/2/3/21/35/49/100/101/709/801/999를 official TU와 비교한다.
  Runtime import library는 CT-owned `.def`의 DLL 이름 cudart64_12.dll로 생성한다.
  이 `.def`는 `tests/p09a_runtime.def`에14개 이름을 기록하고 profile/header와 동기화를 검사한다.
  NVIDIA Runtime 바이너리/코드를 링크하거나 수정한 실행 파일을 원형 앱으로 표시하지 않는다.
- [ ] 실제 EXE의 named Runtime imports를 PE로 확인하고, 앱은 Driver를 동적 호출한다.
  HMODULE 동일성, Count/Get 비활성, SetDevice 즉시 활성, 일반 문맥 보존, 양쪽 할당의
  Runtime↔Driver copy/fill/free, odd-size/guard/읽기전용 입력,2-thread 오류 격리를 관찰한다.
- [ ] 별도 child modes로 no-driver 순수 오류/H2H, missing Driver, 다른 위치 Driver preload,
  필수 export 누락, stale/reset709, 정확한 끝-of-process Runtime retain probe를 실행한다.
  mode마다 새 프로세스로 bootstrap sticky 상태를 분리한다. loader-lock stateful 호출은 허용/자동 감지 시험이 아니다.
  모드는 `shared_primary,ordinary_context,threads,pure_no_driver,missing_driver,wrong_driver,missing_export,stale_reset,retain_probe,noop_copy,noop_fill`로 고정한다.
  마지막2개는 예상 실패 negative control이며 나머지는 모두 pass해야 한다. 앱 main의 pure mode는
  nvcuda를 로드하지 않아야 한다. wrong/missing-export provider의 소스는 `tests/p09a_fake_driver.c`에
  두고 실제 Driver ABI로 빌드해 init/호출 counter를 관찰한다. 생성 DLL만 ignored에 둔다.
  `retain_probe`는 fresh child에서 Driver Init/GetState(active0) → Runtime SetDevice(active1) →
  외부 Driver retain1개 → Runtime 반복/두 스레드 호출 → 외부 몫 release(active1) →
  Runtime 몫으로 예상한 추가 release1개(active0) → 종료 순서다. probe가 숨은 retain을 추가하지 않는다.
- [ ] 독립 native oracle은 실행마다 입력·출력 sentinel을 바꾼다. 별도 fake provider에서 H2D 또는 memset을
  성공 no-op으로 만드는 control을 실행하고 수치/guard mismatch로 실패함을 확인한다. export 없음만으로
  오계산 탐지 능력을 대신하지 않는다. nominal provider는 테스트 macro 없이 빌드한다.
  이 두 control은 `tests/p09a_noop_driver.c`의 명시적 forwarding DLL로 구현한다. 모든 Driver
  export에 실제 wrapper를 두고 별도 고정 이름으로 복사한 nominal CT Driver에 전달하되,
  지정한 HtoD 또는 D8 한 호출만 성공 no-op으로 바꾼다. 나머지 allocation/context/copy는
  실제 CT/Arc 경로를 유지한다. 두 소비자 모두 같은 forwarding HMODULE을 사용한다.
  PE export forwarder만 사용해 함수 주소가 다른 모듈로 바뀌는 bootstrap 우회는 하지 않는다.
  nominal/control/underlying DLL hash를 별도 기록하고 control 결과를 Arc 지원 사례 수에 더하지 않는다.
  noop_copy는 Driver로0xcd 초기화 후 다른 입력의 H2D를 생략하고 실제 D2H 결과를 대조한다.
  noop_fill은 정상 H2D 초기화 후 다른 byte 값의 fill만 생략한다. allocator 초기값에 의존하지 않는다.
- [ ] runner에 새 required case6개를 더한다:
  `cpu.runtime_fmt`, `cpu.runtime_clippy`, `cpu.runtime_rust`, `cpu.runtime_profile`,
  `arc.runtime_abi`, `arc.runtime`.
  앞의3개는 nested manifest의 fmt/clippy/test(`--locked`) 명령,4번째는 Runtime manifest 검증이다.
  ABI/native script는 nested `cargo build --locked`와 MSVC 빌드를 해당 clean source에서 수행한다.
  기존32개를 유지하므로 combined required는38개다. CI CPU lane에도4개가 포함돼야 한다.
- [ ] configuration은 빌드 전후 동일한 tracked fixture/profile/tool 입력 hash를 사용한다.
  생성 DLL/EXE는 빌드 후 harness가 직접 읽어 hash·복사 byte를 검증하고 ignored child manifest에 기록한다.
  아직 생성되지 않은 binary hash를 pre-build configuration에서 읽지 않는다. generated artifact identity를
  v1 report에 자기 주장으로 넣지 않고 별도 native manifest audit로 실제 파일과 대조한다.
  runner는 child pass 문자열만 신뢰하지 말고 정확한 case identity·완료 관찰·manifest/hash를 검사한다.
  missing mode/counter, 바뀐 payload, fake child 성공 JSON이 required pass가 되지 않는 Python RED→GREEN을 작성한다.
- [ ] 독립 검토 후 clean managed worktree의 고정 candidate에서
  `python scripts/run_validation.py --lane combined --required --output-directory results/local/p09a-candidate` 실행.
  이후 독립 `validate_lane_bundle`과 native manifest audit, 사용자11개 해시/공개·신원 검사를 통과한다.
  실제 Runtime/Rust/Python/Arc 결과를 분리해 기록하고 docs-only head는 tested candidate와 execution tree가 같음을 검사한다.
- [ ] 검증한 변경만 commit/push/stacked draft PR로 등록하고 생성 PR을 채팅에 attach한다. main 병합/ready/release는 하지 않는다.
  `docs/P09a1-RESULTS.md`에는 최초 RED·음성 대조군·실제 숫자·ABI/장치/consumer 한계를 남긴다.

## 실행·중단·완료 규칙

구현 시 기존 관리 worktree를 재사용하고 별도 branch를 만든다. GPU 실행은 한 작업자만 수행한다.
각 Task의 RED/GREEN/검토 결과를 ignored ledger에 남긴다. native 오류·오계산은 기능 확대보다
먼저 진단하며, API 의미/범위가 달라지는 발견은 설계에 기록하고 검토한다.

위험한 수명 경로는 Task2/3 뒤 독립 검토, 전체 branch는 Task6 전후 독립 검토를 둔다.
주 구현은 현재 대화의 에이전트가 맡고 하위 에이전트는 검토한다. 새 대화/자동화는 만들지 않는다.
이번 계획 자체의 검토가 끝나기 전 제품 코드나 dependency를 추가하지 않는다.

P09a1 완료는38 required case와 해당14개 ABI/실제 native 관찰이 통과한 고정 source에서만
주장한다. 그때도 실제 nvcc host/커널 등록·launch, 원본 dynamic/static cudart, reset 자동회복,
UVA·async·프레임워크·AMD/NVIDIA 실행은 완료로 표시하지 않는다.
