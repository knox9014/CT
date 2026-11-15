# Fused F32 results — 2026-10-27

정확한 `fma.rn.f32`를 구현하고 실제 nvcc 프로그램을 Intel GPU에서 실행했다.
곱셈 결과를 먼저 반올림하지 않고 덧셈까지 수행한 뒤 한 번 반올림한다. 별도의
곱셈·덧셈과 결과가 달라지는 입력을 포함해 차이를 검증했다. Driver46 / Runtime40
함수 프로파일은 그대로다.

## 구현과 수치 계약

F32 전용 IR 연산과 parser의 정확한 opcode/operand 검사를 추가했다. emitter도
F32 타입·세 입력·목적지 타입을 재검사한다. OpenCL.std import를 한 번만 필요할 때
생성해 OpMemoryModel 앞에 배치하고, OpExtInst fma26으로 내린다. 다른 식의 암묵적
결합을 막는 ContractionOff는 유지한다. 분리된 mul/add를 대신 쓰거나 OpenCL mad로
치환하지 않으며 fast-math·denorm-flush 플래그를 추가하지 않는다.

`.rn.f32`만 지원한다. 생략된 rounding, 다른 rounding, ftz/sat, F64/F16/packed,
mad alias는 미지원이다. NaN은 분류만 비교하고 payload/sign은 보장하지 않는다.
다른 GPU의 부동소수점 모드, 모든 IEEE754 입력·예외 플래그, 성능 우위를 검증한
것은 아니다.

Python 기준 계산은 host float 연산 없이 binary32를 부호 있는 정수×2의 지수로
해독한다. 정확한 정수 곱·합을 구한 뒤 nearest-even으로 한 번 반올림한다. 별도
mul/add 기준은 곱에서 먼저 binary32 반올림을 적용한다. literal anchor는 상쇄,
tie-even, subnormal 입력·출력, underflow, 중간 곱 overflow의 상쇄, 무한대와 zero
부호를 확인한다.

## 실제 실행과 대조군

genuine nvcc의 fused/renamed fused/split 세 엔트리를 생성하고 보존 PTX와 원본
fatbin PTX의 모든 토큰을 비교했다. 모듈에는 explicit fma2개와 별도 multiply/add
각1개가 있으며 모든 엔트리의 ContractionOff를 검사했다. 각 fused 엔트리를
64 threads×3 blocks,128 threads×4 blocks에서 실행했다.

서로 다른 seed2개에서 매번 fused704개·split704개 결과 전체를 검사했다.
16개 고정 edge triple과 seed별16개 유한 random triple을 반복 배치한다.
finite/inf/signed-zero는 비트 단위, NaN은 분류로 비교한다. 매 모드에서 실제로
fused와 split이 달라지는 입력도 요구한다. 입력3개의 비트 보존과 입력·출력 버퍼
양 끝 guard를 검사했다.

C++ CPU 기준은 nearest-even을 설정하고 MXCSR의 FTZ/DAZ를 끄며, CUDA 호출 뒤에도
모드를 재확인한다. std::fma와 volatile 중간 곱을 사용하는 분리 계산을 비교한다.
이 CPU 계산은 테스트 기준이며 제품 실행을 CPU로 대체하는 경로가 아니다.
출력은 CT Runtime/Driver를 통해 GPU에서 받은 값이다. 커널 실행 생략·복사 생략
대조군은 각각 exit42로 실패했다.

고정된 실제 `spirv-val --target-env opencl1.2`가 정상 FMA 모듈을 통과시키고
undefined import 변형을 거부했다. 별도 구조 검사에서 fma→mad 치환을 거부했다.
미지원 명령·변형 모듈은 GPU에 제출하지 않았으며 입력/거부 stderr도 hash로 묶었다.

## 회귀와 검토

