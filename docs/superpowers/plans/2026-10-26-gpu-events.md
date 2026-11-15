# GPU 이벤트 구현 계획

목표는 기존 CUDA 프로그램이 사용하는 이벤트 생성·기록·대기·삭제·경과 시간 측정을 Intel에서 지원하는 것이다. CPU 시간을 GPU 시간처럼 반환하지 않는다. Intel에서 검증한 뒤 AMD로 확장한다.

## 1. GPU 시계 기반 — 구현 및 검증

- `Backend::timestamp`는 선택적 `zeDeviceGetProperties`와 `zeDeviceGetGlobalTimestamps`를 사용한다.
- `DEVICE_PROPERTIES_1_2` (`0x20006`)로 주파수의 단위를 cycles/second로 고정한다. 기존 구조 유형의 nanoseconds 단위와 혼용하지 않는다.
- 양수 주파수와 1~64의 `timestampValidBits`를 검사한다. kernel timestamp 비트 수를 사용하지 않는다.
- 시계 API가 없어도 기존 초기화·복사·실행 경로는 유지한다. 미지원 기능은 성공으로 위장하지 않는다.
- device lost/reset 오류는 기존 context poison 및 loader pin 정책을 따른다.
- `scripts/run_gpu_clock.py`는 선택한 Intel 장치에서 실제 시계 증가와 1,024개 값의 왕복 복사 8회를 확인한다. 소스·실행 파일 해시가 연결된 원시 증거는 무시되는 `.cache/`에만 보관한다.
- 이 단계는 시계 읽기 검증이다. CUDA 이벤트 지원, 시간 정확도, 성능 우위의 증거는 아니다.

## 2. Driver 이벤트 5개 — 구현 및 통합 검증 완료

대상: `cuEventCreate`, `cuEventRecord`, `cuEventSynchronize`, `cuEventDestroy_v2`, `cuEventElapsedTime`.

- 최초 범위는 flags=0 및 현재 context 소유권이다. context당 live event 128개, 재사용하지 않는 핸들을 사용한다.
- 현재 native 명령이 동기 실행되는 조건에서 record가 GPU counter를 읽는다. 이 query 자체는 queue를 비우지 않으므로 호출 계층의 순서 보장이 필요하다.
- 각 기록은 GPU ticks, frequency, valid bits, 기록 순서, query 전후의 단조 시계 경계를 저장한다.
- 경과 시간은 마스킹한 GPU tick 차이 / frequency로만 계산한다.
- 단조 시계는 여러 차례 wrap 가능성을 거부하는 상한 검사에만 사용한다. 출력 시간을 대체하지 않는다.
- 역순 기록은 1, 미기록 핸들은 400, 호환되지 않는 시계나 모호한 wrap 구간은 801로 거부한다. 오류 시 출력은 보존한다.
- 같은 기록의 자기 비교, 한 번 wrap, 여러 번 wrap, 64비트 경계, 주파수 불일치, context 불일치를 먼저 테스트한다.
- 공식 CUDA typedef와 버전 경계(일반 함수 2000, destroy_v2 4000)를 검증한다.

## 3. Runtime 이벤트 5개 및 큐 연결 — 구현 및 검증

대상: `cudaEventCreate`, `cudaEventRecord`, `cudaEventSynchronize`, `cudaEventDestroy`, `cudaEventElapsedTime`.

- live 128개 / lifetime 4096개의 재사용하지 않는 opaque token과 context 소유권을 사용한다.
- record마다 독립적인 완료 세대를 만든다. synchronize는 호출 시점의 세대를 잡고, 다시 기록해도 이전 대기가 늘어나지 않도록 한다.
- scheduler의 enqueue는 context gate 안에서 build → send → 실패하지 않는 commit 순서로 진행한다. 실패한 enqueue는 기존 세대를 보존한다.
- 정상 완료, native 오류, sticky error로 생략, panic, job 폐기 모두 수락된 세대에 완료를 통지한다.
- cleanup job은 앞선 오류가 있어도 실행한다. 논리적 삭제와 native 정리는 분리한다. Drop에서 native 정리를 하지 않는다.
- 잠금 순서는 stream → context → event이다. 두 이벤트는 token 순서대로 잠그고 같은 이벤트는 한 번만 잠근다. 대기 중 잠금은 보유하지 않는다.
- elapsed는 전체 큐를 기다리지 않고 readiness를 검사한다. pending은 600, 미기록은 400으로 구분한다.

