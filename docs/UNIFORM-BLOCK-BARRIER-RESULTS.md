# Uniform block barrier results — 2026-10-27

CUDA의 `__syncthreads()`가 생성하는 정형 `bar.sync 0;`의 첫 지원을 구현했다.
실제 nvcc 프로그램을 CT Runtime/Driver로 연결해 현재 Intel GPU에서 실행했다.
지원 범위는 하나의 기본 블록이 return으로 끝나는 커널이다. 모든 스레드가
동일한 barrier 순서를 실행한다는 것을 이 구조 제한으로 보장한다.

공유 메모리 저장 공간, 분기·반복문 안의 barrier, count/predicate/다른 barrier
ID, warp·cluster 동기화는 아직 지원하지 않는다. Driver46 / Runtime40 함수
프로파일은 그대로이며, API 함수 개수 증가와 별개의 PTX 실행 기능이다.

## 구현과 거부 경계

- PTX IR에 BlockBarrier를 추가하고 parser와 SPIR-V 생성기 양쪽에서 구조를 검증한다.
- SPIR-V `OpControlBarrier`의 execution/memory scope는 Workgroup(2), memory
  semantics는 SequentiallyConsistent | WorkgroupMemory | CrossWorkgroupMemory
  (0x310)이다. 메모리 fence만으로 대체하지 않는다.
- 정형 지원 밖의 입력은 GPU 제출 전에 거부한다. 기존 barrier 없는 CFG 지원은 유지한다.
- 예전에 미지원 명령 예제로 쓰던 `bar.sync 0`은 여전히 미지원인 `bar.sync 1`로
  바꿔 기존 module-selection/CLI 거부 검증의 목적을 유지했다.

설계와 근거 자료는 [구현 계획](superpowers/plans/2026-10-27-uniform-block-barrier.md),
지원 경계는 [PTX 프로파일](compatibility/ptx-profile.md)에 기록했다.

## 실제 실행과 대조군

genuine nvcc가 생성한 두 개의 서로 다른 커널 엔트리에서 각 3개의 barrier를
확인했다. 보존 PTX와 원본 fatbin의 모든 PTX 토큰을 비교했다. fixture는 global
scratch에 값을 쓰고 barrier를 거쳐 이웃 스레드의 값을 읽는 과정을 반복한다.
쓰기와 읽기 단계 사이를 분리해 데이터 경쟁을 피한다.

64 threads × 3 blocks와 128 threads × 4 blocks를 각각 실행하고, 서로 다른
무작위 seed 2개에서 매번 704개 output 값 전체를 독립 Python oracle과 비교했다.
C++ 검사도 scratch 최종값, input 보존, 각 버퍼 양 끝 guard를 확인했다.
커널 실행 생략 및 복사 생략 대조군은 각각 예상한 데이터 오류(exit42)를 검출했다.
barrier 제거가 모든 GPU에서 반드시 수치 오류를 낸다는 주장은 하지 않는다.

실제 고정 `spirv-val --target-env opencl1.2`가 정상 모듈을 통과시키고 undefined
scope ID 변형을 거부했다. 별도의 exact operand 검사가 Invocation scope 변형을
거부했다. 이 scope 변형은 고정 validator 자체에서는 통과하므로, validator 통과와
CUDA 동기화 의미 검증을 구분한다. 변형된 모듈은 GPU에 제출하지 않았다.
다른 ID, counted barrier, 분기에서 도달하는 barrier도 오프라인 번역에서 거부했다.

## 회귀 및 증거

Python 197개, Runtime Rust 129개 테스트와 Rust workspace 테스트가 통과했다.
workspace의 기존 ignored 테스트 4개는 실행 증거에 포함하지 않는다.
새 Rust 검증은 parser 3개, SPIR-V operand 1개, 직접 변형한 공개 IR 거부 1개다.
workspace clippy와 workspace/Runtime format 검사도 통과했다.
독립 읽기 전용 검토에서 구현 blocker는 없었고, 거부 입력/출력의 최종 hash 검증
누락 지적은 최종 캡처 전에 보완했다.

Source fingerprint: `a714d645a026b6f7c9216f484413d8b8dd2720663bd884f4ea8c1ed922f7617c`.

| 증거 | 로컬 기록 |
| --- | --- |
| barrier 및 부모 Runtime/native 회귀 | `.cache/runtime-attribute-runs/f8ee9bc4b9324b52bde57c33bd9a5f4b/block-barrier-manifest.json` |
| 기존 profiler 및 부모 회귀 | 같은 폴더의 `profiler-manifest.json` |
| 원본 vectorAdd 새 빌드 | `.cache/upstream-vectoradd-runs/d5a26f1d672748e3b029e5ec8ce5d30d/manifest.json` |
| 같은 vectorAdd 바이너리 재실행 | 같은 폴더의 `replay-4ae4eca191e748f788175696f9bac99a.json` |
| 원본 matrixMul 오프라인 진단 | `.cache/matrixmul-triage/2d5548dec4054a738018a2f929ef236c/manifest.json` |

vectorAdd 새 캡처와 replay가 모두 통과했다. 이는 원본 앱 소스를 수정하지 않고
CT import library로 빌드한 현재 Windows x64 Intel 환경의 진단 증거다.
다른 Intel 장치, AMD/NVIDIA, framework 전체 지원, 성능 우위 또는 release 판정을
의미하지 않는다.

matrixMul 재진단에서 미지원 Runtime import는 0개, strict inspect exit는 0이다.
실행 호환성은 여전히 unproven이며, 오프라인 번역은 `.shared` line32에서 거부된다.
shared 선언 4개, barrier 4개, FMA 48개가 관찰된다. 원본 앱과 GPU 커널을 실행하지
않았다. 다음 구현은 static shared 저장 공간과 주소·정렬 검증이며, 이후 반복문
등에서의 uniform barrier 증명, 필요한 fused arithmetic, 장치 선택 정책을 거쳐
실제 matrixMul 전체 실행을 검증해야 한다.

재현 명령:

```powershell
python scripts/run_block_barrier.py
python scripts/run_upstream_vectoradd.py
python scripts/run_upstream_vectoradd.py --replay <new-vectoradd-manifest>
python scripts/triage_matrixmul.py
```

원시 로그·컴파일러 산출물·vendor 자료는 무시되는 `.cache/`에만 둔다.
사용자 기존 파일 11개의 hash를 보존했고 staging·commit·upload는 하지 않았다.
