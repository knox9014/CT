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
