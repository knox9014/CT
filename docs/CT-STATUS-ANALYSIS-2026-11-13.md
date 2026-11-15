# CT 작업 현황과 근거 분석 — 2026-11-13

이 문서는 현재 작업 트리, 기존 결과 문서, 실제 구현과 이번 재실행을 대조한 분석이다. 제품 코드는 변경하지 않았다. 이번에 만든 것은 이 문서와 무시되는 `.cache` 아래 진단 파일·로그·빌드 출력이다. 기존 증거를 최신 성공으로 바꾸거나 실패 기대값을 수정하지 않았다.

## 1. 현재 위치

**CT는 Windows x64 / Intel Arc B390에서 제한된 PTX를 번역·실행하고 일부 CUDA Driver/자체 Runtime 경로를 검증한 초기 호환 계층이다. 일반 CUDA 앱 호환이나 실용적인 제품 완성은 입증되지 않았다.**

핵심 계산 경로가 작동한다는 근거는 있다. 현재 빌드에서도 Numba 생성 PTX의 직접 실행이 통과했다. 그러나 원본 Numba의 전체 호출 경로는 현재 제품 DLL만으로 완료되지 않는다. 기존 Numba JIT 실험의 성공은 별도 시험 DLL·메모리 정책·프로세스 어댑터를 포함한 구성에 귀속된다.

성공 가능성의 수치, 전체 완료율, 완성 시점, NVIDIA 대비 성능 비율을 산출할 근거는 없다.

## 2. 근거를 읽는 기준

| 구분 | 의미 |
| --- | --- |
| 이번 재실행 | 이번 분석에서 명령을 실행하고 종료값·출력을 직접 확인 |
| 과거 검증 기록 | 고정 소스·입력·산출물에 대해 기존 결과 문서와 저장 기록에 남은 결과 |
| 구현 확인 | 현재 소스에 코드가 존재함을 확인. 모든 경로의 실행 성공과 다름 |
| 실험 구성 | 제품 외 DLL, 명시적 정책 또는 프로세스 어댑터에 의존 |
| 미검증/미지원 | 필요한 성공 증거가 없거나 현재 경로가 명시적으로 거부 |

CPU 회귀 테스트, GPU 계산, API 주소 조회, 실제 API 호출, 앱 완료, 성능은 서로 다른 근거다. 거부가 기대되는 진단이 통과해도 해당 앱이 실행된 것은 아니다. 반복 실행의 출력 비교 횟수도 서로 다른 앱이나 새로운 입력의 수가 아니다.

## 3. 이번에 직접 확인한 상태

분석 시작 시 브랜치 `codex/p09a2-launch-design`, HEAD `219e6e5`였다. 변경된 추적 파일 102개와 비추적 파일 326개가 있었다. 이 문서 추가 전 수치이며 무시되는 캐시는 제외한다. 이 개수는 변경 규모의 단서이지 기능 수나 완성도가 아니다.

현재 제품/검증 입력 지문은 다음과 같다. `scripts/run_validation.py`의 `source_fingerprint`로 계산했고 일반 결과 문서는 이 지문 범위 밖이다.

`391ca50eb42ab556f76415fafabc75963a315a2504b9d746f52edc791cc5b0cd`

