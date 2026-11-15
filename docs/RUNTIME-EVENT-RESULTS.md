# Runtime 이벤트 5개 구현 결과 — 2026-10-26

후속 [profiler/import 연결 결과](PROFILER-IMPORT-CLOSURE-RESULTS.md)에서 Runtime40 및 대상 import 누락0개를 검증했다. 아래는 이벤트 단계의 기록이다.

Driver 이벤트를 Runtime의 비동기 작업 큐와 연결했다. 지원 프로파일은 **Driver 46개 / Runtime 38개**다. 원본 matrixMul의 미지원 Runtime import는 이벤트 5개가 빠져 **7개에서 2개(`cudaProfilerStart`, `cudaProfilerStop`)**로 줄었다. 원본 matrixMul 실행 완료를 뜻하지 않는다.

## 새 동작

`cudaEventCreate`, `cudaEventRecord`, `cudaEventSynchronize`, `cudaEventDestroy`, `cudaEventElapsedTime`을 구현했다. 이벤트는 생성한 context에 속하고 process당 live 128개 / lifetime 4096개로 제한한다. opaque token을 재사용하지 않는다. Driver의 이벤트 함수 5개는 기존 소유·고정된 DLL에서 완전한 묶음으로 지연 로딩한다. 기본 15개 및 kernel 5개 로딩과 분리했다.

record마다 독립적인 완료 객체를 만든다. 큐가 작업을 수락한 뒤에만 최신 기록으로 게시하므로 등록 실패는 이전 기록을 보존한다. synchronize는 호출 시 잡은 기록만 기다리며 나중의 재기록이 기존 대기를 늘리지 않는다. destroy는 논리적으로 즉시 닫고 native 삭제를 순서대로 큐에 넣는다. 앞서 대기하던 호출은 별도 완료 객체로 안전하게 끝난다.

elapsed는 전체 큐를 기다리지 않고 최신 기록의 준비 상태를 검사한다. 미완료는 600, 미기록은 400이며 오류 시 출력은 보존한다. 이벤트의 Driver 오류만 별도 경로에서 한 번 변환해 400/600을 보존한다. 기존 메모리 API의 오류 변환 계약은 바꾸지 않았다. 준비 상태 검사와 native 시간 조회는 context gate로 보호하고 두 이벤트의 잠금 순서를 고정했다.

시간은 실제 GPU counter 차이를 사용한다. CPU dispatch·idle 간격을 포함할 수 있으며 커널만의 실행 시간이나 교정된 벤치마크를 주장하지 않는다. 기본/CT 소유 stream을 지원하지만 native queue 병렬 실행, copy/compute overlap, PTDS, Query/CreateWithFlags, interprocess 이벤트는 지원 범위에 포함하지 않는다. 자세한 규칙은 [Runtime 이벤트 계약](compatibility/runtime-events.md)에 있다.

## 오류 및 동시성 검증

Runtime unit 테스트 **126개**를 통과했다. 새 테스트 14개는 아래를 포함한다.

- 작업이 commit보다 먼저 끝나도 완료가 보존되는 순서.
- 큐 등록 실패 시 이전 기록 및 열린 핸들 보존.
- 재기록·pending 삭제 후에도 이전 snapshot 대기가 안전하게 끝나는 수명.
- 다른 context, 삭제된 token, live/lifetime 한도와 같은 이벤트 자기 비교.
- 두 이벤트를 반대 순서로 동시에 조회해도 잠금이 교착되지 않는 경로.
- 정상·이전 오류로 생략·panic·accepted job 폐기의 완료 통지 및 오류 뒤 cleanup 실행.
- optional event5의 개별 누락·캐싱과 400/600 오류 변환.
- 잘못된 공개 인수의 GPU 없는 사전 거부와 출력 보존.

독립 검토에서 `pending=0`을 먼저 게시하면 장치 동기화 직후에도 이벤트가 600으로 보일 수 있는 경쟁 상태를 발견했다. 완료 통지를 막는 테스트로 먼저 실패를 재현한 뒤, 이벤트 완료 게시를 먼저 하고 context 대기를 깨우도록 수정해 통과했다. 후속 검토에서 추가 실행 코드 blocker는 발견되지 않았다.

## 실제 GPU 및 회귀 검증

