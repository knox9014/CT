# P09a Runtime 의존성 감사

2026-10-21 읽기 전용 조사. 기준 `4c60225d027be1c8b5d969096fe2bef877f72a70`.
이 문서는 설치/ABI/native 실행 결과가 아니며 Runtime 구현 상태를 올리지 않는다.

## 확인된 입력

| 항목 | 실제 관찰 |
| --- | --- |
| Runtime 공개 헤더 | 보존된 공식 패키지에서 선택3개 파일의 바이트 일치 |
| compiler 보조 헤더 | 별도 nvcc 보조 패키지에서 선택2개 파일의 바이트 일치 |
| MSVC | vswhere로 설치된 x64 compiler 위치 확인; 이번 조사에서 빌드하지 않음 |
| nvcc 호스트 producer | PATH/표준 Toolkit 위치에서 확인되지 않음; 보존된 nvcc wheel에도 nvcc.exe 없음 |
| 기존 compiler corpus | NVRTC PTX와 nvFatbin. nvcc host stub/Runtime EXE의 증거 없음 |
| 현재 CT 로더 | cudart import 전부 거부; nvcuda.dll과 PTX/fatbin만 번들 |
| Runtime native 시험 | 이번 조사에서0개. 기존32/32를 새 Runtime 성공으로 세지 않음 |

PATH와 표준 설치 위치 조사는 알려진 경로에 한정한다. 컴퓨터 전체에 nvcc가 없다는 증명은 아니다.

## 선택 파일 provenance

### nvidia_cuda_runtime_cu12-12.0.107-py3-none-win_amd64.whl

Package SHA-256: `f595d66142e9ba5d1157d73ef06488735d814415a462714426f3989344e675eb`.

| 파일 | SHA-256 |
| --- | --- |
| cuda_runtime_api.h | `0f1cf968eb66ee320f51b3cb8f670ab1f785e1882c85291ee0918ef2d573dbf9` |
| driver_types.h | `7424f3836f00b666967ef6e813bcaa5283cc9ddb9adbf470938b79b1fd2f0370` |
| cudart_platform.h | `533a3dc955c7e7b3c6bd3b6f6298364c832657311f5b9e3e8e6608c84550dd03` |

### nvidia_cuda_nvcc_cu12-12.0.76-py3-none-win_amd64.whl

Package SHA-256: `135809154702a6302713391d3b78b9f6b4584157f539103dbd2b1d5e5922a225`.

| 파일 | SHA-256 |
| --- | --- |
| crt/host_runtime.h | `0eee347bf357fdd3c2ef5f712bde9211b75bd5acaddeaf2b365b0da53c3ca5e4` |
| fatbinary_section.h | `4ebcd4d30c74ee5c5798ee8a8856a7cf709e940e6beea73364b47792035bd0a8` |

이 해시는 보존된 원본 wheel의 해당 include 파일과 비교해 일치함을 확인했다.
처음에는5개가 모두 Runtime wheel 출처라고 가정했지만, 실제 archive 목록에서 compiler
보조2개가 없음을 확인했다. 두 번째 nvcc 보조 wheel과 대조해 실제 출처를 바로잡았다.
현재 Driver 헤더 pin2개만으로 새 Runtime 헤더 closure를 검증했다고 보지 않는다.

구현 때 compiler의 실제 include dependency 목록을 로컬에서 수집하고, transitively 사용한
vendor 파일을 원본 패키지별로 pin해야 한다. 이 표는 전체 closure나 ABI 통과 증거가 아니다.
vendor 파일/바이너리·절대 경로·raw dependency 로그는 ignored 상태를 유지한다.

## 단계별 의존성과 증거 경계

| 단계 | 필요한 것 | 열리는 주장 | 남는 것 |
| --- | --- | --- | --- |
| P09a1 | 공식 Runtime 헤더, MSVC, CT Runtime14 ABI, 단일 Driver, 로더 profile | CT 소유 공식 헤더 앱의 메모리/장치/오류 연결 | launch/등록·일반 nvcc·원본 cudart 미검증 |
| P09a2 | 실제 고정 nvcc, shared Runtime host/생성 stub, 내장 module·등록/launch | 관찰한 compiler 경로의 원형 host 연결 | 더 넓은 문법/ABI/global/RDC와 실제 외부 앱 |
| P09b | 원래 static cudart가 포함된 앱의 Driver 요구 | 그 artifact의 static Runtime 경로 | 동적 shim으로 대체됐다고 세지 않음 |

CUDA package 이름만으로 host compiler 존재를 판단하지 않는다. 실제 nvcc 확보 전 수동
host stub을 만들더라도 일반 nvcc 산출물의 호환성 증거로 승격하지 않는다.

설계: [P09a1 Runtime 연결](superpowers/specs/2026-10-21-runtime-memory-design.md).
원본 공개 자료: [Runtime 패키지](https://pypi.org/project/nvidia-cuda-runtime-cu12/12.0.107/),
[compiler 보조 패키지](https://pypi.org/project/nvidia-cuda-nvcc-cu12/12.0.76/).
