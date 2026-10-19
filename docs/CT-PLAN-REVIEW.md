# CT 계획 검토 결과

검토일: 2026-10-19. 기준 코드: M3e `4b0c64f`.
이 문서는 구현 전 계획 검토 기록이다. 후속 [M3f 구현·시험 결과](M3f-RESULTS.md)에서
P00/P01의 실행 증거와 독립 코드 리뷰를 별도로 확인할 수 있다.
검토 방식: 현재 코드/기존 결과/공식 명세와 대조한 작성자의 자체 검토.
독립 리뷰어나 새 GPU 실행에 의한 구현 검증은 아니다. 이번 요청의 산출물은 계획 문서다.

## 검토 대상

- [G0~G14 요구사항](CT-COMPLETION-GOALS.md)
- [P00~P25 전체 작업·의존성](CT-EXECUTION-ROADMAP.md)
- [M3f 명세](superpowers/specs/2026-10-19-m3f-selection-design.md)
- [P00/P01 상세 계획](superpowers/plans/2026-10-19-m3f-selection.md)
- 실제 fatbin decoder, parser의 단일 Kernel 구조, Compiled, CUDA module/native 소유권,
  전역 mutex, 동기 backend 및 기존 native 시험 harness

## 발견한 문제와 반영한 수정

| ID | 판단 | 수정 |
| --- | --- | --- |
| R01 | 높음: 기능 목록만으로는 작업 순서·완료/차단 조건을 판정할 수 없음 | 26개 작업의 선행 조건/산출물/증거와15개 G 영역의 담당 매핑 추가 |
| R02 | 높음: warp 전체가 Runtime보다 먼저라는 순서는 불필요한 직렬 의존 | primary context·기본 메모리·등록 뒤 동기 Runtime(P09), 비동기는 P07/P08 뒤 연결 |
| R03 | 높음: 복수 PTX를 받아 모두 연결하거나 첫 이미지만 고르면 잘못된 코드 선택 가능 | 대체 이미지와 링킹 구분, 알려진 두 프로파일·전체 ABI·명시적 순위·native fallback 금지 |
| R04 | 높음: 현재 decoder는 candidate metadata를 반환하지 않고 parser도 본문 profile을 IR에서 버림 | 두 독립 Profile 타입과 필드별 변환, 본문/metadata 일치218 시험을 상세 계획에 추가 |
| R05 | 높음: 개별 압축 해제 cap만 유지하면 여러 후보의 누적 메모리가 증가 | 후보8개/누적1MiB, 각 해제 전 선언 크기 누적 검사; process 전체 메모리 상한과 구분 |
| R06 | 높음: 비동기 API보다 queue 완료·자원 수명 계약이 뒤면 free/unload 경쟁 발생 | P07을 stream API의 선행 조건으로 분리; in-flight 보존·event generation·잠금/재진입 명시 |
| R07 | 높음: 정적 cudart는 Runtime DLL 교체만으로 해결되지 않음; 여러 DLL에 상태가 복제될 위험 | 동적 shim/원래 정적 Runtime의 Driver 요구를 별도 경로로 검증; 단일 CT Driver 상태 계약 |
| R08 | 중간: AMD를 모든 Intel 기능 뒤로 미루면 backend 설계 오류를 늦게 발견 | P14는 P00 뒤 시작 가능; P15도 기존 제한 IR로 시작하고 기능별 공통 프로파일 확장 |
| R09 | 중간: Invalid와 Unsupported가 섞인 입력에서 모두 전역 우선이라고 하면 모순 | extraction→translation 단계별 first-error 계약으로 수정, valid 입력의 순서 독립과 분리 |
| R10 | 중간: 새 계획이 기준 DLL을 덮어쓴 뒤에 이전 실패를 재현하려 할 수 있음 | 첫 Rust 변경 전 baseline DLL/해시 보존을 Task1에 추가 |
| R11 | 중간: 정적 시험 참조가 실제 GPU pass로 보일 수 있음 | manifest 유효성과 실행 결과 분리, not_run/skip 구분과 선언 제한 시험 추가 |
| R12 | 중간: 기능 계획에 내구성 요구가 있으나 첫 상세 계획에는 반복 시험이 빠짐 | kernel100회/module cycle1000회를 별도 집계하도록 추가 |

