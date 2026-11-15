# Original matrix kernel results — 2026-10-27

NVIDIA cuda-samples의 원본 matrixMul PTX를 수정 없이 CT Driver로 연결해 Intel
GPU에서 실행했다. 타일16·32 두 커널을 네 가지 크기에서 검사했다. 이는 원본
커널 실행이며, 원본 matrixMul EXE와 장치 선택·전체 Runtime 경로의 실행 증거는
아니다. Driver46 / Runtime40 프로파일과 Rust 제품 코드는 유지했고 검증 도구를
추가했다.

## 입력과 실제 실행 범위

ABI는 원본의 C,A,B,wA,wB 다섯 인자이며 wA=K, wB=N이다. 행 우선 A[M,K]와
B[K,N]에서 C[M,N]을 구한다. 양쪽 커널의 다중 타일 사례는 K와 N이 달라 인자
순서·행 간격 오류를 구분한다.

| 타일 | M | K | N | grid x,y | block x,y | 내부 타일 반복 | 출력 값 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 16 | 16 | 16 | 16 | 1,1 | 16,16 | 1 | 256 |
| 16 | 32 | 48 | 64 | 4,2 | 16,16 | 3 | 2048 |
| 32 | 32 | 32 | 32 | 1,1 | 32,32 | 1 | 1024 |
| 32 | 64 | 64 | 96 | 3,2 | 32,32 | 2 | 6144 |

현재 어댑터는 Intel Arc B390이며 max threads/group은1024로 관찰됐다. 실제
cuDeviceGet 결과와 속성1..7을 사용해 네 사례 모두의 한도를 첫 launch 전에
검사한다. 부분 타일, 임의 크기와 불충분한 장치는 이 실행 프로파일에서 거부한다.

A는 정수[-8,8]/8, B는 정수[-9,9]/16으로 만든다. 정수 dot product를128로 나눈
값과 모든 F32 중간합이 정확히 표현되므로 허용 오차 없이 비교할 수 있다.
seed2개에서 매번9472개 출력 전체, 합계18,944개를 비트 단위로 확인했다. 모든
A/B 바이트를 보존하고 A/B/C 각각 앞뒤16-word guard를 검사했다. C 데이터는
NaN으로 시작해 쓰기 생략이 정상 결과로 오인되지 않게 한다.

## 독립된 실행·검사 경로

별도 Python worker가 명시적인 로컬 CT DLL을 로드한다. 정해진 job 형식·입력
recipe·파일 hash·원본 PTX hash·엔트리 이름을 검사하고, 최적화 Python과 오래된
readback을 거부한다. PTX와 인자 저장 공간을 유지하며 원본 커널을 launch하고
cuCtxSynchronize를 호출한 뒤 A/B/C 전체를 읽어 파일로 기록한다. 모듈·메모리·
context 정리가 성공해야 API completed를 보고한다. 정수 dot 기준 결과를 worker가
계산하거나 GPU에 올리는 경로는 없다. 부모 프로세스가 별도로 수치를 판정한다.

동일한 worker를 기존 no-launch/no-copy forwarding DLL로 실행했다. GPU 할당 직후
실제 cuMemsetD32로 NaN을 채워 no-copy가 오래된 정상 입력을 재사용할 가능성을
제거했다. 모든 대조군은 API와 cleanup을 정상 완료했지만 네 사례의 수치 검사는
모두 실패했다. no-launch는 업로드한 초기 버퍼 그대로, no-copy는 A/B의 NaN poison과
C의 NaN 상태라는 구체적인 서명까지 확인했다. API exit0만으로 성공 처리하지 않는다.

동결된 모듈·DLL·같은 seed를 새 프로세스에서 replay했다. 정상 실행의 모든 raw
readback과 API 보고서 hash가 원래 기록과 같았고, 대조군 서명도 다시 검출했다.
원본 PTX·fatbin 대응은 인증된 원본 빌드/triage에 연결되며, 복사한 SPIR-V는 실제
고정 spirv-val(opencl1.2)을 통과했다. 제품 실행은 원본 PTX를 Driver에 로드한다.

## 회귀·검토와 기록

Python215개, Rust workspace195개, Runtime129개 테스트가 통과했다. 기존 ignored
4개는 실행 증거에서 제외한다. strict clippy/format 검사도 통과했다. 원본 vectorAdd
새 빌드/replay와 이전 FMA·uniform loop·shared·barrier·스트림·복사·이벤트 native
회귀를 같은 소스에서 다시 캡처했다. worker·oracle·builder의 읽기 전용 독립 검토에서
concrete blocker는 발견되지 않았으며, 검토 에이전트는 빌드/GPU 작업을 수행하지 않았다.

Source fingerprint: `6c210c9f24101d455647986d19df39cdda5d0d9a367ed8c5295c9d212d745c24`.

Main manifest SHA-256: `33be1ba4c76978cc67892c5de686b85608f9273681916ec041855ab5ac736e42`.

Original PTX SHA-256: `999de47c5a9d2610641f37fd5a949523d3e29c3b6c257d5dff7f65e9359ec07b`.

| 기록 | 로컬 경로 |
| --- | --- |
| 원본 커널 실행/대조군 | `.cache/runtime-attribute-runs/aeab0cd5381b4f36a7c1c7d353e8d1f4/matrix-kernel-manifest.json` |
| 같은 모듈·입력 replay | 같은 폴더의 `matrix-kernel-replay-bd741401052b44fc87254de860446258.json` |
| 이전 native 회귀 | 같은 폴더의 `fma-manifest.json` 등 부모 기록 |
| 원본 vectorAdd 새 빌드/replay | `.cache/upstream-vectoradd-runs/37ce5a125b934c139037a4860c509c03/manifest.json`, `replay-b2e87d4ffb154c788fc83e94a712485e.json` |
| 원본 matrixMul 빌드/오프라인 진단 | `.cache/matrixmul-triage/e941bded41bb42d29988399f6dd93978/manifest.json` |

```powershell
python scripts/run_matrix_kernels.py
python scripts/run_matrix_kernels.py --audit <new-manifest>
python scripts/run_matrix_kernels.py --replay <new-manifest>
```

현재 Windows x64 Intel 환경과 위 크기·입력의 진단이다. 다른 데이터/크기/장치,
AMD/NVIDIA, CUDA framework 전체, 성능 또는 release 준비를 증명하지 않는다.
다음 과제는 원본 EXE의 compute capability 조회(75/76), 명시적 장치 선택과 나머지
Runtime 경로다. 실제 Intel 정보와 CUDA 호환 프로파일을 구분하는 계약을 정해야 한다.
원본 앱의 PASS 문구에 더해 외부의 finite/수치 검증과 생략 대조군도 필요하다.

원시 로그·버퍼·바이너리·vendor 자료는 무시되는 `.cache/`에만 두었다. 사용자 기존
파일11개를 보존하고 staging·commit·upload는 하지 않았다.

[구현 계획](superpowers/plans/2026-10-27-original-matrix-kernels.md),
[지원 계약](compatibility/ptx-profile.md), [이전 FMA 결과](FUSED-F32-RESULTS.md).
