# Profiler 제어와 matrixMul import 연결 완료 — 2026-10-26

현재 검증 프로파일은 **Driver 46개 / Runtime 40개**다. 대상 원본 matrixMul의 미지원 Runtime 함수명은 **2개에서 0개**로 줄었다. 이는 함수명 연결 단계의 완료이며 matrixMul 실행이나 범용 CUDA 완성을 뜻하지 않는다.

## 구현 정책

`cudaProfilerStart`와 `cudaProfilerStop`을 명시적인 **수집기 없는 호환 모드**로 구현했다. 정상적인 Runtime/current context를 확보한 뒤 이미 게시된 비동기 큐 오류를 읽고, 오류가 없으면 성공으로 반환한다. 진행 중 작업을 기다리거나 오류를 지우지 않는다. worker를 시작하거나 queue node를 예약하지 않으며 가짜 capture 상태, trace 파일, native profiler 연결을 만들지 않는다.

[NVIDIA CUDA12 Runtime 문서](https://docs.nvidia.com/cuda/archive/12.0.1/cuda-runtime-api/group__CUDART__PROFILER.html)는 활성 도구의 context 제어, 반복 호출 및 이전 비동기 오류 가능성을 설명한다. 위 no-collector 동작은 CT의 명시적인 제한 정책이다. 실제 데이터 수집이나 Nsight/CUPTI/Intel profiler 연동 및 NVIDIA 참조 실행과의 일치는 검증하지 않았다. 세부 계약은 [Runtime profiler](compatibility/runtime-profiler.md)에 있다.

## 검증

- 테스트를 먼저 실패시킨 뒤 구현했다. Runtime unit 테스트 **129개** 통과. 새 테스트는 반복 호출, 초기화 오류, raw context 오류 201→49 변환, 이미 Runtime 오류인 49의 보존, 대기 중 작업을 기다리지 않는 동작, 동기화 호출·worker/node 생성 없음 및 나중 오류 보존을 확인한다.
- 공식 profiler header를 인증된 CUDA12.0.76 패키지에서 추출해 hash를 검사했다. 공식 헤더와 CT 헤더의 별도 C++ type assertion 및 ABI 출력이 일치했다. Native consumer가 Runtime export 40개와 실제 호출을 확인했다.
- 실제 Intel 환경에서 정상 반복 호출, Driver 부재 오류 35, native context 동기화가 1을 반환하는 trap, 완료된 benign 비동기 복사 오류 1의 전달을 검사했다. 정상 profiler 호출이 TLS last error를 지우지 않고 초기화 후 caller context를 보존함을 확인했다.
- sync trap은 오류를 전달하는 숨은 native 동기화를 검출한다. 동기화 호출 자체가 없다는 더 강한 근거는 unit fake의 호출 횟수와 소스 검토다.
- 실제 nvcc 프로그램에서 profiler 호출이 queued 복사·이벤트·커널 실행을 감싼다. 세 stream 경로의 96개 출력값을 Python이 독립 비교했고 두 입력이 통과했다. 커널/복사 생략 provider는 수치 실패 42로 검출됐다.
- 같은 새 빌드 체인에서 기존 Runtime 이벤트·Driver 이벤트·optional symbol·host/stream/attribute·queued copy 회귀 및 누락 제어를 통과했다.
- 기존 default/kernel/symbol/u64 pure ABI 소비자 네 개도 새 Runtime40 DLL로 다시 컴파일·실행해 통과했다.
- Python 회귀 테스트 **195개**, Rust workspace 테스트, workspace/Runtime clippy 및 format 검사 통과. 일반 workspace의 기존 외부 자료 의존 테스트 3개와 명시 hardware clock probe 1개는 제외된다.
- 독립 읽기 전용 검토에서 blocker가 발견되지 않았다. 실제 profiling 구현/성능 증거로 분류하지 않는다.

## Import 0개 상태에서도 실행하지 않는 진단

기존 진단은 미지원 import 때문에 CLI run이 거부되는 것을 확인했다. 마지막 두 함수가 생기면 그 명령은 더 이상 실행 방지 장벽이 아니므로, matrixMul 진단을 **엄격한 PE inspect와 오프라인 번역만 수행**하도록 변경했다.

Triage schema2는 알려지지 않은 import가 있으면 blocked/strict inspect2, 없으면 compatibility-unproven/strict inspect0을 정확히 구분한다. schema1 기록을 새 증거로 재분류하지 않는다. 명령·출력·실행 여부·exit code 타입까지 검증하며 현재 소스에서 검증된 vectorAdd DLL manifest를 인증한다.

새 원본 matrixMul 빌드에서 미지원 Runtime import는 `[]`, strict inspect는 0이었다. 원본 EXE나 GPU kernel은 실행하지 않았다. PTX는 계속 `.shared` line 32에서 거부되며 shared 선언 4개, block barrier 4개, FMA 48개가 관찰된다. 공유 메모리·스레드 동기화·fused arithmetic·장치 선택 정책은 다음 별도 구현 과제다.

## 고정 소스 증거

Source fingerprint: `2a166f3f9a69b204308452232d5bdfb7ce67b01e27e71cff270f0789a03a502c`.

| 검증 | 로컬 manifest |
| --- | --- |
| Profiler/no-collector/native/nvcc 및 부모 회귀 | `.cache/runtime-attribute-runs/799ab24f4d7243cdaa49b82155f88cb5/profiler-manifest.json` |
| 기존 pure ABI 4개 | 같은 폴더의 `existing-abi-3661af399d884f3ba11164265f92057f/manifest.json` |
| 원본 vectorAdd 새 빌드 | `.cache/upstream-vectoradd-runs/233eb13588b842019d53c323d60bc3f5/manifest.json` |
| 원본 vectorAdd 동일 바이너리 재실행 | 같은 폴더의 `replay-4bed59786b7a4865beef50d358606765.json` |
| 원본 matrixMul schema2 진단 | `.cache/matrixmul-triage/8274f0c1c94c4dd7a8da09d545b08e97/manifest.json` |

Profiler manifest SHA-256: `77b2bb950176e3da7454ff7414ddf3c21e8ba2e787551ecb3f281db565f7e20f`.

재현 명령:

```powershell
python scripts/run_profiler.py
python scripts/run_upstream_vectoradd.py
python scripts/triage_matrixmul.py
```

현재 Windows x64 Intel 및 인증된 로컬 CUDA producer/compiler 환경의 진단 결과다. 원본 앱 소스는 수정하지 않았고 CT import library를 쓰는 빌드다. release/framework/다른 GPU 호환성·성능 우위 또는 전체 CUDA 지원으로 확대 해석하지 않는다.

원시 로그·바이너리·vendor 자료는 무시되는 `.cache/`에만 두었다. 사용자 소유 기존 파일 11개를 보존했으며 staging·commit·upload는 하지 않았다.