Rust workspace195개, Runtime129개, Python205개 테스트가 통과했다. 기존 ignored
테스트4개는 실행 증거에서 제외한다. workspace clippy `-D warnings`, workspace 및
Runtime format 검사도 통과했다. 이전 스트림·복사·이벤트·barrier·shared·uniform-loop
native 회귀는 같은 소스에서 다시 캡처했다.

독립 설계 검토와 동결된 구현의 읽기 전용 검토에서 concrete blocker는 발견되지
않았다. 검토 에이전트는 빌드·테스트·GPU 작업을 수행하지 않았다.

## 소스 고정 증거

Source fingerprint: `612bab0f064f1da1788d0b3d7411fc9941acd76e5d163dea7b4f46f22b4cfbfb`.

FMA manifest SHA-256: `e271585c38d77f87db19002cc4a9974ad530b7029dae4dad579c17272a78938a`.

| 검증 | 로컬 기록 |
| --- | --- |
| FMA nvcc/native 및 대조군 | `.cache/runtime-attribute-runs/3a1cd89354ce4eb6bae4f3247530469a/fma-manifest.json` |
| 이전 native 회귀 | 같은 폴더의 `uniform-control-manifest.json` 등 부모 기록 |
| 원본 vectorAdd 새 빌드 | `.cache/upstream-vectoradd-runs/b7d2894477d444c98695d6e0541cae41/manifest.json` |
| 같은 vectorAdd 바이너리 재실행 | 같은 폴더의 `replay-0e50d89e61bf4fbb91829bb23d1fb574.json` |
| 원본 matrixMul schema3 오프라인 진단 | `.cache/matrixmul-triage/8ff244696a2f4e9683355177110bb3ea/manifest.json` |
| 해당 matrixMul SPIR-V 검증 | 같은 폴더의 `matrix-validation.json` |

현재 Windows x64 Intel·인증된 로컬 CUDA compiler 환경의 진단이다. 다른 장치,
AMD/NVIDIA, framework 전체 실행, 범용 상위 호환 또는 release 판정을 의미하지
않는다. 원본 앱 소스를 수정하지 않고 CT import library로 빌드하는 것은 원본
NVIDIA 배포 바이너리 자체의 무수정 실행과 구분한다.

원본 vectorAdd의 새 캡처와 동일 바이너리 replay가 통과했다. 원본 matrixMul은
미지원 Runtime import0개·strict inspect exit0이며 전체 PTX가 번역됐다. 커널2개,
FMA48개, shared 선언4개·barrier4개를 관찰했다. schema3는 translated.spv를 hash로
보존하고 구조 정보만 요약해 `validation=not_run`으로 표시한다. 별도 검증 기록은
같은 module/manifest hash에 묶여 실제 고정 검증기의 통과 결과를 남긴다. 원본 앱이나
matrixMul GPU 커널은 실행하지 않았으므로 실행 호환성은 여전히 unproven이다.

다음 단계는 작은 입력으로 원본 커널의 수치 결과·경계·완료를 먼저 검증하고,
장치 선택/조회 정책과 남은 앱 경로를 확인한 뒤 전체 matrixMul 실행으로 확장하는
것이다. 성공한 번역만으로 원본 앱을 곧바로 실행하지 않는다.

```powershell
python scripts/run_fma.py
python scripts/run_upstream_vectoradd.py
python scripts/run_upstream_vectoradd.py --replay <new-vectoradd-manifest>
python scripts/triage_matrixmul.py
```

원시 로그·바이너리·vendor 자료는 무시되는 `.cache/`에만 보관한다. 사용자 기존
파일11개를 hash로 보존하고 staging·commit·upload는 하지 않는다.

[설계·구현 계획](superpowers/plans/2026-10-27-fused-f32.md),
[현재 지원 계약](compatibility/ptx-profile.md),
[NVIDIA PTX 문서](https://docs.nvidia.com/cuda/archive/12.1.1/parallel-thread-execution/index.html),
[OpenCL 확장 명령 규격](https://registry.khronos.org/SPIR-V/specs/unified1/OpenCL.ExtendedInstructionSet.100.html).