## 4. 통합 완료 조건

- 재기록/이전 세대 대기, 완료가 commit보다 빠른 경우, enqueue 실패, 동시 역순 비교, pending 삭제와 기존 waiter를 검증한다.
- 공식 헤더 ABI와 실제 nvcc 프로그램에서 이벤트·비동기 복사·커널 실행을 연결한다.
- 기존 누락 제어·수치 검증, 원본 vectorAdd, 전체 회귀, 독립 검토, 개인정보 검사를 통과한다.
- 각 계층의 독립 증거를 구분한다. Driver 이벤트 검증 후 Driver 41→46을 기록하고, Runtime 연결과 검증까지 끝난 뒤 Runtime 33→38 및 matrixMul 미해결 import 7→2를 기록한다. Driver 단계만으로 Runtime 미지원 함수 수를 줄이지 않는다.
- shared memory, barrier, FMA, 장치 선택 문제는 별도 과제다. 이벤트만으로 matrixMul 실행 완료를 주장하지 않는다.

## 근거

- 로컬에 고정한 Level Zero `ze_api.h`와 CUDA 12 `cudaTypedefs.h` / `cuda_runtime_api.h`.
- [Level Zero Device API](https://oneapi-src.github.io/level-zero-spec/level-zero/1.18.31/core/api/apis/device.html).
- [CUDA 12 Runtime Events](https://docs.nvidia.com/cuda/archive/12.0.1/cuda-runtime-api/group__CUDART__EVENT.html).


## 실행 기록

- Driver 이벤트 기록부, 공개 export 5개, lookup floor, 공식 헤더 비교, native consumer 및 누락 제어를 구현했다.
- 시간 계산/flags/128개 한도/기록 실패 보존 7개 unit 테스트와 resolver 확장 테스트를 RED→GREEN으로 확인했다.
- 독립 검토에서 누락 제어가 임의의 실패를 허용하던 증거 약점을 발견했다. 실패 단계·오류값·출력값을 정확히 검사하도록 고치고 검증기 테스트 2개를 추가했다.
- Ruling: Driver와 Runtime의 완료 증거를 분리한다. 두 계층의 구현 범위와 오류·수명 규칙이 다르므로 Driver 단계를 실제로 검증해도 Runtime 미지원 7개는 그대로 유지한다. 이를 구분하지 않으면 앱 실행 가능성을 과장하게 된다.
- 다음 구현은 section 3의 Runtime 완료 세대와 scheduler transaction이다. 새 Driver 이벤트를 직접 호출해서 pending Runtime 복사를 동기화했다고 간주하면 안 된다.

- 최종 고정 소스 capture `e08ae4204443473bad63b0e4f881e8ab`에서 Driver 이벤트 positive 2회, record 생략/0ms 강제 제어 및 기존 native 회귀가 통과했다. Driver 46 / Runtime 33 / 남은 Runtime import 7개다. 상세 결과: [Driver event results](../../DRIVER-EVENT-RESULTS.md).


### Runtime 실행 기록

Runtime 이벤트5/optional Driver5 묶음과 generation snapshot, transactional enqueue,
cleanup jobs 및 pending readiness 조회를 구현했다. 독립 검토가 발견한 완료 게시
순서 경쟁은 RED→GREEN으로 수정했다. Runtime126/Python193 테스트 및 실제 nvcc
수치·생략 제어가 통과했다. 현재 Driver46/Runtime38이며 남은 Runtime import는
profiler2개다. 공유 메모리/barrier/FMA와 장치 선택은 별도 과제다.
상세 결과: [Runtime event results](../../RUNTIME-EVENT-RESULTS.md).
