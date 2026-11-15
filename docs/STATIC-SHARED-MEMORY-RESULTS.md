# Static shared memory results — 2026-10-27

커널 내부의 고정 크기 공유 메모리를 Intel GPU 실행에 연결했다. genuine nvcc가
만든 정수·실수 커널이 각각 배열 두 개와 barrier 세 개를 사용해 이웃 스레드의
값을 교환한다. 기존 CUDA Runtime/Driver 경로를 통하며 앱에 CT 전용 커널 호출을
추가하지 않는다. Driver46 / Runtime40 프로파일은 그대로다.

## 지원 범위와 원리

커널 내부의 `.shared .align {4,8,16} .b8` 및 32비트 typed 배열을 지원한다.
선언당 양수·4의 배수인 byte extent, 커널당 최대16개·정렬 padding을 포함한16KiB로
제한한다. 하나의 기본 블록이 return으로 끝나야 하며, 기존 canonical `bar.sync 0`
검증을 유지한다. 32비트 정수/실수의 일반·volatile 읽기·쓰기를 구현했다.

공유 주소는 객체 이름과 상대 byte offset을 함께 추적한다. mov·scalar add·unsigned
U32->U64 widening·증명된 cvta.to.shared만 객체 정체성을 보존한다. 레지스터가
덮어써지면 출처도 갱신한다. 다른 객체 주소끼리의 연산, 주소를 데이터로 내보내기,
global 메모리와의 혼용, 잘못된 정렬, 증명 불가능한 주소는 GPU 제출 전에 거부한다.
parser뿐 아니라 SPIR-V 생성기도 공개 IR의 공유 메모리 검증을 다시 수행한다.

각 커널의 각 배열은 독립된 SPIR-V Workgroup U32 배열로 생성한다. AccessChain은
byte offset을4로 나눈 인덱스를 사용한다. F32는 저장·읽기 값의 비트만 변환하므로
포인터의 storage class를 바꾸지 않는다. 같은 이름의 배열을 선언한 두 엔트리도
저장 공간을 합치지 않는다.

동적 인덱스의 범위와 프로그램의 경쟁 상태는 호출자 책임이다. 초기화하지 않은
공유 메모리의 값은 보장하지 않는다. extern/동적 공유 메모리, 64비트·vector·atomic
공유 접근, 분기·반복문 커널과 부분 CTA barrier는 아직 지원하지 않는다.
이는 신뢰하지 않는 PTX를 격리하는 메모리 sandbox가 아니다.

## 검증 결과

- 실제 nvcc 두 엔트리의 보존 PTX와 fatbin PTX 토큰 전체를 비교했다. 각 엔트리에
  512-byte 배열2개, volatile shared load/store 각3개, barrier3개를 확인했다.
- Intel 실행은64 threads ×3 blocks,128 threads ×4 blocks를 모두 검증했다.
  서로 다른 seed2개에서 매번 정수704개·실수704개 출력 전체를 독립 Python oracle과
  비교하고, C++에서도 입력 보존과 각 입력·출력 버퍼 양 끝 guard를 검사했다.
  실수 데이터는 정확히 표현되는 작은 정수와 덧셈으로 구성했다. 일반 F32 수치
  정확도나 성능 benchmark로 확대 해석하지 않는다.
- 커널 실행 생략·메모리 복사 생략 대조군은 각각 exit42로 오류를 검출했다.
- 실제 고정 `spirv-val --target-env opencl1.2`가 정상 모듈을 통과시키고 잘못된
  Workgroup 변수 storage class 변형을 거부했다. 별도 구조 검사는 객체 alias
  변형을 거부했다. 변형 모듈과 미지원 PTX는 GPU에 제출하지 않았다.
- 메모리 공간 혼용, 잘못된 정렬, extern shared, CFG, truncation으로 위조한
  shift-count 정렬 증명은 오프라인 번역에서 거부했다. 입력·stderr도 hash로 고정했다.