| 검사 | 이번 결과 | 적용 범위와 한계 |
| --- | --- | --- |
| Python 전체 발견 테스트 | 394 통과, 실패 0 | `python -m unittest discover -s tests -p 'test_*.py'`. 외부 앱 전체 실행을 뜻하지 않음 |
| Rust workspace | 227 통과, 실패 0, ignored 7 | `cargo test --workspace --offline`을 별도 출력 폴더에서 실행. ignored를 통과로 세지 않음 |
| 별도 CT Runtime | 129 통과, 실패 0 | `cargo test --manifest-path crates/ct-cudart/Cargo.toml --locked --offline`을 별도 출력 폴더에서 실행 |
| 정적 등록부/Driver·Runtime 프로파일 | 통과 | 선언과 참조의 정합성 검사. 실행이나 CUDA 적합성 증거가 아님 |
| bootstrap table 등록부 | inventory_valid | 도구 자체가 native success 미승인, primary source 미검증이라고 표시 |
| 현재 소스의 Intel 기본 GPU 실행 | M0-native 통과 | B390, 16가지 길이/그룹 조합, 오차 0. 준비된 SPIR-V 경로이며 CUDA 번역 전체 시험이 아님 |
| 현재 제품 DLL + 저장된 Numba 원본 PTX 직접 실행 | 계산 54개, guard 96개 일치 | 길이 1/16/37. 별도 Driver 소비자. 원본 Numba JIT 호출 경로와 구분 |
| 현재 제품 DLL + 어댑터 없는 Numba | 장치 1개 열거 후 차단 | 명시적 가상 타깃에서 `current_context` 단계의 `Driver missing function: cuMemGetInfo` |
| 기존 시험 DLL + Numba JIT 실험 | experimental_pass | 7길이, 2커널, 28 launch, 계산 비교 752개/guard 448개. metadata_adapter=true, dxgi-process-budget |
| 과거 R2v 저장 기록의 현재 트리 감사 | 거부 | `ValueError: topology source/scope`. 과거 고정 소스와 현재 소스가 다름. 과거 결과가 허위라는 뜻도, 현재 버전이 통과했다는 뜻도 아님 |
| 현재 캐시 예산 검사 | refused / cache_limit | `python scripts/cache_budget.py --reserve-gib 0`. 현재 캐시가 기본 40 GiB 한도를 초과. 분석 전부터 초과했는지는 이번 검사만으로 확정하지 않음 |

처음의 일반 Rust 명령 두 개는 기존 출력 위치의 `.dll.lib`를 덮어쓰지 못해 LNK1114/오류 5로 중단됐다. 소스 수정 없이 새 출력 위치에서 두 테스트가 통과했다. 따라서 그 초기 실패를 계산 오답이나 코드 컴파일 오류로 분류하지 않는다. 기존 위치의 덮어쓰기 거부 원인이 ACL인지 다른 파일 상태인지는 이번에 확정하지 않았다.

이번 실행은 개발 중인 작업 트리에서의 확인이다. 새 immutable source checkpoint 전체 검증, Clippy/format 재실행, 과거 전체 native parent chain의 현재 소스 재검증은 수행하지 않았다. 일반 Rust 테스트에서 제외된 7건에는 실제 GPU·별도 프로세스·로컬 NVIDIA producer 파일이 필요한 검사가 포함된다. 별도로 실행한 GPU smoke가 이 7건 전부를 대체하지 않는다.

주요 로그:

- `.cache/analysis-2026-11-13-python.log`
- `.cache/analysis-2026-11-13-rust-isolated.log`
- `.cache/analysis-2026-11-13-runtime-isolated.log`
- `.cache/analysis-2026-11-13-gpu-smoke.log`
- `.cache/analysis-2026-11-13-numba.log`
- `.cache/analysis-2026-11-13/current-driver-ptx-probe.log`
- `.cache/analysis-2026-11-13/vanilla-numba-probe.log`
- `.cache/analysis-2026-11-13/artifact-identities.json`

직접 PTX 진단은 기존 `.cache/numba-0651/ptx-scalar-gpu.py`의 DLL 경로만 이번 빌드로 바꾼 복사본이다. 원본 PTX, 커널 인자, 입력과 정답/guard 검사는 유지했다. 일반 앱의 무수정 실행 증거로 세지 않는다.

## 4. 구현 구조와 현재 범위

실행 흐름은 CUDA 호스트 호출 → CT Driver ABI → fatbin/PTX 해석 → 타입 있는 내부 표현 → SPIR-V 생성 → Intel Level Zero 컴파일/실행이다. 자체 CT Runtime은 CT Driver를 호출하는 별도 계층이다.

