# 범용 CT 계획 독립 재검토 결과

검토일: 2026-10-20. 대상:
[전체 명세](CT-UNIVERSAL-PLAN.md),
[첫 실행 계획](superpowers/plans/2026-10-20-universal-foundation.md).

## 결론

CT 소유 Rust 계층, 일반 CUDA API/ABI·GPU 의미 구현, 여러 소비자/기능 조합 검증,
Arc 우선 실행, AMD/NVIDIA 미검증 분리라는 방향은 목표와 일치한다.
두 독립 하위 검토에서 목표 삭제·앱 전용 축소·하드웨어 지원 과장에 해당하는 High는 보고되지 않았다.
아래 실행 계약·의존성 문제를 확인하고 문서에 수정했다. 계획 검토 결과이며 코드 구현이나
모든 미래 조합의 실현성을 검증한 결과는 아니다.

## 발견 사항과 반영

| ID | 중요도 | 발견한 문제 | 반영한 수정 |
| --- | --- | --- | --- |
| R01 | Medium | 기반6Task 전체가 다음 기능 설계/구현의 일괄 선행처럼 읽힘 | P05/P03/P04/P10 설계를 병행 가능하게 명시. 기능별 baseline·계약·관련 검증만 선행이며 전체corpus/CI/audit 완료를 기다리지 않음. 기반 자체 완료와 release gate는 유지 |
| R02 | Medium | report의 환경/config hash를 대조할 기대 입력이 context에 없음 | expected environment/lock/catalog/config hash와 case_catalog 추가. 환경/설정 schema, canonical hash, case_id와 required case 대조·mismatch RED 지정 |
| R03 | Medium | corpus source hash만 있고 source/recipe 위치·replay cache 계약이 없음 | public 상대 source_ref/recipe_ref와hash, 명시적 CorpusContext, 내용주소 localcache, capture/replay/초기분류/기대고정 순서와 누락·변조 거부 지정 |
| R04 | Medium | P22의 IPC/외부자원 조사까지 AMD와여러GPU 뒤로 묶음 | 단일장치·다중프로세스/import 계약,실제peer/multi-GPU,분산/NCCL을 분리. AMD backend는 그target에만 선행 |
| R05 | Low | external memory와Thrust/CUB/Triton/TensorRT의 세부 연결이 약함 | P22a/P23와개별compiler/JIT/library 카드 대응표를 추가해 장기범위 누락 방지 |
| R06 | 구현 예방 | 두 CUDA header의 명목타입/macro 차이를 ABI 차이로 오인할 수 있음 | C++ 별도 TU의정규화표현비교와독립실제호출을 분리. cuGetProcAddress 4/5인자PFN을버전별명시매핑 |
| R07 | 구현 예방 | unsupported 기대가 IO·invalid·validator 오류로 대신 충족되거나 최초capture를pass로 오인할 여지 | module exporter exit/category,초기관측과고정expected replay분리. unsupported는translation의명시적거부만만족 |

R06은문서가잘못된동시include를명시한기존결함은아니지만, 실제공식header와CT 선언을
대조해예방명세를추가했다. R07은부모검토의상태모델보완이다. 발견사항을향후구현버그로보고하지않는다.

## 실제 대조 근거

- 공식 local CUDA12.0.107의cuda.h는cuGetProcAddress를_v2로macro매핑하며CUresult는enum,
  CUcontext는CUctx_st포인터다. CT header는int와다른opaque struct이름을쓴다.
  따라서명목타입대입의실패와Win64 ABI표현의불일치를구분해야한다.
- cudaTypedefs.h의PFN_cuGetProcAddress_v11030은4인자,PFN_v12000은status를포함한5인자다.
  최신alias 하나로두export를검사해서는안된다.
- 기존fatbin ignored시험은local nvFatbin fixture를요구한다. Arc실행가능성만으로
  workspace include-ignored전체선행이충족되지는않으며 producer/native lane을분리해야한다.
- 현재manifest checker는닫힌v1 schema다. 별도coverage registry를추가한다는계획을유지했다.

## 확인한 범위와 남은 실행 결정

부모가현재저장소와두계획을대조했고,새하위에이전트둘이각각범위·의존성과실행계약을읽기전용검토했다.
수정후로컬문서링크·공개내용검사와P00~P25 추적누락여부를정적으로검사했다.
기능코드·GPU시험·tool설치·병합·기존license/Cargo/README 변경은수행하지않았다.

실행시에는정확한SPIRV-Tools revision/아티팩트,생성corpus의관측분류,새API의버전별계약을
해당Task에서고정해야한다. 이미정값은가짜hash나성공으로채우지않는다.
공식validator가현재출력의문제를발견하면그범위의compiler결함을수정하고관련회귀를검증해야한다.
해당결과가없는현시점에실행계획이나전체CT가무결점이라고보증하지않는다.
