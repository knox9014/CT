# Driver GPU 이벤트 5개 구현 결과 — 2026-10-26

후속 [Runtime 이벤트 결과](RUNTIME-EVENT-RESULTS.md)에서 Runtime 38개와 큐 연결을 검증했다. 아래는 Driver 단계 당시의 기록이다.

실제 Intel GPU에서 Driver 이벤트 생성·기록·대기·삭제·경과 시간 측정을 구현하고 검증했다. 현재 검증 프로파일은 **Driver 46개 / Runtime 33개**다. Runtime 이벤트 5개는 아직 비동기 큐와 연결하지 않았으므로 matrixMul의 미지원 Runtime import는 **7개 그대로**다.

## 구현 범위

- `cuEventCreate`: flags0, 현재 context당 live event 128개. metadata를 먼저 예약하고 실제 GPU 시계를 사용할 수 있을 때만 핸들을 발행한다. 실패 시 출력은 보존한다.
- `cuEventRecord`: null/default stream만 지원한다. 현재 native Driver 명령이 동기 실행되는 조건에서 GPU counter를 기록한다. 기록 실패는 이전 기록을 보존한다.
- `cuEventSynchronize`: 해당 context의 유효 이벤트를 검사한다. record가 이미 동기 완료되므로 별도 native queue 대기는 없다. 미기록 이벤트도 완료 상태다.
- `cuEventDestroy_v2`: CPU metadata를 제거한다. 핸들은 재사용하지 않으며 context가 종료되면 이벤트도 폐기된다.
- `cuEventElapsedTime`: 주파수와 유효 비트 수를 검사하고 GPU tick 차이로 ms를 계산한다. CPU 단조 시계는 반 주기 이상 또는 여러 번 wrap 가능성이 있는 구간을 거부하는 상한 검사에만 쓴다.

잘못된/다른 context/삭제된 핸들과 미기록 elapsed는 400이다. 역순 기록은 1, 다른 시계·모호한 wrap은 801이다. 같은 기록은 0ms다. 오류 시 시간 출력은 보존된다. flags1/2/4 및 non-null stream은 현재 범위 밖이다. 이는 제한된 CT 정책이며 완전한 NVIDIA 동작 일치 주장은 아니다.

전역 Driver mutex가 record·재기록·삭제·시간 계산을 직렬화한다. GPU counter 기록은 비동기 queue에 marker를 삽입하는 구현이 아니다. **직접 Driver 이벤트를 호출해서 pending Runtime 복사가 완료됐다고 간주하면 안 된다.** 그 연결은 다음 단계다.

## 검증

- 새 이벤트 unit 테스트 7개를 실패부터 확인한 뒤 통과시켰다. flags, 128개 한도, 기록 실패 보존, 잘못된 핸들의 sampling 방지, 단일 wrap 마스킹, 64비트 경계, 역순·주파수 불일치·다중 wrap 거부를 검사한다. Driver unit 테스트 총 36개 통과.
- resolver의 새 이벤트 5개 버전 경계를 먼저 실패시킨 뒤 연결해 통과했다. 원본 CUDA typedef 기준으로 일반 이벤트 함수 2000, destroy_v2 4000 및 legacy/default-stream record 서명을 사용한다.
- 공식 CUDA 헤더만 사용하는 probe와 CT 헤더 probe의 **46개 서명 출력이 일치**했다.
- 공식 CUDA 타입을 사용하는 native consumer를 Intel B390에서 두 개의 새 입력으로 실행했다. 이벤트 사이에서 1,024개 값의 왕복 복사 8회를 검사했고 양의 GPU counter 경과 시간이 관찰됐다.
- 공개 API에서 미기록 대기, 오류 출력 보존, 자기 비교, 역순, 재기록, 다른 context, 삭제된 context/이벤트, 128개 한도, 삭제 후 새 핸들 발행을 검사했다.
- 기록 생략 provider는 `EVENT_TIMING_REJECT code=400 milliseconds=987.5`, 시간 0 강제 provider는 `EVENT_TIMING_REJECT code=0 milliseconds=0` 지점에서 각각 종료 코드 42로 검출됐다. 다른 초기화·export 실패로 이 제어 검사를 통과할 수 없도록 정확한 marker를 검사한다.
- 기존 비동기 복사·커널 수치 검증과 launch/copy 누락 제어, host allocation·owned stream·default stream·device attribute 검증도 같은 새 DLL들로 통과했다.
- workspace 테스트·clippy·format 통과. 기존 외부 자료 의존 테스트 3개와 명시 실행용 hardware clock probe 1개는 일반 workspace 테스트에서 제외된다.
- 별도 Runtime unit 테스트 112개 통과. Runtime format 및 정적 profile/coverage 검사 통과.
- Python 테스트 **192개 통과**. 첫 회귀에서는 새 profile feature group에 대응하는 coverage ID 누락을 발견해 수정했다.
- 독립 검토에서 실행 코드의 blocker는 발견되지 않았다. 누락 제어가 임의의 실패를 허용하던 증거 약점은 정확한 실패 marker와 검증기 테스트 2개로 수정한 뒤 재검토했다.

첫 탐색 capture는 검증기를 강화하는 동안 소스가 바뀌어 fingerprint 검사에서 거부됐다. 아래 증거는 변경을 마친 소스를 고정해 새로 빌드하고 실행한 결과다.

## 증거와 재현

```powershell
cargo test -p ct-cuda
python scripts/run_driver_events.py
```

두 번째 명령은 기존 native 회귀와 공식 헤더 비교를 포함한다. Windows x64, 인증된 로컬 CUDA producer/compiler 자료 및 Intel B390 검증 환경이 필요하다. vendor 자료·실행 파일·로그는 `.cache/`에만 둔다.

- Source fingerprint: `918cd00ace32743da4aa9b5acfecaf4e3b94ecfe9b6d33f643504da2a260cab0`
- 새 event manifest: `.cache/runtime-attribute-runs/e08ae4204443473bad63b0e4f881e8ab/driver-events-manifest.json`
- Manifest SHA-256: `93ab64e80b941651597cc6fd8b15a65cffbc1e94a16ff0ee9608ac539cce39a5`
- Latest pointer: `.cache/driver-events-latest.json`
- 같은 폴더의 attribute, default stream, owned stream, host 및 queued copy manifest 모두 현재 source fingerprint와 일치함을 확인했다.

검증 시간은 global GPU 시계의 두 sample 사이 구간이며 CPU dispatch·idle 간격을 포함할 수 있다. 커널만의 실행 시간, 성능 우위, 외부 시계 교정, 다른 Intel GPU나 NVIDIA/AMD 호환성을 증명하지 않는다. 원본 matrixMul 실행 완료도 아직 아니다.

다음 구현은 [Runtime 이벤트 완료 세대와 큐 연결](superpowers/plans/2026-10-26-gpu-events.md)이다. 이후에 Runtime 이벤트 5개와 profiler 제어 2개를 마무리하고 shared memory·barrier·FMA·장치 선택 문제를 해결한다.

원시 로그와 바이너리는 무시되는 로컬 cache에 유지했다. 공개 대상 개인정보·비밀 패턴 검사와 기존 사용자 소유 파일 11개의 hash 보존을 확인했다. staging·commit·upload는 하지 않았다. 패턴 검사는 완전한 보안 감사와 구분한다.