| 구성 | 현재 확보한 구현/과거 검증 | 중요한 경계 |
| --- | --- | --- |
| Driver 연결 | 초기화, 열거, context/primary context, 버전별 함수 조회, 메모리/모듈/launch의 제한 집합 | 전체 Driver ABI 아님. 함수 주소를 제공해도 실제 기능이 NOT_SUPPORTED일 수 있음 |
| PTX 번역 | 제한된 32/64비트 정수, FP32, 명시적 FMA, 분기/루프, 여러 entry, 제한된 global | 모든 PTX 명령/타입/버전, 일반 device 함수·libdevice·링킹 아님 |
| 모듈 컨테이너 | raw PTX, 관측된 압축/비압축 fatbin, 후보 검증·용량 기반 선택 | 일반 cubin/SASS-only 프로그램 실행 아님. 대체 이미지 선택은 device linking과 다름 |
| 병렬 계산 | 1D/2D/3D, 제한된 정적 shared memory, CTA-uniform 제어 흐름과 block barrier | 일반 divergent barrier, dynamic shared, warp shuffle/vote, atomics 전반 미지원 |
| 메모리와 수명 | 할당 범위/소유권, H2D/D2H/D2D, typed fill, host allocation, 오류 격리 | UVA/managed/pool/peer 전반, 임의 kernel 주소 접근의 sandbox 보장 없음 |
| 자체 CT Runtime | 등록 ABI, launch, symbol, 메모리, host/stream/event/profiler의 제한 계약 | NVIDIA 공식 Runtime의 초기화 성공과 다름. standalone Cargo workspace라 루트 테스트만으로 검사되지 않음 |
| 비동기 API | 호스트 작업 큐, 소유 stream/event, host lease와 완료/정리 순서 | Driver의 GPU 명령 경로는 직렬·동기식. GPU copy/compute overlap이나 CUDA 전체 비동기 의미를 입증하지 않음 |
| 오류 처리 | 실패 주입, 치명 오류 뒤 차단/자원 보존, stale handle·중복 해제 검사 | 실제 장치 고장·복구, 모든 동시 호출과 무한 churn 검증 아님 |
| 제품 기반 | CLI inspect/run, 실제 Intel 선택/식별, 로컬 MIT 파일과 manifests | 다른 PC 설치·재현, 배포 준비, GitHub 최신 상태는 이번에 확인하지 않음 |

주요 구현 위치: `crates/ct-ptx`, `crates/ct-codegen-spirv`, `crates/ct-backend-intel`, `crates/ct-level-zero`, `crates/ct-cuda`, `crates/ct-cudart`, `scripts/ct.py`.

정적 shared memory의 번역 상한은 16 KiB이며 실제 장치 용량과 함께 제한한다. 이것은 지원 계약의 한계이지 B390 물리 용량 전체에 관한 주장이 아니다.

명시적 `ct-sm52-subset-v1`은 소프트웨어 타깃 정책이다. 실제 Intel 이름을 유지하면서 일부 선택용 메타데이터를 제공한다. NVIDIA CC 5.2 전체 기능 적합성, NVIDIA SM 수, occupancy나 성능 모델을 뜻하지 않는다. 기본 strict 모드와 구분해야 한다.

## 5. 지금까지의 주요 성과와 증거 강도

