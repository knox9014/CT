# CTA-uniform control flow results — 2026-10-27

공유 메모리와 block barrier가 있는 커널에서, 모든 조건 분기가 CTA 안의 모든
스레드에게 동일하다고 증명되는 분기·반복문을 지원한다. 실제 nvcc 정수·실수
반복문을 CT Runtime/Driver로 연결해 현재 Intel GPU에서 실행했다. Driver46 /
Runtime40 프로파일은 그대로이며, 전체 CUDA 또는 일반 divergent barrier 지원을
의미하지 않는다.

## 구현 원리와 경계

상수·커널 인자 값·nctaid/ntid/ctaid는 CTA-uniform, tid 및 모든 메모리 load 결과는
varying으로 판정한다. 계산은 모든 입력이 uniform일 때만 uniform이다. 분기 합류는
AND, 루프는 고정점까지 반복하고, 모든 분기 조건은 수렴한 뒤 검사한다. 되돌아오는
간선이 있어도 entry의 초기 상태를 고정한다. `bra.uni`의 표시만으로 CTA 전체의
동일한 제어 흐름을 가정하지 않는다. 일반·조건부 bra.uni를 bra와 같이 처리한다.
실제 nvcc가 생성하는 정확한 `.pragma "nounroll";`만 실행 의미 없는 metadata로
인식한다. 다른 pragma는 미지원이며 native optimizer의 unrolling 동작은 보장하지 않는다.

공유 주소의 CFG 합류에서는 동일한 객체 출처만 보존하고, 가능한 정렬 나머지는
합친다. 객체 출처가 모호해져도 possible-shared taint를 OR로 남기므로, shared/scalar
또는 서로 다른 shared 객체의 합류가 global 접근·주소 내보내기를 우회하지 못한다.
분석 중 실패한 transfer는 보수적인 tainted 상태로 넓힌다. 수렴 후 엄격한 재검사를
통과한 상태만 사용해 각 명령의 실제 공유 객체를 선택한다.

각 분석은4096 block 방문·65536 명령 해석을 넘으면 거부하며 최종 검사도 작업량에
포함한다. 기존128-block/256-register/4096-static-instruction 제한을 유지한다.
잘못된 target·초기화되지 않은 값·도달 불가능한 block도 거부한다. emitter가 공개
IR에 대해 제어 흐름과 공유 주소 증명을 다시 검사하지만, 임의로 만든 IR 전체의
arity/type 검증기로 해석하면 안 된다.

모든 block에는 Return으로 갈 수 있는 경로가 있어야 한다. 이는 실제 반복문의
종료를 증명하지 않는다. 호출자는 유한 반복 인자·정상 메모리 범위·초기화와 경쟁
방지를 책임져야 한다. 일반 divergent 재합류, 메모리 값의 uniform 추론, 동적 공유
메모리·warp/cluster barrier·FMA 지원은 이번 범위에 포함하지 않는다.

## 검증

- 진짜 nvcc 두 엔트리의 보존 PTX와 원본 fatbin PTX의 모든 토큰을 비교했다.
  각 엔트리는 shared 배열2개, loop 내부 barrier3개, 조건 분기2개를 포함한다.
- 반복 횟수0/3/5를 각각64×2,64×3,128×4 threads/blocks로 실행했다. seed2개에서
  매번 정수832개·실수832개 출력 전체를 확인하고 입력 보존과 입력·출력 버퍼 양 끝
  guard를 검사했다. C++은 회전한 원본 값에 대한 계산식을 사용하고, 독립 Python
  oracle은 각 반복의 배열 교환 단계를 시뮬레이션한다. unsigned wrap과 작은 정확한
  F32 정수 입력을 검증한 것이며 일반 수치 정확도/성능 benchmark는 아니다.
- 실행 생략·복사 생략 대조군은 각각 exit42로 오류를 검출했다.
- 실제 고정 `spirv-val --target-env opencl1.2`가 정상 모듈을 통과시키고 undefined
  branch target 변형을 거부했다. 별도 검사에서 loop edge 제거 변형을 거부했다.
  엔트리마다5 block·조건 분기2개·backedge1개·barrier3개와 Workgroup 객체 독립성,
  volatile 접근, F32 bitcast, barrier scope/semantics0x310을 검사했다.