## 상세 계획의 인터페이스 검토

| 생산자→소비자 | 확인 |
| --- | --- |
| Task2 PtxProfile→Task4 SourceCandidate | ct-fatbin이 ct-ptx에 의존하지 않고 CUDA 계층에서 major/minor/target 필드 변환 |
| Task3 Kernel.profile→Compiled.profile→Task4 선택 | 기존 parse/translate 서명 유지, 검증한 profile이 소실되지 않음 |
| Task4 compile_candidates→기존 module/native | Compiled 하나만 전달; 선택 오류 때 native allocation 없음; export 추가 없음 |
| Task1 baseline→Task5 RED | Rust 변경 전 고정한 DLL을 명시적 경로/해시로 사용 |
| Task1 registry→Task5 결과 갱신 | 정적 test reference와 실제 실행 집계를 별도 기록 |

단일 entry의 ParamKind 비교는 현재 ABI에만 충분하다. P02/P03에서 구조체·정렬·주소 공간을
확장할 때 ABI signature에 offset/size/alignment/address-space가 포함돼야 함을 전체 로드맵에 적었다.
같은 이름/ABI가 계산 동등성의 증거라는 주장은 제거했다. 선택은 명시한 대체 이미지 계약이다.

## 확인과 한계

- 문서 정적 검사 결과: repo 내부 링크41개 정상, 작업 ID26개 중복 없음, G 영역15개 모두 매핑,
  첫 상세 작업5개 존재. 예정 GPU48사례의403,600출력/3,072guard 산술 일치.
- P00~P25의 명시적 필수 의존성에 순환이 없음을 검사했다. 조건부 의존성과 하드웨어 문턱은
  별도로 읽고 검토한다. 앱 실행은 해당 앱의 기능 목록이 고정돼야 상세화할 수 있다.
- G0~G14 전체에 담당 작업이 있으며 고급 기능을 이름 없이 제외하지 않았다.
- git diff whitespace 검사와 문서 bytes의 저장소 공개 검사 규칙도 통과했다.
- 상세 계획은 첫 P00/P01만 실행 가능한 수준이다. P02 이후는 결과를 반영한 별도 명세와
  상세 계획이 필요하다. 전체26개 묶음이 지금 그대로 코딩 가능한 상태라는 주장은 하지 않는다.
- NVIDIA 원본 비교·공존 및 AMD 실장비는 여전히 외부 검증 조건이다. CPU/Arc 결과로 대신하지 않는다.
- SASS, 고급 warp/메모리 모델, 최신 GPU 기능은 연구 위험이 크다. feasibility 실패 시에도
  범용 목표를 조용히 축소하지 않고 지원 범위/대안/차단 원인을 기록한다.
- 계획 문서는 공개 가능한 repo 상대 경로만 사용한다. vendor/binary/raw log는 포함하지 않는다.

## 판단

전체 목표의 **작업 분해·의존성·완료 증거**와 첫 작업의 **파일·인터페이스·RED/GREEN 절차**를
검토하고 위 결함을 수정했다. 현재 코드와 대조했을 때 첫 P00/P01의 설계상 미해결 차단점은
발견하지 못했다. 이는 계획의 자체 검토 결과이며 구현 성공·성능·완전한 CUDA 호환 보장이 아니다.

다음 실행 단위는 P00 기능 추적표 다음 P01(M3f) 복수 PTX 선택이다. 이번 요청 범위에서는
제품 코드를 변경하거나 vendor 의존성을 설치하거나 새 PR을 생성하지 않는다.