| 단계 | 무엇을 확인했는가 | 무엇까지 말할 수 있는가 |
| --- | --- | --- |
| M0~M2 | Intel 네이티브 실행, CUDA Driver 연결, 일부 PTX 커널 변환/실행 | 계산 경로의 제한된 실증. M0 일부는 이번 재실행 |
| M3a~M3o | 실행 파일 로더, 함수 조회, 압축 fatbin, 여러 entry, 다차원, 정수/비트/비교 확장과 오류 처리 | 기능별 제한된 검증. 전 CUDA 지원 아님 |
| P05/P06 | primary context/reset, DLL 소비자, D2D/fill, 메모리 메타데이터 | 명시된 ABI와 소유권 계약. NVIDIA 모든 edge case와의 동등성 아님 |
| P09/P04 | 자체 Runtime 초기화·launch·global/symbol, u32/u64 저장소 | 준비된 producer/consumer 조합. 임의 nvcc 바이너리 호환 아님 |
| 후속 Runtime/컴파일러 확장 | host/stream/event, shared/barrier, FMA, alignment, 후보 용량 선택 | 원본 샘플을 위한 기능 기반 확보 |
| 원본 vectorAdd 소스 | 빌드 방식을 조정한 EXE를 자체 CT Runtime/Driver로 실행; 50,000 출력의 독립 검사 | `upstream_adjusted_build`. 내려받은 일반 배포 EXE의 실행과 다름 |
| 원본 matrixMul 소스 | 명시적 가상 타깃에서 CT DLL만 사용하는 nominal 실행; 별도 관찰 실행에서 전체 출력 검사 | 두 고정 shape의 제한된 앱 경로. 일반 행렬곱 크기/입력/성능으로 확대 불가 |
| R0 | 등록부 정리, private source checkpoint, clean CPU와 Intel capture/replay | 고정된 과거 소스의 재현성 강화 |
| R1a | 원본 matrix PTX에 6 seed × 7 shape = 42조합, pass당 118,272 출력과 4,032 guard | 별도 Driver 소비자의 입력 폭 확대. 원본 EXE가 이 입력을 받은 것은 아님 |
| R1b | 제한된 normal/zero 입력, 8조합/5,120 출력, FMA bit 일치와 고정밀 오차 한도 | FMA 반올림의 일부 수치 검증. NaN/subnormal/overflow 등 전 범위 아님 |
| R1c | pass당 Runtime 512 cycle/Driver module 320 cycle, stale/error/live-budget와 omission 대조군 | 단일 호스트 호출자 범위의 반복 수명 검증. 장시간 무누수·동시성 전체 증명 아님 |
| R2~R2v | CuPy와 공식 Runtime 배포본의 실패 경로 분해, 제한된 초기화 prefix 진전 | 앱 실행 성공이 아닌 실패 원인과 초기화 계약의 조사 |
| Numba 후속 | IPC 주소·UUID, 긴 이름/.common/u64 분류 수정, 원본 생성 PTX 직접 실행, 시험 JIT | 현재 제품의 PTX 직접 실행과 시험 구성의 JIT 성공을 분리해야 함 |

위 R1 수치는 각 결과 문서의 과거 고정 소스 기준이다. 이번에 모든 matrix capture/replay를 재실행하지 않았다. 현재 latest 포인터가 가리키는 matrix/breadth/rounding/lifetime 증거의 제품 지문은 `d28b4fe2...`이며 현재 `391ca50e...`와 다르다.

주요 근거: [R0](R0-INVENTORY-SOURCE-RESULTS.md), [R1a](R1A-EXACT-MATRIX-BREADTH-RESULTS.md), [R1b](R1B-MATRIX-ROUNDING-RESULTS.md), [R1c](R1C-RESOURCE-LIFETIME-RESULTS.md), [vectorAdd](UPSTREAM-VECTORADD-RESULTS.md), [virtual target](VIRTUAL-TARGET-RESULTS.md).

## 6. 반드시 구분해야 하는 네 실행 경로

### A. 별도 소비자 → CT Driver → GPU

지원 PTX의 실제 GPU 실행을 확인하는 가장 직접적인 경로다. 이번 현재 DLL의 Numba PTX 검사도 여기에 속한다. CUDA 호스트 앱 전체의 API 요구를 자동으로 충족하지 않는다.

### B. 조정된 빌드의 샘플 EXE → 자체 CT Runtime → CT Driver

원본 vectorAdd/matrixMul 소스의 실제 계산 경로까지 검증한 과거 기록이 있다. 호스트·커널 소스 바이트가 유지돼도 shared cudart/PTX 타깃 등의 빌드 recipe를 바꿨으므로 원래 배포 바이너리 호환과 같지 않다. matrixMul에는 명시적 가상 타깃과 고정 실행 조건도 필요했다.