- false .uni, 메모리에서 읽은 분기 조건, 루프 뒷경로에서 varying이 되는 조건,
  공유 주소 합류 후 global 탈출, Return 경로 없는 loop를 오프라인에서 거부했다.
  변형 모듈과 거부 입력을 GPU에 제출하지 않았다.
- Rust workspace192개, Runtime129개, Python201개 테스트가 통과했다. 기존 ignored
  테스트4개는 실행 증거에서 제외한다. clippy `-D warnings`, workspace와 Runtime
  format 검사도 통과했다. parser·공개 IR mutation·분석 예산 소진 검사를 포함한다.

독립 설계 검토에서 지적한 공유 주소 합류의 taint 손실을 방지했고, 구현·검증기
검토 및 별도 새 검토에서 추가 concrete blocker는 발견되지 않았다. 검토 에이전트는
코드 읽기만 수행했으며 테스트·GPU 실행 증거는 별도로 수집했다.

## 소스 고정 기록

Source fingerprint: `e7ea4091297db4964c007106b3d3d4f8e991967f75e785241814443802a00b8b`.

Uniform manifest SHA-256: `7e97424c0d7f3d28ae90f876553fcdb9a97d076cc18ade5b553b8e406fbfeadd`.

| 검증 | 로컬 manifest |
| --- | --- |
| uniform loop nvcc/native·대조군 | `.cache/runtime-attribute-runs/6acc05e43383410abe8c44a8bb3158b3/uniform-control-manifest.json` |
| 기존 shared/barrier 및 Runtime/native 회귀 | 같은 폴더의 `static-shared-manifest.json`, `block-barrier-manifest.json`, `profiler-manifest.json` 등 부모 기록 |
| 원본 vectorAdd 새 빌드 | `.cache/upstream-vectoradd-runs/43835067fbbe45d08529b4a8042934bc/manifest.json` |
| 같은 vectorAdd 바이너리 재실행 | 같은 폴더의 `replay-5496abcb319e43c4a00329e100f5011f.json` |
| 원본 matrixMul 오프라인 진단 | `.cache/matrixmul-triage/b249177ebdc844ff8db5f2199d1fa9a4/manifest.json` |

이는 현재 Windows x64 Intel·인증된 로컬 CUDA compiler 환경의 진단이다. 다른 장치,
AMD/NVIDIA, framework 전체 실행, 범용 상위 호환·성능 우위 또는 release 판정을
의미하지 않는다. 원본 앱 소스를 수정하지 않고 CT import library를 사용한 빌드는
원본 NVIDIA 배포 바이너리 자체의 무수정 실행과 구분한다.

vectorAdd의 새 캡처와 동일 바이너리 replay가 통과했다. matrixMul의 미지원
Runtime import는0개·strict inspect exit0이며, 첫 오프라인 거부는 bra.uni line51에서
fma.rn.f32 line86으로 이동했다. shared 선언4개·barrier4개·FMA48개를 관찰했다.
FMA에서 parsing이 중단되므로 matrixMul 전체 커널의 제어 흐름 증명이 완료됐다는
뜻은 아니다. 원본 앱과 GPU 커널은 실행하지 않았다. 다음은 FMA의 fused 반올림
의미와 수치 검증, 장치 선택 정책, 나머지 실제 앱 장애 확인 및 전체 실행 검증이다.

```powershell
python scripts/run_uniform_control.py
python scripts/run_upstream_vectoradd.py
python scripts/run_upstream_vectoradd.py --replay <new-vectoradd-manifest>
python scripts/triage_matrixmul.py
```

원시 로그·바이너리·vendor 자료는 무시되는 `.cache/`에만 보관한다. 사용자 기존
파일11개를 hash로 보존하고 staging·commit·upload는 하지 않는다.

[설계·구현 계획](superpowers/plans/2026-10-27-uniform-control-flow.md),
[현재 지원 계약](compatibility/ptx-profile.md),
[NVIDIA PTX 문서](https://docs.nvidia.com/cuda/archive/12.1.1/parallel-thread-execution/index.html),
[Khronos SPIR-V 명세](https://registry.khronos.org/SPIR-V/specs/unified1/SPIRV.html).