- Python199개, Runtime Rust129개, Rust workspace 테스트가 통과했다. 기존 ignored
  테스트4개는 실행 증거에서 제외한다. workspace clippy는 `-D warnings`로 통과했고
  workspace 및 Runtime format 검사도 통과했다.

독립 검토는 U64->U32 변환 후 원래 상수값이 정렬 증명에 남는 문제를 발견했다.
4294967296이 U32에서0이 되는 shift-count 사례를 실패 테스트로 재현한 뒤, scalar
conversion에서 전체 상수 정보는 버리고 보존되는 하위 정렬 비트만 유지하도록
고쳤다. parser와 직접 변형한 공개 IR의 회귀 테스트를 추가했다. 재검토에서 추가
blocker는 발견되지 않았다.

## 소스 고정 증거

Source fingerprint: `739ca719637b696311cc67cedd5984226ad293f8a22d26b44d3a476b27e6a8ae`.

Shared manifest SHA-256: `01a4f33ad5c3299962768d1903386ace0cf95afe55dd317c2c3f380c111fc974`.

| 검증 | 로컬 기록 |
| --- | --- |
| 공유 메모리 nvcc/native 및 대조군 | `.cache/runtime-attribute-runs/5af337ff046c408a8d8ccde0497ee0f8/static-shared-manifest.json` |
| 동기화 및 이전 Runtime/native 회귀 | 같은 폴더의 `block-barrier-manifest.json`, `profiler-manifest.json` 등 부모 기록 |
| 원본 vectorAdd 새 빌드 | `.cache/upstream-vectoradd-runs/86e4ad5c4ef94958af889d1c20e2dc4c/manifest.json` |
| 같은 vectorAdd 바이너리 재실행 | 같은 폴더의 `replay-13d26ac506394da980100d3c50a1c0fe.json` |
| 원본 matrixMul 오프라인 진단 | `.cache/matrixmul-triage/1cd2e4a778764ce3befbbfbcca8f964b/manifest.json` |

각 기록은 소스 fingerprint, 바이너리·입력·출력 hash 및 부모 manifest hash에
연결된다. 현재 Windows x64 Intel·로컬 CUDA producer/compiler 환경의 진단이다.
다른 Intel 장치, AMD/NVIDIA, framework 전체 지원, CUDA 상위 호환·성능 우위 또는
release 판정을 의미하지 않는다.

vectorAdd의 새 캡처와 동일 바이너리 replay가 통과했다. 원본 소스를 수정하지 않고
CT import library를 사용한 빌드이며, 원본 NVIDIA 배포 바이너리 무수정 실행과는
구분한다. matrixMul의 미지원 Runtime import는0개·strict inspect exit0이고,
오프라인 번역의 첫 거부는 `.shared` line32에서 `bra.uni` line51로 이동했다.
shared 선언4개, barrier4개, FMA48개는 그대로 관찰된다. matrixMul 앱과 GPU 커널은
실행하지 않았다. 다음 과제는 uniform 분기·반복문 및 barrier 도달 증명이며,
필요한 fused arithmetic·장치 선택 정책도 전체 앱 실행 전에 검증해야 한다.

재현 명령:

```powershell
python scripts/run_static_shared.py
python scripts/run_upstream_vectoradd.py
python scripts/run_upstream_vectoradd.py --replay <new-vectoradd-manifest>
python scripts/triage_matrixmul.py
```

원시 로그·바이너리·vendor 자료는 무시되는 `.cache/`에만 둔다. 사용자 기존 파일
11개를 hash로 보존하며 staging·commit·upload는 하지 않는다.

[설계·구현 계획](superpowers/plans/2026-10-27-static-shared-memory.md),
[지원 계약](compatibility/ptx-profile.md),
[NVIDIA PTX 문서](https://docs.nvidia.com/cuda/archive/12.1.1/parallel-thread-execution/index.html),
[Khronos SPIR-V 명세](https://registry.khronos.org/SPIR-V/specs/unified1/SPIRV.html).
