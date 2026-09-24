# Gemma4 Ollama — NVIDIA 및 Mac GPU 실행

Ollama 기반 Gemma4 웹/API 서버와 클라이언트입니다. Linux에서는 NVIDIA GPU를,
Apple Silicon Mac에서는 Metal GPU 가속을 사용합니다.

- [서버 설치, 실행 및 API 설명](server/README.md)
- [클라이언트 설명](client/README.md)

## RTX 5090 · DGX Spark · Apple M4 Max 성능 비교

비교 기준일: 2026-09-24. Gemma4를 Ollama로 실행하는 용도를 기준으로 정리했습니다.
Apple 모델명은 **M4 Max**이며, 아래 Mac 사양은 현재 로컬 머신인
**40코어 GPU / 통합 메모리 64GB** 구성입니다.

### 공식 하드웨어 사양

| 항목 | GeForce RTX 5090 | DGX Spark | Apple M4 Max — 현재 머신 |
|---|---|---|---|
| 제품 형태 | 별도 PC에 장착하는 GPU 카드 | GB10 기반 소형 AI 컴퓨터 | MacBook Pro의 통합 SoC |
| GPU 아키텍처 | NVIDIA Blackwell | NVIDIA Grace Blackwell | Apple 40코어 GPU |
| 메모리 | 전용 GDDR7 VRAM 32GB | CPU·GPU 공유 메모리 128GB | CPU·GPU 공유 메모리 64GB |
| 메모리 대역폭 | 1,792GB/s | 273GB/s | 546GB/s |
| 제조사 AI 연산 지표 | 3,352 AI TOPS | 최대 1 PFLOP, FP4·희소성 조건 | 같은 조건의 GPU FP4 지표 미제시 |
| 이 프로젝트의 GPU 실행 경로 | Ollama NVIDIA GPU 백엔드 | Ollama NVIDIA GPU 백엔드, ARM64 환경 | macOS 네이티브 Ollama의 Metal |
| GPU 선택값 | `auto` 또는 NVIDIA GPU 인덱스 | `auto` 또는 NVIDIA GPU 인덱스 | `auto` 또는 `metal` |