### C. CuPy/공식 NVIDIA Runtime 배포본 → CT Driver

과거 원본 CuPy 14.2.0의 64값 affine/ReLU 작업은 입력 생성 중 error 35로 끝났고 CUDA 출력은 없었다. 관측된 첫 실제 호출은 CT의 `cuDriverGetVersion`으로, 801/output 0을 반환했다.

그 뒤 공식 Runtime 12.9.79를 대상으로 버전 표현 개입과 private table/context bridge를 사용하는 별도 진단이 진행됐다. R2v에서는 실제 attribute 순서 75,76,15,40,16,17을 관측했다. 마지막 17에서 Driver 801/output 0, Runtime 3/count -1이었다. 기본 제품 DLL의 공식 Runtime 성공으로 읽으면 안 된다.

단순 함수 주소 조회 수백 건은 모두 필수 API 호출을 뜻하지 않는다. 과거 관측의 null lookup 수를 그대로 구현해야 할 필수 함수 수로 계산할 수 없다.

속성 17의 사실에 맞는 보고 근거는 아직 확보되지 않았다. 기존 설치 환경의 Sysman scheduler count가 0이라는 조사 기록은 있으나, 이것만으로 CT 제출 경로의 실행 시간 제한 여부를 확정하지 않았다. 이번에는 해당 OS/드라이버 조사를 재실행하지 않았다.

근거: [CuPy](R2-CUPY-BOOTSTRAP-RESULTS.md), [resolver](R2B-BOOTSTRAP-RESOLVER-RESULTS.md), [R2v](R2V-RUNTIME-TOPOLOGY-RESULTS.md).

### D. Numba → 시험 메모리/링크 DLL + 메타데이터 어댑터 → GPU

이번 기존 실험 구성 재실행은 성공했다. 원본 Numba 패키지 파일을 편집하지 않더라도 실행 프로세스에서 `CtypesFunction.read_func_attr_all`을 교체하므로 바닐라 Numba 지원이 아니다. 실행기는 `finally`에서 원래 메서드를 복원한다.

세 가지 의존성이 있다.

1. **메모리 조회:** 시험 DLL은 DXGI 프로세스 예산/사용량 정책을 쓴다. 장치 전체 가용량과 같은 계약으로 검증되지 않았다. 현재 제품 DLL에는 Numba가 요구한 `cuMemGetInfo`가 없다.
2. **링크:** 시험 DLL의 단일 PTX 전달 경로가 필요하다. 일반 CUDA device linker/LTO/cubin 링크 구현이 아니다. 현재 제품의 JIT 링크 기능 완료로 세지 않는다.
3. **함수 속성:** 시험 프로세스에서 register/shared/local/const/maxthreads 값을 `None`으로 대체한다. `cuFuncGetAttribute`의 올바른 제품 구현이나 전체 Numba에서 속성 생략이 안전함을 증명하지 않는다.

현재 제품 DLL과 기존 시험에 포함된 `ct_cuda.dll`은 서로 다른 파일 해시다. 기존 시험의 JIT 성공은 현재 트리 전체를 재빌드한 제품 DLL의 성공으로 대체할 수 없다. 이번에는 각각의 파일 해시를 별도로 보존했다.

근거: [Numba 실험 실행기](../scripts/numba_jit_experiment.py), [누적 로드맵](CT-EXECUTION-ROADMAP.md) 및 이번 로그.

## 7. 검증 방법에서 확보한 것과 남은 약점

기존 검증은 샘플의 PASS 문구만 수집한 수준보다 강하다. NaN 초기 출력, 원소별 독립 정답, 입력 보존/guard, no-launch/no-copy 대조군, 파일 해시·소스 지문과 별도 프로세스 replay가 있다. R1b에는 별도 유리수 계산으로 확인한 FMA 정답도 있다.

실제 원본 샘플은 NaN 출력에서도 PASS를 낼 수 있었지만, 외부 checker가 이를 거부하는 대조군이 기록돼 있다. 따라서 앱 종료값이나 샘플 PASS만으로 정답을 판단하지 않은 점은 중요한 검증 자산이다.

