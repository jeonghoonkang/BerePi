# NVIDIA DGX Spark

NVIDIA DGX Spark는 책상 위에서 AI 모델을 개발하고 실행할 수 있는 소형 AI 컴퓨터입니다. GB10 Grace Blackwell Superchip과 128GB 통합 메모리를 기반으로 대규모 언어 모델(LLM)의 추론, 미세 조정, AI 애플리케이션 개발을 지원합니다.

이 문서는 DGX Spark 제품의 주요 기능을 소개합니다. 현재 이 폴더에는 별도의 실행 코드나 설치 스크립트가 없습니다.

## 주요 기능

### 1. 로컬 AI 모델 추론

- 로컬 장비에서 모델을 실행하여 챗봇, 문서 질의응답, 텍스트 생성 등의 서비스를 개발할 수 있습니다.
- NVIDIA가 안내하는 단일 장비의 추론 지원 규모는 최대 2,000억(200B) 파라미터입니다.
- FP4 정밀도와 희소성 적용 조건에서 최대 1 PFLOP의 AI 연산 성능을 제공합니다. 실제 처리 속도는 모델, 정밀도, 입력 길이 및 실행 환경에 따라 달라집니다.

근거: [공식 제품 소개](https://www.nvidia.com/en-us/products/workstations/dgx-spark/), [하드웨어 안내](https://docs.nvidia.com/dgx/dgx-spark/hardware.html)

### 2. AI 모델 미세 조정 및 프로토타입 개발

- 사전 학습 모델을 사용자 데이터와 목적에 맞게 미세 조정할 수 있습니다.
- 공식 제품 소개 기준으로 최대 700억(70B) 파라미터 모델의 미세 조정을 지원합니다. 사용 가능한 모델 규모는 학습 방식과 메모리 사용량에 따라 달라집니다.
- AI 에이전트와 애플리케이션을 로컬에서 개발·검증하고, 이후 NVIDIA GPU 기반 클라우드나 데이터센터로 확장하는 개발 흐름을 지원합니다.

근거: [공식 제품 소개 — Workloads](https://www.nvidia.com/en-us/products/workstations/dgx-spark/)

### 3. 대용량 통합 메모리와 GPU 가속

- CPU와 GPU가 공유하는 128GB 통합 시스템 메모리를 제공합니다.
- 20코어 ARM64 CPU와 Blackwell GPU를 활용해 AI 연산과 데이터 처리 작업을 수행합니다.
- 큰 모델과 데이터셋을 다루는 실험 환경을 데스크톱 크기의 장비에 구성할 수 있습니다.

근거: [시스템 개요](https://docs.nvidia.com/dgx/dgx-spark/system-overview.html)

### 4. NVIDIA AI 개발 환경 및 컨테이너 지원

- AI 작업에 최적화된 NVIDIA DGX OS를 제공합니다.
- CUDA, cuDNN 등 NVIDIA 개발 도구와 라이브러리를 활용할 수 있습니다.
- Docker와 NVIDIA Container Runtime을 지원하여 GPU 애플리케이션을 컨테이너로 실행할 수 있습니다.
- NVIDIA NGC 컨테이너 레지스트리를 통해 AI 개발용 소프트웨어를 활용할 수 있습니다.

근거: [시스템 개요 — Software](https://docs.nvidia.com/dgx/dgx-spark/system-overview.html)

### 5. 로컬 및 원격 개발

- 모니터, 키보드, 마우스를 연결해 직접 사용할 수 있습니다.
- 같은 네트워크의 다른 컴퓨터에서 SSH, NVIDIA Sync 또는 원격 데스크톱 도구로 접속할 수 있습니다.
- 기존 개발용 PC에서 접속해 DGX Spark를 AI 연산 장비로 활용하는 구성이 가능합니다.

근거: [시스템 개요 — Flexible Access and Usage](https://docs.nvidia.com/dgx/dgx-spark/system-overview.html)

### 6. 고속 네트워크를 통한 확장

- NVIDIA ConnectX-7 네트워크를 이용해 여러 DGX Spark를 연결할 수 있습니다.
- 여러 장비를 활용하는 모델 실행에는 해당 구성을 지원하는 소프트웨어와 분산 실행 설정이 필요합니다.
- 일반 네트워크 연결에는 10GbE와 Wi-Fi 7을 지원합니다.

근거: [하드웨어 안내](https://docs.nvidia.com/dgx/dgx-spark/hardware.html), [시스템 개요](https://docs.nvidia.com/dgx/dgx-spark/system-overview.html)

## 활용 예시

다음은 DGX Spark를 기반으로 구축할 수 있는 애플리케이션 예시입니다. 각 서비스에는 별도의 모델 및 소프트웨어 구성이 필요합니다.

- **문서 질의응답**: 내부 문서를 검색하고 LLM으로 답변을 생성하는 RAG 서비스 개발
- **개인용 AI 비서**: 로컬 모델을 이용한 요약, 글쓰기, 작업 보조 기능 구현
- **모델 맞춤화**: 특정 도메인의 데이터로 모델을 미세 조정하고 결과 비교
- **AI 서비스 실험**: 웹 UI 또는 API와 모델을 연동하여 사용 흐름 검증

## 시작하기

1. [공식 사용자 가이드](https://docs.nvidia.com/dgx/dgx-spark/)에 따라 초기 설정을 진행합니다.
2. 로컬 또는 원격 접속 환경을 구성합니다.
3. 실행할 모델과 도구가 ARM64 및 해당 GPU 환경을 지원하는지 확인합니다.
4. [DGX Spark Playbooks](https://build.nvidia.com/spark)의 예제를 참고하여 개발 환경과 워크로드를 구성합니다.

문서 확인 기준일: 2026-09-24. 제품 기능과 소프트웨어 지원 범위는 업데이트에 따라 변경될 수 있습니다.