사양 근거: [NVIDIA RTX 5090](https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/rtx-5090/),
[NVIDIA의 RTX 5090 메모리 대역폭 안내](https://blogs.nvidia.com/blog/studio-ai-geforce-rtx-50-series-broadcast/),
[DGX Spark 하드웨어](https://docs.nvidia.com/dgx/dgx-spark/hardware.html),
[Apple M4 Max 사양](https://support.apple.com/en-us/121553).
Ollama의 플랫폼별 GPU 지원은 [공식 GPU 문서](https://docs.ollama.com/gpu)를 참고하세요.

M4 Max 제품군에는 32코어 GPU·410GB/s 구성도 있습니다. 위 표는 40코어 GPU·546GB/s
구성이며, 제품군의 최대 메모리인 128GB와 현재 머신의 64GB를 구분해야 합니다.
통합 메모리는 OS와 다른 앱도 사용하므로 전체 용량을 모델에 할당할 수 있는 것은 아닙니다.

### Gemma4 실행 시 성능 해석

아래는 사양에 따른 예상 특성이며, 세 장비에서 동일 조건으로 측정한 속도 순위는 아닙니다.

| 작업 조건 | 비교 및 판단 |
|---|---|
| 모델과 KV 캐시가 32GB VRAM에 모두 들어가는 경우 | RTX 5090은 높은 메모리 대역폭과 NVIDIA GPU 연산 자원을 갖춰 빠른 추론을 기대할 수 있습니다. 실제 우위와 배수는 동일 모델·백엔드 설정으로 측정해야 합니다. |
| 모델 실행에 32GB보다 많은 GPU 메모리가 필요한 경우 | 단일 RTX 5090은 CPU 메모리로 일부를 옮기거나 양자화·컨텍스트 축소가 필요할 수 있습니다. M4 Max 64GB와 Spark 128GB는 더 큰 메모리 공간이 장점입니다. |
| 한 사용자의 순차 토큰 생성 | 가중치를 반복해서 읽는 작업에서는 메모리 대역폭이 중요합니다. M4 Max의 대역폭은 Spark의 2배지만, 이것이 Gemma4 생성 속도 2배를 의미하지는 않습니다. |
| 긴 입력 처리 또는 여러 요청 동시 처리 | 메모리 대역폭뿐 아니라 연산 성능, 배치 처리, KV 캐시 용량, 커널 최적화가 중요합니다. 단일 사용자 결과를 다중 사용자 처리량으로 일반화할 수 없습니다. |
| 더 큰 모델을 NVIDIA 환경에서 개발·실험 | Spark는 128GB 통합 메모리와 NVIDIA 소프트웨어 환경의 조합이 장점입니다. ARM64와 GB10을 지원하는 런타임·컨테이너가 필요합니다. |
| 현재 Mac에서 Gemma4 사용 | 별도 장비 없이 Metal로 실행할 수 있으며, 이 머신에서는 `gemma4:31b`의 GPU 적재와 추론을 확인했습니다. |

대역폭 사양만 계산하면 RTX 5090은 M4 Max의 약 **3.28배**, Spark의 약 **6.56배**입니다.
이 값은 **메모리 대역폭 비율**이며 토큰 생성 속도 비율이 아닙니다.
FP4, INT4 양자화, FP16, 희소성의 연산 조건도 서로 다르므로 제조사 TOPS/PFLOPS를
그대로 나눠 Ollama 성능을 비교하면 안 됩니다. Apple Neural Engine의 TOPS도
이 프로젝트에서 사용하는 Metal GPU 성능으로 대입할 수 없습니다.

### 이 프로젝트에서 확인한 실행 결과

| 장비 | Gemma4 검증 상태 | 동일 조건 토큰 생성 속도 |
|---|---|---|
| RTX 5090 | 이번 작업에서 직접 측정하지 않음 | 미측정 |
| DGX Spark | 이번 작업에서 직접 측정하지 않음 | 미측정 |
| M4 Max 40코어 / 64GB | Ollama 0.34.3, `gemma4:31b`, 컨텍스트 2048에서 추론 및 `100% GPU` 적재 확인 | 정식 반복 벤치마크 미실시 |

로컬 Ollama 목록의 모델 파일 크기는 약 19GB였고, 검증 시 `ollama ps`의 적재 크기는
약 20GB였습니다. 이는 해당 모델 아티팩트와 짧은 입력에서의 관측값이며,
모든 양자화 버전이나 긴 컨텍스트의 메모리 사용량을 보장하지 않습니다.

정확한 비교에는 세 장비에서 모델 digest·양자화, Ollama 버전, 입력 내용과 토큰 수,
컨텍스트 길이, 출력 토큰 수, thinking 설정 및 동시 요청 수를 맞춰야 합니다.
모델 로딩을 포함한 최초 요청과 로딩 후 반복 요청을 분리하고, 반복 측정의 중앙값을
비교하세요. `ok`처럼 짧은 응답은 동작 확인용이며 지속적인 생성 속도 비교에는 부족합니다.
프롬프트 캐시를 사용하지 않은 요청에서 API의
`prompt_eval_count / (prompt_eval_duration / 1e9)`는 입력 처리 속도,
`eval_count / (eval_duration / 1e9)`는 생성 속도(tokens/s)입니다.
캐시 적중이 있다면 입력 토큰 수에서 `prompt_eval_cached_count`를 빼고 계산하며,
시간이 0인 결과는 속도 계산에서 제외합니다.
두 지표와 전체 응답 시간을 함께 기록하면 입력 처리와 생성 단계의 차이를 볼 수 있습니다.
응답 필드 기준은 [Ollama Generate API](https://docs.ollama.com/api/generate)를 참고하세요.

## Apple Silicon Mac에서 실행

macOS에 네이티브 Ollama와 Python 3를 설치한 환경에서 실행합니다.
이미 설치된 Ollama와 모델은 재사용합니다.

```bash
cd server
printf 'metal\n' > gpu-selection
/bin/bash ./run_service.sh
```

기본 웹 주소는 `http://localhost:8082`입니다. 별도 인스턴스 실행 예시:

```bash
/bin/bash ./run_service.sh 8083 metal
```

이 경우 웹 포트는 `8083`, Ollama 포트는 `18083`입니다.
Apple GPU는 Ollama가 자동으로 사용하며 CUDA 설치는 필요하지 않습니다.
`metal`은 Apple GPU 사용 의도를 나타내고 실제 모델 배치는 Ollama가 결정합니다.
`auto`도 Mac GPU를 자동 활용합니다. `mps`는 `metal`의 별칭으로 받지만,
Ollama 자체는 PyTorch MPS가 아니라 Metal 백엔드로 추론합니다.

## 실제 GPU 사용 확인

웹에서 답변을 한 번 생성한 뒤 다음 명령을 실행합니다.

```bash
ollama ps
# 별도 인스턴스를 실행했다면 해당 Ollama 포트 지정
OLLAMA_HOST=127.0.0.1:18083 ollama ps
```

`PROCESSOR` 열의 `100% GPU`는 모델 전체가 GPU에 적재되었다는 뜻이며,
GPU 연산 사용률이 항상 100%라는 의미는 아닙니다.
CPU/GPU가 함께 표시되면 일부만 GPU에 적재된 상태입니다.
메모리에서 모델이 내려가면 목록이 비어 있으므로 다시 요청한 직후 확인합니다.

2026-09-24 로컬 검증: M4 Max, 통합 메모리 64GB, Ollama 0.34.3 환경에서
`gemma4:31b`를 컨텍스트 2048로 실행하고 `100% GPU` 적재를 확인했습니다.
모델과 컨텍스트 크기에 따라 필요한 메모리는 달라집니다.

이미 실행 중이던 Python 웹 서버에는 코드 변경이 자동 반영되지 않습니다.
실행 중인 서버를 기존 실행 방식으로 재시작하면 새 GPU 목록과 선택 기능이 반영됩니다.
Ollama 자체의 Metal 가속은 별도로 이미 사용할 수 있습니다.

GPU 탐지, CPU 요청 옵션, Linux CUDA 유지 및 macOS 시작 회귀 테스트:

```bash
cd server
python3 -m unittest test_mac_gpu test_macos_startup
```

Mac의 GPU 메모리는 시스템 메모리와 공유됩니다. 메모리가 부족하면 컨텍스트를
줄이거나 더 작은 모델을 사용하세요. Docker Desktop 내부의 Ollama 대신
macOS 네이티브 Ollama를 사용해야 Apple GPU 가속을 이용할 수 있습니다.

근거: [Ollama GPU 지원](https://docs.ollama.com/gpu),
[Ollama FAQ — GPU 적재 확인 및 Docker 제약](https://docs.ollama.com/faq).
