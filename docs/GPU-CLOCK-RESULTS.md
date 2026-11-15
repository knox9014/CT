# GPU 시계 기반 구현 결과 — 2026-10-26

후속 단계에서 Driver 이벤트 5개까지 구현·검증했다. 아래는 시계 기반 단계의 기록이며 최신 상태는 [Driver 이벤트 결과](DRIVER-EVENT-RESULTS.md)를 따른다.

CUDA 이벤트 구현의 첫 단계로 Intel backend에 실제 GPU counter 읽기를 추가했다. 아직 CUDA 이벤트 5개를 공개 API로 연결하지 않았다. 현재 검증 프로파일은 Driver 41개 / Runtime 33개이며, matrixMul 실행 완료를 의미하지 않는다.

## 변경

`Backend::timestamp`는 초기화와 독립적인 선택 기능이다. 기존 장치 검색 경로는 유지한다. 반환 값은 GPU ticks, cycles/second 주파수, global counter의 유효 비트 수다. 시계 조회 자체는 queue 동기화를 하지 않으므로 호출 계층에서 앞선 작업을 정렬해야 한다.

Level Zero `DEVICE_PROPERTIES_1_2`를 명시해 단위 혼동을 방지했다. 주파수 0 또는 비트 수 1~64 밖의 metadata는 거부한다. 시계 API가 없으면 unsupported를 반환한다. device lost/reset은 기존 context poison 및 loader pin 정책에 연결했다. CPU timestamp는 결과로 노출하지 않는다.

[공식 Device API](https://oneapi-src.github.io/level-zero-spec/level-zero/1.18.31/core/api/apis/device.html) 및 고정된 `ze_api.h`와 서명·단위를 비교했다.

## 확인한 범위

- Intel backend 테스트 38개 통과. 새 시계 테스트 7개가 metadata, optional symbol 누락, 잘못된 device, property/query 오류, fatal 상태, recoverable 오류 후 재시도를 검사한다.
- 명시 실행하는 hardware probe 통과. `B390` 이름 필터로 선택한 장치에서 1,024개 값의 왕복 복사를 8회 검사하고 실제 counter 증가를 확인했다.
- 소스·실행 파일 hash를 연결한 새 capture에서 주파수 19,200,000 cycles/s, 유효 비트 수 64가 관찰됐다. 이는 보고된 주파수이며 외부 기준으로 정확도를 교정한 결과는 아니다.
- workspace 테스트 및 clippy 통과. 일반 실행에서는 기존 외부 자료 의존 테스트 3개와 새 hardware probe 1개가 제외된다. 새 hardware probe는 별도로 명시 실행해 통과했다.
- 별도 Runtime unit 테스트 112개 및 clippy 통과.
- 새 소스로 다시 빌드한 비동기 복사 통합 검사 통과. 수치 검증 2회, 복사/커널을 생략하면 각각 종료 코드 42로 실패하는 제어 검사, Driver 누락과 잘못된 복사의 정리 검사가 통과했다. 이 실행은 기존 host allocation·owned stream·default stream·device attribute 검사도 함께 통과했다.
- Python 회귀 테스트 190개 통과. workspace/Runtime format 검사 통과.
- 독립 하위 에이전트가 ABI·단위·optional 기능·poison 처리·probe를 읽기 전용 검토했고 수정 필요 사항을 발견하지 않았다.

## 재현

프로젝트 루트에서 다음 명령을 실행한다. Windows x64, System32 Level Zero, 지원 Intel GPU가 필요하다. 다른 장치에서는 필터를 명시적으로 바꾼다. 일치하는 장치가 없으면 다른 GPU로 조용히 대체하지 않는다.

```powershell
cargo test -p ct-backend-intel
python scripts/run_gpu_clock.py --device-name-contains B390
```

첫 명령은 hardware probe를 제외한다. 두 번째 명령이 새로운 실행 파일을 빌드하고 실제 장치 검증을 실행한다. 소스·실행 파일이 도중 바뀌면 capture를 거부한다.

비동기 복사 및 앞선 4개 단계의 새 manifest는 `.cache/runtime-attribute-runs/dd595dc21f7f4c94b6e8e107a4fd9da5/`에 있다. 이 manifest들과 GPU clock capture의 소스 fingerprint가 현재 소스와 일치함을 확인했다.

원시 로그와 manifest는 `.cache/gpu-clock-runs/`에만 저장하며 `.cache/gpu-clock-latest.json`이 마지막 capture를 가리킨다. 새 capture는 `c03bab8bbacc49b285751ac9ed9177dc`이며 release claim은 false다. GPU clock 출력은 벤치마크 점수나 커널 실행 시간으로 해석하지 않는다.

## 한계와 다음 단계

이 검사는 전송이 정상인 구간에서 GPU 시계가 증가함을 확인한다. 경과 시간 변환의 정확도, counter wrap 처리, CUDA event 수명·재기록·대기 semantics는 아직 구현·검증하지 않았다. 다음 단계는 [GPU 이벤트 구현 계획](superpowers/plans/2026-10-26-gpu-events.md)의 Driver 이벤트 5개와 시간 계산 경계 테스트다. 그 뒤 Runtime의 완료 세대와 비동기 큐를 연결한다.

공개 대상 검사에서 기존 프로젝트 파일 118개를 검사했고 사용자 소유 파일 11개의 baseline hash가 유지됐다. 해당 검사는 개인정보·비밀 패턴 검사이며 완전한 보안 감사는 아니다. staging·commit·upload는 하지 않았다.