그러나 다음 한계가 남는다.

- 소수 샘플/닫힌 입력 집합 중심이다. 테스트 수가 커도 일반 앱 다양성과 같지 않다.
- 저장 replay/audit와 GPU 재실행을 구분해야 한다. audit만으로 현재 장치에서 다시 계산한 것은 아니다.
- NVIDIA 원본 하드웨어와의 동작 대조는 여전히 별도다. CPU 수치 oracle은 모든 CUDA 메모리 순서·오류 우선순위까지 검증하지 않는다.
- 이번 CPU 통과는 현재 트리의 검사 결과이며, 현재 소스에 맞는 전체 native qualification을 대신하지 않는다.
- Numba 시험 DLL 구현·빌드 recipe·의존성 일부가 무시되는 `.cache`에 있다. 공개 저장소만 받은 사용자가 같은 실험을 수행할 수 있다는 근거가 없다.
- 원본 EXE 크기 확대, 동시 호스트 호출, 실제 장치 고장/복구, 다른 Intel PC, 장시간 안정성은 미완료다.

## 8. 정리 과정에서 확인한 불일치와 관리 문제

| 항목 | 확인 내용 | 영향 |
| --- | --- | --- |
| README와 로컬 최신 상태 | README는 Runtime 진단/초기 Driver 중심이며 후속 Runtime 샘플·R1·Numba 실험 구분을 충분히 설명하지 않음 | README만 읽으면 로컬 성과를 과소평가하거나 최신 경계를 놓칠 수 있음 |
| PTX 계약 문서 | 문서에는 식별자 128자, unannotated u64의 미사용/정수 scalar 거부가 남아 있음. 현재 parser는 256바이트 상수와 제한된 scalar 분류를 사용 | 문서와 코드가 일치하지 않는 구체적 사례. 일반 u64 지원으로 무조건 넓혀 쓰면 안 됨 |
| 로드맵의 시점 혼재 | 오래된 “다음 작업/미구현” 문장과 후속 완료 기록이 한 문서에 공존 | 머리말·최신 결과·소스를 함께 읽어야 함. 문서 날짜만으로 최신성을 판단할 수 없음 |
| 등록부와 Numba | `applications.json`에는 vectorAdd/matrixMul/CuPy가 있으나 Numba 항목은 없음 | 최신 비샘플 실험의 버전·상태·산출물 연결이 중앙 등록부에 없음 |
| 루트/별도 Runtime workspace | 루트 `Cargo.toml` members에 `ct-cudart`가 없고 자체 `[workspace]` 보유 | 루트 테스트 통과만 보고 Runtime도 검증했다고 하면 잘못됨. 이번에는 둘 다 실행 |
| 미커밋·비추적 변경 다수 | 시작 시 102/326개 | 현재 로컬과 특정 공개 커밋을 동일시할 수 없음. 기존 개발물은 그대로 보존 |
| 소스와 저장 증거 시점 차이 | 과거 R2v/current latest matrix 지문과 현재 소스 불일치 | 현재 버전의 전체 통과 주장 전에 새 고정 소스 검증이 필요 |
| 캐시·도구 의존성 | SDK, 컴파일러, wheel, 시험 DLL, 원시 결과가 로컬 캐시에 분산 | 다른 PC/깨끗한 clone 재현 비용이 불확실. 이번에는 정리/삭제하지 않음 |
| 개발 저장공간 한도 | 분석 후 현재 캐시 검사가 예약 0에서도 `cache_limit`으로 거부됨 | 예산 검사가 적용된 새 실험 전에 보존할 증거와 재생성 가능 빌드를 구분해야 함. 과거 native closure의 임의 삭제로 해소하면 안 됨 |

위 문서 차이는 이번에 발견한 관리·표현 문제이며, 그 자체로 GPU 계산 오답을 입증하는 것은 아니다. 분석 중 기존 계약/결과 문서를 덮어쓰지 않았다.