- 공식 CUDA 타입을 사용하는 native consumer에서 38개 export와 이벤트 5개 호출을 확인했다. 공식 헤더/CT 헤더의 독립적인 함수형 검사도 컴파일했다.
- 새 native 이벤트 호출에서 양의 GPU 시간, 미기록/자기 비교/역순/재기록, 다른 context, 삭제 후 거부 및 caller context 보존을 확인했다.
- Driver 없음, 이벤트 함수 5개 각각의 누락, 외부 DLL로의 forwarding을 구분했다. 실제 누락 export와 forwarding 주소를 확인하고, 오류 35 이후에도 기존 메모리 할당·동기화·해제가 동작함을 검사했다.
- 실제 nvcc 소비자에서 이벤트가 queued HtoD/DtoD/DtoH 및 커널 실행을 감싼다. flags0 stream의 event synchronize, flags1 stream의 device synchronize, default stream의 free fence 경로에서 결과를 검사한다. Python이 세 경로의 총 96개 출력값을 독립적으로 계산해 비교한다.
- 커널/복사 생략은 수치 실패 42, record 생략은 elapsed의 정확한 400 실패 지점, 시간 0 강제는 시간 검사 실패 43으로 검출한다.
- 기존 Driver 이벤트, host allocation, owned/default stream, attribute, queued copy/launch 제어도 같은 빌드 체인에 포함했다.
- Rust workspace 테스트 및 workspace/Runtime clippy·format 통과. 일반 workspace에서는 기존 외부 자료 의존 테스트 3개와 명시 hardware clock probe 1개가 제외된다.
- Python 회귀 테스트 **193개** 통과. 이벤트가 지원되면서 기존 loader의 미지원 입력 예시를 아직 미지원인 profiler 함수로 바꾸고, strict rejection과 진단 규칙이 계속 유지됨을 확인했다.

탐색 중 forwarding 제어 DLL의 import library 누락을 발견해 빌드 명령을 수정했다. 추가 ABI 수동 빌드는 기존 symbol harness의 외부 헤더·함수 분리 옵션을 그대로 적용해 확인했다. 소스 수정 중 fingerprint가 바뀐 탐색 결과는 최종 증거로 재분류하지 않았다.

## 남은 범위

함수 2개를 채운 뒤에도 matrixMul에는 `.shared` 저장소, `bar.sync`, 필요한 fused arithmetic, 장치 선택 정책의 별도 구현·검증이 필요하다. 현재 offline 번역은 `.shared` line 32에서 거부되고 원본 앱은 실행하지 않았다. 다른 Intel 장치, AMD/NVIDIA 동작 일치, 일반 AI framework, 성능 우위 또는 release qualification은 아직 주장하지 않는다.

원시 로그·vendor 자료·바이너리는 무시되는 `.cache/`에만 보관한다. 기존 사용자 소유 파일 11개의 hash를 보존했고 staging·commit·upload는 하지 않았다. 개인정보 패턴 검사는 완전한 보안 감사와 구분한다.


## 고정 소스 증거

최종 source fingerprint는 `fbdf1447954ec0f1656aeb38406e72c02504a0cd0191d61e24b774aad06f8ee8`이다. 아래 원시 증거는 모두 무시되는 로컬 cache에 있다.

| 검증 | Manifest |
| --- | --- |
| Runtime 이벤트/optional 제어/nvcc 수치 및 누락 제어 | `.cache/runtime-attribute-runs/e78aa606ce4341cb9ced605dc1304de1/runtime-events-manifest.json` |
| 기존 default/kernel/symbol/u64 pure ABI | 같은 폴더의 `existing-abi-70f37f137f454ba09169aad460f97c80/manifest.json` |
| 원본 vectorAdd 새 빌드 | `.cache/upstream-vectoradd-runs/834f9c59cd9349f3a6221248bd21f70f/manifest.json` |
| 원본 matrixMul 실행 없는 검사 | `.cache/matrixmul-triage/241aa66126a8490983cf6018b747ca9e/manifest.json` |

Runtime 이벤트 manifest SHA-256은 `03fd6ca6d46098ac70697ab8ebc7f0ead2992543a8311f25f96ef9ab9b089046`이다. 부모 Driver 이벤트/queued copy/host/stream/attribute manifest와 모든 실행 bundle의 바이너리 hash 및 source fingerprint를 확인했다.

Runtime 이벤트 positive 2회는 모두 통과했고, 누락 제어 4개는 의도한 실패를 냈다. Native optional 제어 8개는 각 결과를 엄격하게 검사했다. 원본 vectorAdd 소스는 수정하지 않았고 CT import library를 사용한 진단 빌드다. 일반 제품/clean-lane qualification으로 재분류하지 않는다.

재현 명령:

```powershell
python scripts/run_runtime_events.py
python scripts/run_upstream_vectoradd.py
python scripts/triage_matrixmul.py
```

첫 명령은 실제 GPU 작업과 기존 native 회귀를 포함한다. 인증된 로컬 CUDA producer/compiler 자료와 현재 Windows x64 Intel 검증 환경이 필요하다. 추가 전체 소스 재검증 중 vectorAdd 빌드에 한 차례 디렉터리 생성 권한 오류가 있었으며, 새 폴더에서 재실행해 통과했다. 이 실패 결과는 성공 증거로 사용하지 않았다.

최종 vectorAdd 재실행도 통과했다: 같은 폴더의 `replay-ae3e9c2608fd4921ab85eb9e9733ca10.json`. 실행 파일·DLL을 바꾸지 않은 재현 검사다. 최종 공개 대상 패턴 검사 137개 및 기존 사용자 파일 11개의 hash 확인을 통과했다.
