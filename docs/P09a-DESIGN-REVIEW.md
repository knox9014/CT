# P09a1 설계 독립 검토 기록

2026-10-21. 대상: [서면 설계](superpowers/specs/2026-10-21-runtime-memory-design.md),
[의존성 감사](P09a-DEPENDENCY-AUDIT.md).
구현·GPU 실행·Runtime ABI 통과 보고서가 아니다.

두 읽기 전용 검토를 수행했다. 첫 검토는 Runtime/Driver 공유, 초기화·참조·오류와
실패 경로를 확인했다. 두 번째는 producer 유무, header/package provenance와
검증 주장의 경계를 확인했다.

| 지적 | 반영한 규칙 | 검토 결과 |
| --- | --- | --- |
| 호출자 DLL의 loader lock 아래 Runtime 호출 제한 누락 | stateful 호출은 loader-lock 밖에서만 지원; 자동 감지·회피 미약속 | 집중 재검토에서 해결 확인 |
| retain rollback release 실패 뒤 재시도 정책 누락 | 장치별 primary 획득 캐시 sticky Failed999; 재retain/release·재사용 금지 | 집중 재검토에서 해결 확인 |
| Count/Get 경로의 module 수명 불명확 | 소유 module reference 유지; 첫 함수 표 게시/사용 전 Runtime/Driver pin | 집중 재검토에서 명확화 확인 |
| active=true만으로 Runtime retain 누수를 놓칠 가능성 | CPU 호출 횟수 + 별도 native child 종료 직전 참조 probe | 집중 재검토에서 정책 대응 확인 |
| Runtime 패키지 하나로 모든 헤더 출처를 설명할 위험 | Runtime3개/compiler 보조2개로 분리; 전체 closure는 후속 pin 필요 | 다른 검토자가 원본 wheel/선택5개 파일 hash를 재계산해 일치 확인 |

최종 집중 재검토에서는 추가 차단 사항이 보고되지 않았다. 이는 해당 서면 설계의
읽기 전용 검토 결과이며, 구현에 결함이 없다는 보증이나 실제14개 함수 동작의 성공이 아니다.
코드·dependency·tool lock·실행 profile은 이번 단계에서 변경하지 않았다.

확정 전 남은 절차는 사용자의 서면 설계 검토와 그 후 상세 구현 계획이다.
Runtime 메모리 fixture와 실제 nvcc host 등록/launch 증거를 구별하는 조건을 유지한다.

## 2026-10-22 상세 계획 검토

사용자의 후속 `이어해봐`에 따라 [상세 실행 계획](superpowers/plans/2026-10-22-runtime-memory.md)을 작성했다.
여섯 Task의 파일·공통 인터페이스·RED/GREEN·필수 gate를 구현자가 자체 검토했고,
두 읽기 전용 검토자가 수명/오류 경로와 producer/로더/evidence 경계를 각각 대조했다.
계획과 설계 사이의 차단 모순이나 잘못된 실행 증거 주장은 보고되지 않았다.

비차단 제안 두 개도 계획에 반영했다: no-op control은 나머지 실제 Driver/Arc 경로를
유지하는 forwarding wrapper로 만들며, retain probe의 fresh child 초기 상태와 정확한
retain/release/GetState 순서를 고정했다. 원래32개 + Runtime6개 = required38개를 확인했다.

계획 작성 중 초기화 오류 표현을 명확히 했다. Driver가999를 반환하면 Runtime도999를
유지하며, 출처를 구별할 수 없는 native 초기화 실패를 일괄3으로 바꾸지 않는다.
Driver init의 첫 결과도 고정해 자동 재시도를 막는다. 원래 오류 변환 표·실패 고정 설계의
구체화이며 새 API 범위를 추가한 것이 아니다.

현재 제품 코드/Runtime export/새 native 실행 결과는0이며, 사용자 상세 계획 검토가 남아 있다.
첫 설계 PR의 기존 CPU/validator CI는 `f262a52`에서 통과했다. 계획 문서 변경을 새 Runtime
검증 성공으로 표시하지 않는다.