로컬 MIT 라이선스 파일과 workspace/package 선언은 존재한다. 원본 저장소의 commit/push/배포 상태나 제3자 SDK·가중치 등의 재배포 권한을 이번 분석으로 확정하지 않는다.

## 9. 기술적 판단 — 사실과 해석의 구분

**관측 사실:** 현재 소스에서 제한된 Numba 생성 PTX가 실제 B390에서 실행되고 정답이 맞는다. 기존 샘플·수치·수명 검증 기록이 있으며, 현재 CPU 회귀도 통과한다. 원본 Numba의 현재 제품 경로와 CuPy/공식 Runtime 경로에는 아직 실제 차단점이 있다.

**이 사실에서 가능한 해석:** PTX를 Intel 실행 코드로 옮기는 핵심 경로는 제한된 범위에서 실증됐다. 지금의 주요 미완료 영역에는 호스트 API/초기화·메모리/함수 메타데이터·JIT 계약과 더 넓은 커널 의미론이 포함된다. 단순한 아이디어 단계라고 부르는 것은 관측 결과와 맞지 않는다.

**이 사실로 확정할 수 없는 것:** 남은 문제가 모두 쉽게 해결된다는 주장, 특정 앱 다음에 다른 앱도 자연스럽게 지원된다는 주장, 범용 CUDA 대체의 완성 가능성·기간·비용·속도. 몇 가지 초기화 항목을 해결한 뒤 추가 요구가 얼마나 나올지는 아직 모른다.

수치 정확성과 앱 호환성은 각각 문턱을 가진다. 커널이 맞아도 앱 초기화가 실패할 수 있고, 초기화가 성공해도 실제 워크로드의 명령·라이브러리·동기화 요구는 남을 수 있다.

## 10. 이 분석을 바탕으로 한 후속 순서 제안

이 절은 제안이며 새 기능 구현을 수행한 기록이 아니다.

1. **현재 기준점 고정:** 기존 변경을 보존한 채 제품/시험 DLL/입력/도구/증거의 역할을 묶는다. 현재 버전 기준의 CPU·관련 native 결과를 연결하고, 과거 기록은 과거 소스에 계속 귀속한다. 새 대규모 실험 전에 캐시 예산 거부도 보존 정책에 맞게 해결한다.
2. **문서 정합성:** README·PTX 계약·앱 등록부에 제품 구현, 과거 검증, Numba 시험 구성을 구분해 반영한다. 성공 범위를 넓혀 적는 방식으로 해결하지 않는다.
3. **비샘플 경로 선택:** 현재 Numba 직접 PTX/JIT 실험을 바탕으로 원본 Numba 호출 경로를 주 대상으로 삼을지 판단한다. CuPy의 공식 Runtime/private bootstrap 조사는 별도 경로로 유지한다.
4. **Numba 차단점의 계약부터 검토:** 메모리 조회의 의미와 출처, 단일 PTX 링크의 제한, 함수 속성의 실제 Intel 자원값/필수 소비 여부를 따로 확인한다. 시험 성공을 위해 쓴 값을 정식 CUDA 성공값으로 자동 채택하지 않는다.
5. **실제 작업 하나의 완료:** 어댑터 조건과 허용 지원 범위를 명시하고, 그 범위에서 입력→GPU 계산→전체 결과/guard→반복·정리까지 검증한다. 어댑터 없는 실행과 시험 구성 실행을 계속 별도 기록한다.
6. **타 PC·성능:** 다른 Intel 모델/깨끗한 설치에서 재현한 후 실제 입력의 cold/warm·전송·전체 시간과 메모리를 측정한다. 성능 합격 기준을 결과를 보고 뒤늦게 바꾸지 않는다.

현재까지의 사실만으로 개발을 중단해야 한다는 결론도, 성공을 확신해야 한다는 결론도 나오지 않는다. 다음 판단에 필요한 것은 현재 소스의 고정된 검증과 비샘플 앱의 계약상 차단점 해소 여부다.
