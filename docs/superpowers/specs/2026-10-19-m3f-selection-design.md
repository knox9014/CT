# M3f 명세: 제한된 복수 PTX 선택과 기능 추적

기준: M3e `4b0c64f`. 상태: 이 제한 프로파일을 M3f로 구현하고 Arc에서 검증했다. 원본 NVIDIA 대조와
AMD/일반 CUDA 호환은 이 명세의 완료에 포함되지 않는다. 결과는 docs/M3f-RESULTS.md 참조.
요구사항: [전체 목표](../../CT-COMPLETION-GOALS.md) G0/G1/G2/G13.
범위: P00/P01만 상세 설계한다. 다른 작업은 [전체 로드맵](../../CT-EXECUTION-ROADMAP.md)을 따른다.

## 의도와 대안

기존 CUDA 앱이 전달하는 fatbin의 여러 대체 PTX 이미지 중 지원 가능한 한 이미지를
순서에 의존하지 않고 선택한다. 현재 하나만 허용하는 decoder와 단일 entry 번역기는 유지하며
후자의 여러 entry 지원은 P02에 둔다. 커널별 치환, 서로 다른 모듈의 연결은 하지 않는다.

대안은 (a) 첫 PTX 사용, (b) 무조건 최고 버전 사용, (c) 검증한 프로파일의 명시적 우선순위다.
추천은(c)다. 첫 항목/숫자만 보는 방식은 이미지 순서·미지원 의미를 숨길 수 있다.
첫 구현은 모두 이해할 수 있는 후보만 받는 보수적 범위이며, 다른 미래 프로파일과 섞인
일반 fatbin을 처리한다고 주장하지 않는다. 알 수 없는 프로파일의 안전한 skip은 후속 명세다.

## 기능 추적 계약(P00)

`docs/compatibility/profile-v1.json`에 schema_version=1, 기준 commit, OS/host/GPU,
export 목록(symbol, signature_id, lookup_ranges, behavior, test_ids), 기능 목록
(id, state, limits, test_ids)을 둔다. state는 experimental/unsupported이며 최초 프로파일은
full conformance를 선언하지 않는다. 근거 실행은 별도 ignored 결과에 pass/fail/skip/not_run으로
보관하고, JSON 지원 선언만으로 시험 pass를 생성하지 않는다.

`include/ct_cuda.h`의26 export와 일치해야 한다. cuDriverGetVersion처럼 export는 있으나
NOT_SUPPORTED를 반환하는 계약도 명시한다. PTX 버전/명령 변형의 범위는 기존 PTX 표를
전사하고, 다음 기능마다 갱신한다. 후속 전체 CUDA inventory는 새 프로파일로 확장한다.

## 후보·프로파일 계약(P01)

- raw fatbin16MiB, 전체 record256, PTX 후보8개까지. 후보9개는 Unsupported.
- 후보별 현재 PTX256KiB, 해제 전 declared/padded byte 총합1,048,576까지.
  각 후보를 해제하기 전에 누적 크기에 더해 검사하며 초과 시 Unsupported. overflow는 Invalid.
  이 cap은 후보의 누적 해제 크기이고 입력 버퍼·문자열·SPIR-V를 포함한 프로세스 전체 메모리 상한은 아니다.
- `Profile`은 major/minor/target을 가진다. 허용 조합은7.0/sm_50과8.0/sm_52만이다.
- record metadata와 PTX 본문의 프로파일이 같아야 한다. 불일치는 Invalid.
- 성공하려면 모든 후보가 기존 metadata/options/padding/ASCII 규칙과 PTX 구문·타입 검사를 통과해야 한다.
  추출 단계는 record 순서대로 첫 오류에서 중단하고, 추출 성공 뒤의 번역/선택 단계도 첫 오류에서 중단한다.
  각각 발견한 Invalid/Unsupported를 반환하며, 여러 단계에 오류가 섞인 입력의 종류별 우선순위는 보장하지 않는다.
- 후보 간 entry 이름과 순서 있는 ParamKind 목록은 같아야 한다. 인자 이름은 비교하지 않는다.
  entry/ABI가 다르면 Unsupported; 동일 프로파일 중복도 내용과 무관하게 Unsupported.
- 우선순위는 명시적으로8.0/sm_52 > 7.0/sm_50. 미래 버전은 자동 순위에 들어가지 않는다.
  이는 CT의 제한 프로파일 선택 정책이며 NVIDIA compute capability를 광고하지 않는다.
- 같은 이름/ABI가 같은 계산임을 증명하지는 않는다. fatbin 제공자가 대체 이미지를 담는
  입력 계약 아래 선택할 뿐, CT가 후보의 의미 동등성을 판정하거나 모듈을 합치지는 않는다.
- 선택된 후보만 native 모듈로 만든다. native compile/load 실패 시 낮은 후보로 재시도하지 않는다.
- raw PTX는 단일 후보(profile=None) 경로를 유지한다. 후보 배열에 raw와 binary를 섞지 않는다.
- 기존 `extract_ptx`는 한 후보만 허용하는 wrapper로 유지한다. 새 C export는 추가하지 않는다.

## 상태와 수명

실패 시 출력 module handle은 null, context는 parser/selection 오류 뒤에도 사용 가능해야 한다.
부분 native 모듈을 만들지 않는다. native 실패의 poison/자원 보존은 기존 계약을 유지한다.
입력은 신뢰한 C 포인터와 충분히 읽을 수 있는 전체 버퍼라는 기존 전제다.
이 작업은 arbitrary host pointer 검증 또는 untrusted GPU 코드 격리를 제공하지 않는다.

## 완료 기준

- 압축/비압축 각각 순서를 뒤집어 같은8.0 후보를 선택한다.
- 하위 후보 add, 상위 후보 sub의 다른 의미를 갖는 합성 입력에서 CPU sub 정답을 확인한다.
  두 후보의 entry/인자 이름을 바꾼 버전에서도 일반 선택 규칙은 유지된다.
- 동일 프로파일 중복, entry/ABI 불일치, metadata/본문 불일치, 미지원 후보,
  해제 크기/후보 수 초과는 명시적으로 실패하고 context 복구 검사 통과.
- 실제 nvFatbin producer로 만든 다중 후보와 기존 공식 호스트/CLI를 검증한다.
- 현재 M1~M3e 회귀, rustfmt/Clippy, ABI/공개 검사 통과. SPIR-V 공식 validator가 없으면
  그 검사는 skip으로 기록하고 native compile 성공과 구분한다.

제외: unknown profile skip, 여러 entry/링킹, cudart 등록, AMD 실행, NVIDIA 대조가 없는
상태의 CUDA 전반 conformance. 상세 명령과 파일 경계는 연결된 구현 계획에 고정한다.
