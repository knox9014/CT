# CT (Cuda Translater)

**한국어** · [English](README.en.md)

**이미 가진 Intel GPU에서 기존 CUDA 프로그램을 실행할 수 있게 만드는 프로젝트입니다.**

CUDA를 사용하는 프로그램은 GPU에 계산을 맡길 때 CUDA 드라이버를 호출합니다. CT는 그 호출을 받아 지원 범위 안의 GPU 코드(PTX)를 Intel에서 실행할 수 있는 형태(SPIR-V)로 변환하고, Intel Level Zero를 통해 실행합니다.

```text
CUDA 프로그램 → CT의 CUDA 드라이버 인터페이스 → PTX를 SPIR-V로 변환 → Intel GPU
```

**현재 집중하는 환경은 Windows x64와 Intel Arc B390입니다.** AMD 백엔드는 Intel에서 실사용 앱을 검증한 뒤의 목표입니다.

## 지금까지 확인한 것

| 항목 | 결과 |
| --- | --- |
| GPU 계산 | Arc B390에서 벡터 덧셈, ReLU, 행렬 곱셈 등 일부 CUDA 커널을 실행하고 결과를 확인했습니다. [커널 검증](https://github.com/knox9014/CT/blob/d57659f6a64d7fb211130de45a896654cce40738/docs/M2-RESULTS.md) |
| NVIDIA 공식 샘플 | `vectorAddDrv`의 원본 호스트·커널 소스로 실험용 빌드를 만들었습니다. 압축 PTX가 들어 있는 CUDA 컨테이너(fatbin)를 CT로 실행해 50,000개 결과를 검증했습니다. [빌드 방식과 결과](https://github.com/knox9014/CT/blob/d57659f6a64d7fb211130de45a896654cce40738/docs/M3e-RESULTS.md) |
| CUDA 앱 호환성 | CUDA Runtime 초기화를 진단 중입니다. CuPy 배포본의 실제 배열 연산과 범용 앱 실행은 아직 검증 전입니다. |
| 다른 GPU | Intel Arc B390에서 검증했습니다. 다른 Intel 모델과 AMD는 이후 검증 대상입니다. |

## 사용 설명서

Windows x64와 Intel Arc B390에서 소스를 빌드해 검증용 예제를 실행할 수 있습니다. 아래 명령은 공개 개발 커밋을 기준으로 작성했습니다. GitHub 기본 브랜치에는 프로젝트 문서가 있고, 실행 코드는 아래 체크아웃 단계에서 가져옵니다.

### 1. 준비하기

- Intel 그래픽 드라이버를 설치합니다. CT는 이 드라이버의 Level Zero를 사용합니다.
- Git과 Python 3을 설치하고, PowerShell 7에서 `git --version`과 `python --version`이 실행되는지 확인합니다. [Python 다운로드](https://www.python.org/downloads/windows/)
- Visual Studio Build Tools에서 **C++를 사용한 데스크톱 개발** 워크로드를 설치합니다. MSVC x64 도구와 Windows SDK를 포함하세요. [Visual Studio 다운로드](https://visualstudio.microsoft.com/downloads/)
- rustup으로 Windows MSVC용 Rust를 설치한 뒤 새 PowerShell에서 `cargo --version`을 확인합니다. [Rust 설치](https://rustup.rs/)

```powershell
git clone https://github.com/knox9014/CT.git
cd CT
git checkout --detach d57659f6a64d7fb211130de45a896654cce40738
```

### 2. Intel GPU가 동작하는지 확인하기

```powershell
cargo run --quiet --bin ct-intel-smoke
```

CT가 Level Zero에서 찾은 첫 Intel GPU를 사용합니다. 마지막 JSON에서 `"status":"pass"`와 `device`에 표시된 실제 GPU 이름을 확인하세요. 이 단계는 저장소에 포함된 SPIR-V 예제로 Intel 실행 환경을 확인합니다. [Intel 기본 테스트](https://github.com/knox9014/CT/blob/d57659f6a64d7fb211130de45a896654cce40738/docs/M0-RESULTS.md)

여러 Intel GPU 중 특정 모델을 시험하려면 예제 파일 경로 뒤에 모델명의 일부를 넣으세요. 예를 들어 `cargo run --quiet --bin ct-intel-smoke -- tests/fixtures/vector_add.spv B390`은 B390을 찾습니다.

### 3. CUDA 호출이 CT를 거쳐 실행되는지 확인하기

```powershell
pwsh -NoProfile -File scripts/run_m3_smoke.ps1
```

스크립트가 CT와 검증용 CUDA 프로그램 두 개를 빌드하고 Intel GPU에서 실행합니다. 마지막 JSON에서 `"status": "pass"`와 `"results": 514`를 확인하세요. [CUDA Driver 연결 검증](https://github.com/knox9014/CT/blob/d57659f6a64d7fb211130de45a896654cce40738/docs/M3a-RESULTS.md)

### 4. 내가 가진 프로그램 확인하기

아래 경로를 신뢰할 수 있는 Windows x64 실행 파일과 그 프로그램이 읽는 PTX 파일로 바꾸세요. 먼저 `inspect`로 실행 파일이 가져오는 CUDA 함수를 확인합니다. 동적으로 찾는 함수나 실제 계산의 호환성은 실행 파일 검사만으로 확인할 수 없습니다.

```powershell
python scripts/ct.py inspect "C:\path\to\app.exe"
cargo build -p ct-cuda
python scripts/ct.py run --ct-dll target/debug/ct_cuda.dll --ptx "C:\path\to\kernel.ptx" "C:\path\to\app.exe" -- kernel.ptx
```

`--` 뒤에는 프로그램 자체의 인자를 넣습니다. 여기서는 프로그램이 `kernel.ptx`를 인자로 받는다고 가정했습니다. CT는 실행 파일과 지정한 GPU 코드 파일을 `.cache/runs/` 아래의 실행 폴더에 복사하고, 그 폴더에서 CT를 `nvcuda.dll`로 사용합니다. 이 예제는 외부 PTX를 사용하는 독립 프로그램을 대상으로 합니다. [Driver API 지원 범위](https://github.com/knox9014/CT/blob/d57659f6a64d7fb211130de45a896654cce40738/docs/compatibility/driver-api.md) · [공식 샘플 재현](https://github.com/knox9014/CT/blob/d57659f6a64d7fb211130de45a896654cce40738/docs/M3e-RESULTS.md)

### 문제가 생기면

| 증상 | 확인할 것 |
| --- | --- |
| `link.exe`를 찾지 못하거나 MSVC 관련 오류가 발생함 | C++ 워크로드와 Windows SDK가 설치됐는지 확인하고 새 PowerShell을 엽니다. |
| GPU를 찾지 못함 | 장치 관리자에서 Arc B390이 표시되는지 확인하고 Intel 그래픽 드라이버를 확인합니다. |
| `unsupported static CUDA symbol` 또는 `CUDA Runtime imports are unsupported` | 위 Driver 실행 경로의 지원 범위를 벗어난 프로그램입니다. 오류 문구와 필요한 CUDA 함수를 확인하세요. |

문제를 공유할 때는 GPU 모델, Windows 버전, 재현 단계와 오류 문구를 적고 로그에서 개인 경로를 지워 주세요. [공개 자료 보호 규칙](https://github.com/knox9014/CT/blob/d57659f6a64d7fb211130de45a896654cce40738/docs/PUBLICATION.md)

## 다음 목표

1. 실제로 필요한 CUDA 앱 하나를 Intel에서 배포본 그대로 실행해 작업을 끝냅니다.
2. 같은 입력으로 NVIDIA 공식 드라이버에서 실행한 결과와 비교합니다.
3. 다른 Intel PC에서도 설치와 실행을 재현하고, 성능과 제한을 기록합니다.
4. Intel 검증을 바탕으로 AMD 백엔드를 추가합니다.

[개발 순서와 출시 기준](https://github.com/knox9014/CT/blob/d57659f6a64d7fb211130de45a896654cce40738/docs/CT-EXECUTION-ROADMAP.md) · [Driver API 지원 범위](https://github.com/knox9014/CT/blob/d57659f6a64d7fb211130de45a896654cce40738/docs/compatibility/driver-api.md) · [PTX 지원 범위](https://github.com/knox9014/CT/blob/d57659f6a64d7fb211130de45a896654cce40738/docs/compatibility/ptx-profile.md)

## 라이선스

CT는 [MIT 라이선스](LICENSE)로 배포합니다. 개인용·상업용으로 사용, 수정 및 재배포할 수 있습니다. 복사본이나 소프트웨어의 상당 부분을 배포할 때는 저작권 표시와 라이선스 문구를 포함해야 합니다. 제3자 자료에는 각자의 라이선스가 적용됩니다.
